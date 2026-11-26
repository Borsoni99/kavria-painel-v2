import { useState } from "react";
import { api } from "../lib/api";
import { money, moneyInput, monthLabel } from "../lib/format";
import { useApi } from "../lib/useApi";
import { Notice, PageTitle } from "./Layout";

type Goals = {
  months: { month: string; goal_c: number }[];
  changes: { month: string; old_c: number | null; new_c: number; changed_at: string }[];
  current_month: string;
};

function nextMonths(from: string, n: number) {
  const [y, m] = from.split("-").map(Number);
  return Array.from({ length: n }, (_, i) => {
    const d = new Date(y, m - 1 + i, 1);
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
  });
}

export default function Metas() {
  const { data, error, reload } = useApi<Goals>("/api/admin/goals");
  const [editing, setEditing] = useState<Record<string, string>>({});
  const [msg, setMsg] = useState<{ tone: "ok" | "error"; text: string } | null>(null);

  if (!data) return error ? <Notice tone="error">{error}</Notice> : <div className="text-slate-400">Carregando…</div>;
  const byMonth = Object.fromEntries(data.months.map((m) => [m.month, m.goal_c]));
  const months = Array.from(new Set([...nextMonths(data.current_month, 3), ...data.months.map((m) => m.month)])).sort().reverse();

  const save = async (month: string) => {
    try {
      await api.put(`/api/admin/goals/${month}`, { goal: editing[month] });
      setMsg({ tone: "ok", text: `Meta de ${monthLabel(month)} salva.` });
      setEditing((e) => ({ ...e, [month]: "" }));
      reload();
    } catch (e) {
      setMsg({ tone: "error", text: e instanceof Error ? e.message : String(e) });
    }
  };

  return (
    <>
      <PageTitle title="Metas mensais (4 canais)" />
      {msg && <Notice tone={msg.tone}>{msg.text}</Notice>}
      <div className="card max-w-2xl">
        <div className="card-title">Meta de faturamento por mês</div>
        <table className="table">
          <thead><tr><th>Mês</th><th className="num">Meta atual</th><th>Nova meta</th><th /></tr></thead>
          <tbody>
            {months.map((m) => (
              <tr key={m}>
                <td>{monthLabel(m)}{m === data.current_month && <span className="pill ml-2 bg-brand-600/30 text-brand-400">atual</span>}</td>
                <td className="num">{money(byMonth[m])}</td>
                <td>
                  <input className="input w-36 py-1 text-right" placeholder={byMonth[m] ? moneyInput(byMonth[m]) : "R$"}
                    value={editing[m] ?? ""} onChange={(e) => setEditing({ ...editing, [m]: e.target.value })}
                    onKeyDown={(e) => { if (e.key === "Enter") void save(m); }} />
                </td>
                <td><button className="btn-ghost py-1" disabled={!editing[m]} onClick={() => void save(m)}>Salvar</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {data.changes.length > 0 && (
        <div className="card mt-6 max-w-2xl">
          <div className="card-title">Histórico de alterações</div>
          <ul className="space-y-1 text-sm text-slate-300">
            {data.changes.map((c, i) => (
              <li key={i}>{new Date(c.changed_at).toLocaleString("pt-BR")} · {monthLabel(c.month)}: {money(c.old_c)} → {money(c.new_c)}</li>
            ))}
          </ul>
        </div>
      )}
    </>
  );
}
