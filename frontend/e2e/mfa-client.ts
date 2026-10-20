// Synthetic verification only. Real endpoints enforce every factor and limit.
import {createHmac} from 'node:crypto';
import fs from 'node:fs';
import type {APIRequestContext,APIResponse} from '@playwright/test';
type State={secret:string;codes:string[]};
const cacheFile=process.env.BUILDTRUST_E2E_MFA_CACHE;
const factors=new Map<string,State>(cacheFile&&fs.existsSync(cacheFile)?Object.entries(JSON.parse(fs.readFileSync(cacheFile,'utf8'))):[]);
const save=()=>{if(cacheFile){fs.writeFileSync(cacheFile,JSON.stringify(Object.fromEntries(factors)),{mode:0o600});}};
export const marker={'X-BuildTrust-Request':'1'};
const pause=(seconds:number)=>new Promise(resolve=>setTimeout(resolve,Math.max(1,Math.min(60,seconds))*1000+150));
export function totp(secret:string){
  const alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';const bits=[...secret.replace(/=/g,'').toUpperCase()].map(c=>alphabet.indexOf(c).toString(2).padStart(5,'0')).join('');
  const bytes=Buffer.from((bits.match(/.{8}/g)||[]).map(b=>parseInt(b,2)));const counter=Buffer.alloc(8);counter.writeBigUInt64BE(BigInt(Math.floor(Date.now()/30000)));
  const hash=createHmac('sha1',bytes).update(counter).digest(),offset=hash[hash.length-1]&15;
  return ((hash.readUInt32BE(offset)&0x7fffffff)%1000000).toString().padStart(6,'0');
}
export async function respectfulPost(request:APIRequestContext,url:string,options:Parameters<APIRequestContext['post']>[1]={}){
  let response=await request.post(url,{timeout:60000,...options,headers:{...options?.headers,...marker}});
  for(let i=0;i<4&&response.status()===429;i++){await pause(Number(response.headers()['retry-after']||1));response=await request.post(url,{timeout:60000,...options,headers:{...options?.headers,...marker}});}
  return response;
}
export async function completeMfa(request:APIRequestContext,response:APIResponse,email:string,password:string){
  if(!response.ok())return response;
  const step=await response.json();if(step.access_token||!step.challenge_token)return response;
  if(cacheFile&&fs.existsSync(cacheFile)){factors.clear();for(const [key,value] of Object.entries(JSON.parse(fs.readFileSync(cacheFile,'utf8'))))factors.set(key,value as State);}
  if(step.status==='MFA_SETUP_REQUIRED'){
    const start=await respectfulPost(request,'/api/v1/auth/mfa/enroll/start',{data:{challenge_token:step.challenge_token}});if(!start.ok())throw new Error('Isolated MFA setup failed: '+start.status());
    const setup=await start.json();const confirmed=await respectfulPost(request,'/api/v1/auth/mfa/enroll/confirm',{data:{challenge_token:step.challenge_token,code:totp(setup.secret)}});
    if(!confirmed.ok())throw new Error('Isolated MFA confirmation failed: '+confirmed.status());
    factors.set(email,{secret:setup.secret,codes:(await confirmed.json()).recovery_codes});save();return confirmed;
  }
  const state=factors.get(email);if(!state)throw new Error('Use a fresh isolated browser database with its own enrolled factors.');
  const code=state.codes.shift();save();
  const completed=await respectfulPost(request,'/api/v1/auth/mfa/verify',{data:{challenge_token:step.challenge_token,code}});
  if(!completed.ok())throw new Error('Isolated MFA verification failed: '+completed.status());
  if(state.codes.length<=4){
    const renewed=await respectfulPost(request,'/api/v1/auth/mfa/recovery-codes/regenerate',{headers:{Authorization:'Bearer '+(await completed.json()).access_token},data:{current_password:password,code:state.codes.shift()}});
    if(!renewed.ok())throw new Error('Isolated MFA code renewal failed: '+renewed.status());state.codes=(await renewed.json()).recovery_codes;save();return renewed;
  }
  return completed;
}
