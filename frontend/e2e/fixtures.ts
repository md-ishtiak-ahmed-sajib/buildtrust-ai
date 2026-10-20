import { test as base, expect } from "@playwright/test";
import {completeMfa,marker,respectfulPost} from './mfa-client';
export { expect };
export type { Page, APIRequestContext } from "@playwright/test";
const pause = (seconds: number) => new Promise(resolve=>setTimeout(resolve,Math.min(60,Math.max(1,seconds))*1000+100));

// The suite signs in many people quickly. Respect the real server allowance;
// never disable throttling or reset buckets to make browser checks pass.
export const test=base.extend<{admissionAware:boolean;manualMfa:boolean}>({
  manualMfa:[false,{option:true}],
  request:async({request},use)=>{
    const proxy=new Proxy(request,{get(target,key){
      if(key==="post")return async(url:string,options?:Parameters<typeof target.post>[1])=>{
        const result=await respectfulPost(target,url,options);
        const data=options?.data as {email?:string;password?:string}|undefined;
        return url.endsWith('/auth/login')?completeMfa(target,result,data?.email||'',data?.password||''):result;
      };
      if(['put','patch','delete','fetch'].includes(String(key)))return (url:string,options?:{headers?:Record<string,string>})=>(Reflect.get(target,key).bind(target))(url,{...options,headers:{...options?.headers,...marker}});
      const value=Reflect.get(target,key);return typeof value==="function"?value.bind(target):value;
    }});
    await use(proxy);
  },
  admissionAware:[async({page,manualMfa},use,testInfo)=>{
    testInfo.setTimeout(Math.max(testInfo.timeout,300000));
    await page.route("**/api/v1/auth/login",async route=>{
      let response=await route.fetch();
      if(response.status()===429){await pause(Number(response.headers()["retry-after"]||1));response=await route.fetch();}
      if(!manualMfa){const body=route.request().postDataJSON();response=await completeMfa(page.request,response,body.email,body.password);}
      await route.fulfill({response});
    });
    await use(true);
  },{auto:true}]
});
