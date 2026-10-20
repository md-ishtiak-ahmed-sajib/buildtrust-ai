import {
  createContext,
  useContext,
  useEffect,
  useState,
  lazy,
  Suspense,
} from "react";
import { useGuardedAction } from "./DraftGuard";
import {
  NavLink,
  Routes,
  Route,
  Navigate,
  Link,
  useLocation,
} from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  LayoutDashboard,
  Files,
  ScanLine,
  ChartNoAxesCombined,
  Wallet,
  ShieldCheck,
  LogOut,
  ChevronDown,
  Building2,
  ArrowRight,
  LockKeyhole,
  Check,
  Menu,
  CircleHelp,
  Ruler,
  NotebookPen,
  PackageSearch,
} from "lucide-react";
import { api, post, setToken, titleCase } from "./api";
import { PasswordChange, PasswordRecovery } from "./AccountSecurity";
import type { Project, User } from "./types";
import {MfaLogin,type LoginComplete,type LoginChallenge} from './MfaSecurity';
import { Loading, ErrorState } from "./ui";
const OverviewPage = lazy(() =>
  import("./pages/Overview").then((m) => ({ default: m.OverviewPage })),
);
const InvoicesPage = lazy(() =>
  import("./pages/Invoices").then((m) => ({ default: m.InvoicesPage })),
);
const PaymentsPage = lazy(() =>
  import("./pages/Payments").then((m) => ({ default: m.PaymentsPage })),
);
const CashFlowPage = lazy(() =>
  import("./pages/CashFlow").then((m) => ({ default: m.CashFlowPage })),
);
const AuditPage = lazy(() =>
  import("./pages/Audit").then((m) => ({ default: m.AuditPage })),
);
const DocumentsPage = lazy(() =>
  import("./pages/Documents").then((m) => ({ default: m.DocumentsPage })),
);
const MaterialsPage = lazy(() =>
  import("./advanced/Prices").then((m) => ({ default: m.MaterialsPage })),
);
const EstimatesPage = lazy(() =>
  import("./advanced/Estimates").then((m) => ({ default: m.EstimatesPage })),
);
const TakeoffPage = lazy(() =>
  import("./advanced/Takeoff").then((m) => ({ default: m.TakeoffPage })),
);
const OperationsPage = lazy(() =>
  import("./Operations").then((m) => ({ default: m.OperationsPage })),
);
const ControlsPage = lazy(() =>
  import("./Controls").then((m) => ({ default: m.ControlsPage })),
);
const CommercialPage = lazy(() => import("./Controls").then((m) => ({ default: () => <m.ControlsPage commercial /> })));
const AdministrationPage = lazy(() => import("./Administration").then((m) => ({ default: m.AdministrationPage })));
const PerformancePage = lazy(() =>
  import("./Performance").then((m) => ({ default: m.PerformancePage })),
);

type AppContext = {
  user: User;
  project: Project;
  refresh: () => Promise<void>;
};
const Context = createContext<AppContext>(null!);
export const useWorkspace = () => useContext(Context);
const nav = [
  { to: "/overview", label: "Overview", icon: LayoutDashboard },
  { to: "/documents", label: "Documents", icon: Files },
  { to: "/estimates", label: "BOQ & Estimates", icon: NotebookPen },
  { to: "/takeoff", label: "Quantity Takeoff", icon: Ruler },
  { to: "/materials", label: "Materials & Prices", icon: PackageSearch },
  { to: "/invoices", label: "Invoice Intelligence", icon: ScanLine },
  { to: "/cashflow", label: "Cash-Flow Forecast", icon: ChartNoAxesCombined },
  { to: "/payments", label: "Payment Center", icon: Wallet },
  { to: "/audit", label: "Audit & Security", icon: ShieldCheck },
  { to: "/reviews", label: "Review Inbox", icon: Files },
  { to: "/controls", label: "Cost Control & Accounting", icon: NotebookPen },
  { to: "/commercial", label: "Commercial Management", icon: Building2 },
  { to: "/team", label: "Team & Access", icon: ShieldCheck },
  {
    to: "/performance",
    label: "Performance & Scenarios",
    icon: ChartNoAxesCombined,
  },
];

