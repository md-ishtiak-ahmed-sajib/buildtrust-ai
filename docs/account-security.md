# Accounts, recovery and private backups

The four passwords in the README belong to the separate public demo on localhost port 8003. Keep them public and unchanged. Their password-change and recovery controls are disabled. Private setup continues to generate different passwords.

## Sign in and sign out

Each sign-in creates a 30-minute server session. The browser keeps its token in memory. Sign out revokes that session on the server. Password changes and recovery revoke every session for the affected account. Deactivation and role changes also revoke sessions. Project membership is checked on every protected request.

After installing the security migration, sign in again. Earlier tokens have no server session and are rejected. Financial records, approvals, balances and audit history are preserved.

If the server cannot be reached during sign-out, the browser clears local access and explains that server revocation was not confirmed. The token still expires within its original 30 minutes. A successful local screen change alone is not proof of server logout.

## Authenticator setup and recovery

1. Private Admin and Finance Manager accounts must set up an authenticator after entering the correct password. Other private roles may enable it in **Account security**.
2. Select **Show authenticator setup**. Scan the locally generated QR code with a compatible authenticator, or enter the manual key. No QR service receives the secret.
3. Enter the current six-digit code. Codes last 30 seconds; one period on either side is allowed for clock drift. Keep the computer and phone clocks accurate. A used period cannot be reused.
4. Save all ten recovery codes privately when shown. Each works once. They are never shown again; the server stores only hashes.
5. On later sign-ins, enter a fresh authenticator code or an unused recovery code. The restricted sign-in step expires after five minutes and allows five failed attempts. It grants no project access.
6. Replacing a factor or recovery codes requires the current password and an existing second factor. Required-role accounts cannot disable MFA. These changes revoke earlier sessions.

The public-demo profile is exempt. Its four README passwords remain unchanged. Neither password recovery nor a web Admin can remove another person's MFA. If all factors are lost, the local owner uses this private interactive command:

```powershell
uv run --project backend python scripts/manage_security.py mfa-reset --email YOUR_PRIVATE_EMAIL
```

The command revokes sessions and affected pending payment authority, records the reset without secrets and requires fresh enrollment. Local operating-system ownership remains the recovery trust boundary. Do not record setup keys, QR codes or recovery codes in screenshots or submission files.

## Change or recover a private password

1. Signed-in users open **Account security** and supply their current password and a new password of 12–128 characters.
2. For a forgotten non-Admin password, an Admin opens **Team & Access**, verifies the person's identity and selects **Issue recovery token**.
3. Share the token privately with that person. Hide it after sharing. The database stores its hash, not its text. Audit events contain no token.
4. On the sign-in page, open **Recover a forgotten password**. Paste the token and enter the new password.
5. The token expires after 15 minutes and can be used once. A new token invalidates earlier unused tokens. Recovery does not reactivate a disabled account.

An Admin account needs local-owner recovery. From a private interactive terminal at the repository root:

```powershell
uv run --project backend python scripts/manage_security.py recover --email YOUR_ADMIN_EMAIL
```

The command uses the private profile selected by `BUILDTRUST_DATA_DIR` or `.env`. It refuses redirected output and public demo recovery. It displays one token for private delivery; do not record the terminal. No email is sent. Local operating-system ownership is the recovery trust boundary.

## Usage limits

| Operation | Default allowance |
|---|---|
| All sign-in attempts | 50 per IP per minute, before password hashing |
| Failed sign-in | 10 per normalized account and 50 per IP per minute |
| Admin account creation | 5 per Admin per minute |
| Price refresh | 5 per user per minute; cached requests still pass admission checks |
| Upload, import, analysis and export group | 10 per user per minute, shared across projects |
| Document preview | 30 per user per minute |
| Recovery issue | 5 per target account and 10 per issuing Admin per hour |
| Recovery redemption | 10 attempts per IP per minute |
| MFA operations | 20 per IP per minute, 10 per operation group/IP per minute and 5 per account per minute |
| Optional local model | 20 calls per user and 100 per project per UTC day; 2 concurrent calls |

Limits persist in SQLite and survive restarts. A 429 response includes `Retry-After`. The supported deployment is one local application process. There is no public signup.

Paid providers stay disabled until explicitly enabled with credentials, positive call limits and a positive operation ceiling and daily budget. Provider budgets use their USD billing units, separate from BDT project money. Configure an upper bound for the complete search operation, including any billable retries/retrieval. Unknown or missing bounds block paid access. The reserved upper bound is charged against the local allowance even after a failed call; it is not a claim about the provider's actual invoice. Unknown submissions keep their reservation until reviewed. No live paid calls were used for automated acceptance.

The local model uses a loopback HTTP endpoint, a 10-second bound, at most 1,024 generated tokens and a 128 KB response limit. Exhausted or unavailable model access falls back to deterministic explanations. Model text cannot approve or execute payments.

## Private backup and restore

Create a new backup file; existing backup files are never overwritten:

```powershell
uv run --project backend python scripts/manage_security.py backup --output data/backups/project.private.zip
```

The backup includes a consistent SQLite snapshot, referenced uploads, signing material, the separate MFA encryption key and local credential/profile files when present. Its manifest records checksums and configuration identifiers. It is sensitive private data, not a submission artifact. Keep a protected copy outside the computer for disaster recovery.

Restore to a **new, empty directory**, never over the working profile:

```powershell
uv run --project backend python scripts/manage_security.py restore --archive data/backups/project.private.zip --target data/restore-check
```

Restore verifies archive bounds, paths, hashes, database integrity, foreign keys and the audit chain. It then revokes copied sessions and recovery tokens and appends a restore audit event. Sign in again after restoration; an enrolled account still needs its second factor. A missing or mismatched MFA encryption key fails closed and is never silently replaced. Restoring an older backup can restore older recovery-code state: replace recovery codes after recovery and review account access before sharing the restored profile. Review the restored account roles and active status before shared use. After a credential incident, use local-owner recovery to replace affected passwords. The acceptance test also signs in against a restored copy and compares project balances.

The runtime root, uploads, database, signing material and backups receive private OS permissions. Windows allows the owner, SYSTEM and local Administrators. Linux uses owner-only files/directories. This is access control, not encryption. An unrestricted OS administrator remains trusted.
