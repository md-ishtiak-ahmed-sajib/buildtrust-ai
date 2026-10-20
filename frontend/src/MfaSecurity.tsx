import {useState} from 'react';
import {useQuery} from '@tanstack/react-query';
import {api,post,setToken} from './api';
import type {User} from './types';

export type LoginComplete={access_token:string;user:User;recovery_codes?:string[]};
export type LoginChallenge={status:'MFA_SETUP_REQUIRED'|'MFA_REQUIRED';challenge_token:string;expires_in:number};
type Enrollment=LoginChallenge&{secret:string;provisioning_uri:string;qr_png_base64:string};

function RecoveryCodes({codes,onDone}:{codes:string[];onDone:()=>void}){
  return <section className="mfa-panel" aria-label="Save recovery codes"><h2>Save your recovery codes</h2>
    <p>Each code works once. Save them privately. They are shown only now and are never emailed.</p>
    <pre className="mfa-codes" aria-label="One-time recovery codes">{codes.join('\n')}</pre>
    <button type="button" className="button primary" onClick={onDone}>I saved my codes — continue</button></section>;
}

export function MfaLogin({challenge,onComplete,onCancel}:{challenge:LoginChallenge;onComplete:(result:LoginComplete)=>void;onCancel:()=>void}){
  const [enrollment,setEnrollment]=useState<Enrollment|null>('qr_png_base64' in challenge?challenge as Enrollment:null),[code,setCode]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(false),[complete,setComplete]=useState<LoginComplete|null>(null);
  if(complete)return <RecoveryCodes codes={complete.recovery_codes||[]} onDone={()=>{setCode('');setEnrollment(null);onComplete(complete);setComplete(null);}}/>;
  const setup=challenge.status==='MFA_SETUP_REQUIRED';
  return <section className="mfa-panel" aria-label="Authenticator verification"><h1>{setup?'Set up your authenticator':'Verify your authenticator'}</h1>
    <p>{setup?'Private Admin and Finance accounts need a second factor before opening the workspace.':'Enter a fresh authenticator code or an unused recovery code.'}</p>
    <p>The sign-in step expires after five minutes. A code you just used cannot be used again.</p>
    {setup&&!enrollment&&<button className="button primary" type="button" disabled={busy} onClick={async()=>{setBusy(true);setError('');try{setEnrollment(await post<Enrollment>('/auth/mfa/enroll/start',{challenge_token:challenge.challenge_token}));}catch(e){setError((e as Error).message);}finally{setBusy(false);}}}>Show authenticator setup</button>}
    {enrollment&&<><img className="mfa-qr" src={'data:image/png;base64,'+enrollment.qr_png_base64} alt="Scan this private authenticator setup code"/><label>Manual setup key<input readOnly aria-label="Manual setup key" value={enrollment.secret} autoComplete="off"/></label><p>Scan locally with your authenticator app. Keep the setup key private.</p></>}
    {(!setup||enrollment)&&<form onSubmit={async e=>{e.preventDefault();setBusy(true);setError('');try{const result=await post<LoginComplete>(setup?'/auth/mfa/enroll/confirm':'/auth/mfa/verify',{challenge_token:challenge.challenge_token,code});setToken(result.access_token);setCode('');setEnrollment(null);if(result.recovery_codes?.length)setComplete(result);else onComplete(result);}catch(e){setError((e as Error).message);}finally{setBusy(false);}}}>
      <label>{setup?'Authenticator code':'Authenticator or recovery code'}<input type="password" autoFocus required autoComplete="one-time-code" maxLength={64} value={code} onChange={e=>setCode(e.target.value)} /></label>
      <button className="button primary" disabled={busy}>{busy?'Checking…':'Verify and continue'}</button></form>}
    {error&&<p role="alert">{error}</p>}<button className="button" type="button" onClick={()=>{setCode('');setEnrollment(null);onCancel();}}>Back to password sign-in</button>
    <p>Lost both your authenticator and recovery codes? Ask the local owner. Password recovery does not remove MFA.</p>
  </section>;
}

export function MfaSettings({onSignedOut}:{onSignedOut:()=>void}){
  const status=useQuery({queryKey:['mfa-status'],queryFn:()=>api<{enabled:boolean;required:boolean;public_demo:boolean;recovery_codes_remaining:number}>('/auth/mfa/status')});
  const [password,setPassword]=useState(''),[code,setCode]=useState(''),[setup,setSetup]=useState<Enrollment|null>(null),[codes,setCodes]=useState<string[]>([]),[error,setError]=useState(''),[busy,setBusy]=useState(false);
  if(status.isPending)return <p role="status">Loading authenticator settings…</p>;
  if(status.error)return <p role="alert">{status.error.message}</p>;
  if(status.data?.public_demo)return <p>The four public demo accounts do not require MFA. Private accounts follow the MFA policy.</p>;
  if(codes.length)return <RecoveryCodes codes={codes} onDone={()=>{setCodes([]);void status.refetch();}}/>;
  if(setup)return <MfaLogin challenge={setup} onCancel={()=>setSetup(null)} onComplete={r=>{setToken(r.access_token);setSetup(null);void status.refetch();}}/>;
  return <section className="mfa-panel"><h3>Authenticator security</h3><p>{status.data?.enabled?'Enabled':'Not enabled'} · {status.data?.required?'Required for your role':'Optional for your role'}</p>
    {status.data?.enabled&&<p>{status.data.recovery_codes_remaining} unused recovery codes remain.</p>}
    <label>Confirm current password<input type="password" autoComplete="current-password" value={password} maxLength={128} onChange={e=>setPassword(e.target.value)}/></label>
    {status.data?.enabled&&<label>Fresh authenticator or unused recovery code<input type="password" autoComplete="one-time-code" value={code} maxLength={64} onChange={e=>setCode(e.target.value)}/></label>}
    <div className="mfa-actions"><button type="button" className="button" disabled={busy||!password} onClick={async()=>{setBusy(true);setError('');try{setSetup(await post<Enrollment>('/auth/mfa/enroll/start',{current_password:password,...(status.data?.enabled?{code}:{})}));setPassword('');setCode('');}catch(e){setError((e as Error).message);}finally{setBusy(false);}}}>{status.data?.enabled?'Replace authenticator':'Enable authenticator'}</button>
    {status.data?.enabled&&<><button className="button" type="button" disabled={busy||!password||!code} onClick={async()=>{setBusy(true);setError('');try{const r=await post<LoginComplete>('/auth/mfa/recovery-codes/regenerate',{current_password:password,code});setToken(r.access_token);setCodes(r.recovery_codes||[]);setPassword('');setCode('');}catch(e){setError((e as Error).message);}finally{setBusy(false);}}}>Replace recovery codes</button>
      <button className="button" type="button" disabled={busy||!password||!code||status.data.required} title={status.data.required?'Your role requires MFA':undefined} onClick={async()=>{setBusy(true);setError('');try{await post('/auth/mfa/disable',{current_password:password,code});setPassword('');setCode('');onSignedOut();}catch(e){setError((e as Error).message);}finally{setBusy(false);}}}>Disable MFA</button></>}
    </div>{status.data?.required&&<p>Your role cannot disable MFA. Only the local owner can reset a lost setup.</p>}{error&&<p role="alert">{error}</p>}
  </section>;
}
