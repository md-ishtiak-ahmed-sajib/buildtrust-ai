import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useWorkspace } from "./App";
import { api, post, titleCase } from "./api";
import { PageTitle, Panel, ConfirmButton, Loading, ErrorState } from "./ui";
import { Field, useAction } from "./advanced/shared";
import { usePasswordOptions } from "./AccountSecurity";

type Account = { id: number; name: string; email: string; role: string; active: boolean; version: number };
const roles = ["OPERATOR", "FINANCE_MANAGER", "ADMIN", "AUDITOR"];
export function AdministrationPage() {
  const { user, project } = useWorkspace(), query = useQueryClient(), action = useAction();
  const [name, setName] = useState(""), [email, setEmail] = useState(""), [password, setPassword] = useState("");
  const [role, setRole] = useState("OPERATOR"), [filter, setFilter] = useState("");
  const [changes, setChanges] = useState<Record<number, { role: string; active: boolean }>>({});
  const options=usePasswordOptions();
  const [recovery,setRecovery]=useState<{token:string;expires_at:string;email:string}|null>(null);
  const accounts = useQuery({ queryKey: ["local-accounts"], enabled: user.role === "ADMIN",
    queryFn: () => api<Account[]>("/administration/users") });
  const members = useQuery({ queryKey: ["project-members", project.id], enabled: user.role === "ADMIN",
    queryFn: () => api<Account[]>(`/administration/members?project_id=${project.id}`) });
  const reload = () => query.invalidateQueries();
  if (user.role !== "ADMIN") return <ErrorState message="An active Admin manages local accounts and project access." />;
  return <>
    <PageTitle eyebrow="LOCAL ACCOUNTS & PROJECT ACCESS" title="Team & Access"
      description="Create individual accounts for independent preparation, checking, approval and audit. Permissions are checked by the backend on every request." />
    {action.feedback}
    {recovery && <Panel title="Recovery token — share privately once"><p>Verify {recovery.email} before sharing. Expires: {recovery.expires_at}. It is not stored in browser history.</p><label>Single-use token<input readOnly value={recovery.token} autoComplete="off" /></label><button className="button" onClick={()=>setRecovery(null)}>Hide and clear token</button></Panel>}
    <Panel title="Create local account">
      <form className="advanced-grid" onSubmit={event => { event.preventDefault(); void action.run(async () => {
        await post("/administration/users", { name, email, password, role });
        setName(""); setEmail(""); setPassword(""); await reload();
      }, "Local account created. Assign its project membership below."); }}>
        <Field label="Team member name"><input required value={name} onChange={event => setName(event.target.value)} maxLength={200} /></Field>
        <Field label="Account email"><input required type="email" value={email} onChange={event => setEmail(event.target.value)} autoComplete="off" maxLength={254} /></Field>
        <Field label="Initial private password"><input required type="password" value={password} onChange={event => setPassword(event.target.value)} minLength={12} maxLength={128} autoComplete="new-password" /></Field>
        <Field label="New account role"><select value={role} onChange={event => setRole(event.target.value)}>{roles.map(value => <option key={value} value={value}>{titleCase(value)}</option>)}</select></Field>
        <button className="button primary" disabled={action.busy || !project.active}>Create account</button>
      </form>
      <p>Share credentials privately. Passwords are hashed and are never returned by the account API.</p>
    </Panel>
    <Panel title={`Accounts and membership · ${project.name}`}>
      <Field label="Search team accounts"><input type="search" value={filter} onChange={event => setFilter(event.target.value)} /></Field>
      <p>The last active Admin and the last Admin assigned to each project are protected. Account changes take effect on subsequent requests.</p>
      {accounts.error || members.error ? <ErrorState message={(accounts.error || members.error)!.message} /> : accounts.isPending || members.isPending ? <Loading /> :
        <div className="table-scroll"><table><caption>Local accounts and access to the selected project</caption>
          <thead><tr><th>Account</th><th>Current role</th><th>Active</th><th>Project membership</th><th>Changes</th></tr></thead>
          <tbody>{accounts.data.filter(account => `${account.name} ${account.email}`.toLowerCase().includes(filter.toLowerCase())).map(account => {
            const selected = changes[account.id] || { role: account.role, active: account.active };
            const member = members.data.some(row => row.id === account.id);
            return <tr key={account.id}><td>{account.name}<br /><small>{account.email}</small></td>
              <td><select aria-label={`Role for ${account.email}`} value={selected.role} onChange={event => setChanges(value => ({ ...value, [account.id]: { ...selected, role: event.target.value } }))}>{roles.map(value => <option key={value}>{value}</option>)}</select></td>
              <td><input type="checkbox" aria-label={`Active account ${account.email}`} checked={selected.active} onChange={event => setChanges(value => ({ ...value, [account.id]: { ...selected, active: event.target.checked } }))} /></td>
              <td>{member ? "Assigned" : "No access"}<br /><ConfirmButton title={`${member ? "Remove" : "Assign"} project access?`}
                description={`${account.name} ${member ? "will lose" : "will gain"} access to ${project.name}.`}
                disabled={action.busy || !project.active || !account.active}
                onConfirm={() => action.run(async () => { await post(`/administration/members?project_id=${project.id}`, { user_id: account.id, member: !member }); await reload(); }, "Project membership updated").then(() => {})}>{member ? "Remove access" : "Assign access"}</ConfirmButton></td>
              <td>{options.data?.password_management_enabled && account.role !== "ADMIN" && account.active && <button className="button" disabled={action.busy} onClick={()=>void action.run(async()=>{const r=await post<{token:string;expires_at:string}>(`/administration/users/${account.id}/recovery`);setRecovery({...r,email:account.email});},"Recovery token issued. Verify the recipient before sharing.")}>Issue recovery token</button>}<ConfirmButton title="Apply account authority changes?" description={`Update role and active status for ${account.name}. Existing financial approvals are rechecked against current authority.`}
                disabled={action.busy || !project.active || (selected.role === account.role && selected.active === account.active)}
                onConfirm={() => action.run(async () => { await api(`/administration/users/${account.id}`, { method: "PATCH", body: JSON.stringify({ ...selected, expected_version: account.version }) }); setChanges(value => { const next = { ...value }; delete next[account.id]; return next; }); await reload(); }, "Account authority updated").then(() => {})}>Apply changes</ConfirmButton></td></tr>;
          })}</tbody></table></div>}
    </Panel>
  </>;
}