export default function App() {
  const guardAction = useGuardedAction();
  const [user, setUser] = useState<User | null>(null),
    [projectId, setProjectId] = useState(0),
    [projectFilter, setProjectFilter] = useState(""),
    [mobile, setMobile] = useState(false);
  const client = useQueryClient(),
    location = useLocation();
  useEffect(() => {
    const expire = () => {
      setToken("");
      setUser(null);
      client.clear();
    };
    window.addEventListener("session-expired", expire);
    return () => window.removeEventListener("session-expired", expire);
  }, [client]);
  const projects = useQuery({
    queryKey: ["projects"],
    queryFn: () => api<Project[]>("/projects"),
    enabled: !!user,
  });
  const archived = useQuery({
    queryKey: ["archived-projects"],
    queryFn: () => api<Project[]>("/projects/archived"),
    enabled: !!user,
  });
  const project =
    [...(projects.data || []), ...(archived.data || [])].find(
      (p) => p.id === projectId,
    ) || projects.data?.[0];
  const [signoutNotice, setSignoutNotice] = useState("");
  const clearAccount = () => {
    setToken("");
    setUser(null);
    setProjectId(0);
    client.clear();
  };
  const logout = async () => {
    try { await post("/auth/logout"); setSignoutNotice("Signed out. The server session was revoked."); }
    catch { setSignoutNotice("Local sign-out finished, but server revocation could not be confirmed. The server token expires within 30 minutes."); }
    finally { clearAccount(); }
  };
  if (!user) return <><Login onLogin={u=>{setSignoutNotice("");setUser(u);}} />{signoutNotice && <p className="signout-notice" role="status">{signoutNotice}</p>}</>;
  if (projects.isPending) return <Loading />;
  if (projects.error) return <ErrorState error={projects.error} onRetry={() => { void projects.refetch(); }} />;
  if (!project)
    return (
      <div className="state">
        No project is assigned to this account.
        <button className="button" onClick={logout}>
          Sign out
        </button>
      </div>
    );
  return (
    <Context.Provider
      value={{
        user,
        project,
        refresh: async () => {
          await client.invalidateQueries();
        },
      }}
    >
      <div className="app">
        <aside className={`sidebar ${mobile ? "mobile-open" : ""}`}>
          <Link to="/overview" className="brand">
            <span className="brand-mark">
              <Building2 size={24} />
            </span>
            <span>
              BuildTrust<span className="brand-ai"> AI</span>
              <small>CONSTRUCTION FINANCE</small>
            </span>
          </Link>
          <div className="sidebar-label">WORKSPACE</div>
          <nav aria-label="Main navigation">
            {nav.map((n) => (
              <NavLink key={n.to} to={n.to} onClick={() => setMobile(false)}>
                <n.icon size={19} />
                <span>{n.label}</span>
                {n.to === "/invoices" && <span className="nav-dot" />}
              </NavLink>
            ))}
          </nav>
          <div className="sidebar-bottom">
            <div className="sandbox-box">
              <ShieldCheck size={23} />
              <strong>A safer way to pay</strong>
              <p>
                Every decision backed by evidence. Every payment approved by
                you.
              </p>
              <span>
                <span className="live-dot" />
                Sandbox environment
              </span>
            </div>
            <a
              className="support-link"
              href="/docs"
              target="_blank"
              rel="noreferrer"
            >
              <CircleHelp size={17} /> API reference <ArrowRight size={14} />
            </a>
            <div className="sidebar-version">
              BuildTrust AI <span>v0.2.0</span>
            </div>
          </div>
        </aside>
        <div className="main-shell">
          <header className="topbar">
            <div className="topbar-left">
              <button
                className="icon-button mobile-toggle"
                aria-label="Toggle navigation"
                onClick={() => setMobile(!mobile)}
              >
                <Menu size={21} />
              </button>
              <span className="breadcrumb">
                Workspace <span>/</span>{" "}
                <strong>
                  {nav.find((n) => location.pathname.startsWith(n.to))?.label ||
                    "Overview"}
                </strong>
              </span>
            </div>
            <div className="topbar-right">
              <PasswordChange onChanged={()=>{setSignoutNotice("Password changed. All sessions were revoked; sign in again.");clearAccount();}} />
              <span className="simulation">
                <span />
                SIMULATION
              </span>
              <div className="user-avatar">
                {user.name
                  .split(" ")
                  .map((s) => s[0])
                  .join("")}
              </div>
              <div className="user-info">
                <strong>{user.name}</strong>
                <small>{titleCase(user.role)}</small>
              </div>
              <button
                className="icon-button"
                aria-label="Sign out"
                title="Sign out"
                onClick={() => guardAction(logout)}
              >
                <LogOut size={17} />
              </button>
            </div>
          </header>
          <main>
            <div className="project-strip">
              <div>
                <Building2 size={16} />
                <input
                  className="project-search"
                  type="search"
                  aria-label="Find project"
                  placeholder="Find project"
                  value={projectFilter}
                  onChange={(e) => setProjectFilter(e.target.value)}
                />
                <select
                  aria-label="Select project"
                  value={project.id}
                  onChange={(e) => {
                    const value = Number(e.target.value);
                    guardAction(() => setProjectId(value));
                  }}
                >
                  {projects.data
                    ?.filter(
                      (p) =>
                        p.id === project.id ||
                        p.name
                          .toLowerCase()
                          .includes(projectFilter.toLowerCase()),
                    )
                    .map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name}
                      </option>
                    ))}
                  {!!archived.data?.length && (
                    <optgroup label="Archived runs · read only">
                      {archived.data
                        .filter(
                          (p) =>
                            p.id === project.id ||
                            `${p.name} ${p.run_id}`
                              .toLowerCase()
                              .includes(projectFilter.toLowerCase()),
                        )
                        .map((p) => (
                          <option key={p.id} value={p.id}>
                            {p.name} · {p.run_id}
                          </option>
                        ))}
                    </optgroup>
                  )}
                </select>
                <ChevronDown size={14} />
              </div>
              <span>
                <span className="live-dot" />
                All financial data persisted locally{" "}
                <span className="strip-divider">|</span> {project.currency} · Project currency
              </span>
            </div>
            {!project.active && <div className="notice" role="status">Archived run · read only. Original records, receipts and audit evidence remain available.</div>}
            <Suspense fallback={<Loading />}>
              <Routes>
                <Route path="/overview" element={<OverviewPage />} />
                <Route path="/documents" element={<DocumentsPage />} />
                <Route path="/estimates" element={<EstimatesPage />} />
                <Route path="/takeoff" element={<TakeoffPage />} />
                <Route path="/materials" element={<MaterialsPage />} />
                <Route path="/invoices" element={<InvoicesPage />} />
                <Route path="/cashflow" element={<CashFlowPage />} />
                <Route path="/payments" element={<PaymentsPage />} />
                <Route path="/audit" element={<AuditPage />} />
                <Route path="/reviews" element={<OperationsPage />} />
                <Route path="/controls" element={<ControlsPage />} />
                <Route path="/commercial" element={<CommercialPage />} />
                <Route path="/team" element={<AdministrationPage />} />
                <Route path="/performance" element={<PerformancePage />} />
                <Route path="*" element={<Navigate to="/overview" replace />} />
              </Routes>
            </Suspense>
            <footer className="app-footer">
              <span>
                BuildTrust Demo Construction Ltd. · All records are fictional.
              </span>
              <span>
                <LockKeyhole size={12} /> Human authorization required for every
                payment
              </span>
            </footer>
          </main>
        </div>
      </div>
    </Context.Provider>
  );
}
function Login({ onLogin }: { onLogin: (u: User) => void }) {
  const [challenge,setChallenge]=useState<LoginChallenge|null>(null);
  const [email, setEmail] = useState("operator@buildtrust.demo"),
    [password, setPassword] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  return (
    <div className="login-page">
      <section className="login-story">
        <div className="brand">
          <span className="brand-mark">
            <Building2 size={24} />
          </span>
          <span>BuildTrust AI</span>
        </div>
        <div>
          <span className="eyebrow">CONSTRUCTION FINANCE, WITH CONFIDENCE</span>
          <h1>
            Good projects start
            <br />
            with trusted decisions.
          </h1>
          <p>
            Bring your construction documents, cash flow, and payment controls
            into one clear workspace.
          </p>
          <div className="login-proof">
            {[
              "Four-way document verification",
              "Human approval before settlement",
              "Traceable evidence for every decision",
            ].map((t) => (
              <div key={t}>
                <Check size={17} />
                {t}
              </div>
            ))}
          </div>
        </div>
        <small>2026 Shenzhen FinTechathon · Topic E: SME Finance Copilot</small>
      </section>
      <section className="login-form-area">
        {challenge?<MfaLogin challenge={challenge} onCancel={()=>setChallenge(null)} onComplete={r=>{setToken(r.access_token);setChallenge(null);onLogin(r.user);}}/>:<form
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            setError("");
            try {
              const r = await post<LoginComplete | LoginChallenge>(
                "/auth/login",
                { email, password },
              );
              setPassword('');
              if('access_token' in r){setToken(r.access_token);onLogin(r.user);}
              else setChallenge(r);
            } catch (e) {
              setError((e as Error).message);
            } finally {
              setBusy(false);
            }
          }}
        >
          <span className="simulation">
            <span />
            SANDBOX ENVIRONMENT
          </span>
          <h1>Welcome to BuildTrust</h1>
          <p>Sign in to your financial workspace.</p>
          <label>
            Email address
            <input
              type="email"
              autoComplete="username"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </label>
          <label>
            Password
            <input
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>
          {error && <ErrorState message={error} />}
          <button className="button primary login-submit" disabled={busy}>
            {busy ? "Signing in…" : "Sign in to workspace"}
            <ArrowRight size={17} />
          </button>
          <div className="login-help">
            <LockKeyhole size={16} />
            <p>
              Use the demo credentials printed by setup. All transfers are
              simulated and require an authorized approver.
            </p>
          </div>
        </form>}
        {!challenge&&<PasswordRecovery />}
      </section>
    </div>
  );
}
