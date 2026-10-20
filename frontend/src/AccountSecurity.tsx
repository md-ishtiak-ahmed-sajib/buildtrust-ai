import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, post } from "./api";
import {MfaSettings} from './MfaSecurity';

export function usePasswordOptions() {
  return useQuery({queryKey:["password-options"], queryFn:()=>api<{password_management_enabled:boolean;public_demo:boolean}>("/auth/options")});
}

export function PasswordChange({onChanged}:{onChanged:()=>void}) {
  const options=usePasswordOptions();
  const [current,setCurrent]=useState(""),[next,setNext]=useState(""),[message,setMessage]=useState(""),[busy,setBusy]=useState(false);
  return <details className="account-security"><summary>Account security</summary><div className="account-security-card">
    <h3>Change password</h3>
    {!options.data?.password_management_enabled ? <p>The four public demo passwords stay fixed. Use the README accounts.</p> : <form onSubmit={async event=>{event.preventDefault();setBusy(true);setMessage("");try{await post("/auth/password/change",{current_password:current,new_password:next});setCurrent("");setNext("");onChanged();}catch(error){setMessage((error as Error).message);}finally{setBusy(false);}}}>
      <label>Current password<input required type="password" autoComplete="current-password" value={current} onChange={e=>setCurrent(e.target.value)}/></label>
      <label>New password (12–128 characters)<input required type="password" autoComplete="new-password" minLength={12} maxLength={128} value={next} onChange={e=>setNext(e.target.value)}/></label>
      <button className="button primary" disabled={busy}>Change password and sign out</button>
      <p role="status">{message}</p>
    </form>}
    <MfaSettings onSignedOut={onChanged}/>
  </div></details>;
}

export function PasswordRecovery() {
  const options=usePasswordOptions();
  const [token,setToken]=useState(""),[next,setNext]=useState(""),[message,setMessage]=useState(""),[busy,setBusy]=useState(false);
  if(!options.data?.password_management_enabled)return null;
  return <details className="recovery-panel"><summary>Recover a forgotten password</summary>
    <p>Ask your Admin for a recovery token after they verify your identity. Admin accounts require the local-owner command. Tokens expire in 15 minutes.</p>
    <form onSubmit={async e=>{e.preventDefault();setBusy(true);setMessage("");try{const r=await post<{message:string}>("/auth/password/reset",{token,new_password:next});setMessage(r.message);setToken("");setNext("");}catch(error){setMessage((error as Error).message);}finally{setBusy(false);}}}>
      <label>Recovery token<input required type="password" autoComplete="off" value={token} onChange={e=>setToken(e.target.value)}/></label>
      <label>New password<input required type="password" autoComplete="new-password" minLength={12} maxLength={128} value={next} onChange={e=>setNext(e.target.value)}/></label>
      <button className="button" disabled={busy}>Reset password</button><p role="status">{message}</p>
    </form>
  </details>;
}
