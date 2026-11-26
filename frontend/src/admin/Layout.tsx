import type { ReactNode } from "react";
import { NavLink, Outlet } from "react-router-dom";

const links = [
  { to: "/admin", label: "Status", end: true },
  { to: "/admin/metas", label: "Metas" },
];

export default function AdminLayout() {
  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-10 border-b border-ink-700 bg-ink-950/95 backdrop-blur">
        <div className="mx-auto flex max-w-screen-2xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
          <div className="text-lg font-semibold tracking-tight">
            Kavria <span className="text-slate-500">· painel v2 multicanal</span>
          </div>
          <nav className="flex flex-1 flex-wrap gap-1">
            {links.map((l) => (
              <NavLink
                key={l.to}
                to={l.to}
                end={l.end}
                className={({ isActive }) =>
                  `rounded-lg px-3 py-1.5 text-sm ${isActive ? "bg-ink-700 text-white" : "text-slate-400 hover:bg-ink-800 hover:text-slate-200"}`
                }
              >
                {l.label}
              </NavLink>
            ))}
          </nav>
          <form method="post" action="/admin/logout">
            <button className="btn-ghost">Sair</button>
          </form>
        </div>
      </header>
      <main className="mx-auto max-w-screen-2xl px-4 py-6">
        <Outlet />
      </main>
    </div>
  );
}

export function PageTitle({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
      <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
      {children}
    </div>
  );
}

export function Notice({ tone, children }: { tone: "ok" | "error" | "warn"; children: ReactNode }) {
  const cls = {
    ok: "border-emerald-500/40 bg-emerald-500/10 text-emerald-200",
    error: "border-red-500/40 bg-red-500/10 text-red-200",
    warn: "border-amber-500/40 bg-amber-500/10 text-amber-100",
  }[tone];
  return <div className={`mb-4 rounded-lg border px-4 py-3 text-sm ${cls}`}>{children}</div>;
}
