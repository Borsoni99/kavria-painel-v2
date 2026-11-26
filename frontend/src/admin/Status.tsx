import { useState } from "react";
import { api } from "../lib/api";
import { useApi } from "../lib/useApi";
import { Notice, PageTitle } from "./Layout";

type Status = {
  jodda_configurada: boolean;
  workers_enabled: boolean;
  health: { last_ok_at: string | null; last_error: string | null; consecutive_errors: number };
  linhas_pedido: number;
  primeiro_dia: string | null;
  ultimo_dia: string | null;
  por_marketplace: Record<string, number>;
  pedidos_ultima_sync: { novas: number; atualizadas: number; at: string } | null;
  resumos_ultima_sync: { at: string } | null;
  carga_historica: { from: string; to: string; at: string } | null;
};

const when = (iso: string | null | undefined) => (iso ? new Date(iso).toLocaleString("pt-BR") : "—");

export default function StatusPage() {
  const { data, error, reload } = useApi<Status>("/api/admin/status");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const tvKeyHint = `${window.location.origin}/tv?key=…`;

  const syncNow = async () => {
    setBusy(true);
    setMsg(null);
    try {
      const r = await api.post<{ pedidos: { novas: number; atualizadas: number } }>("/api/admin/sync", {});
      setMsg(`Sincronizado: ${r.pedidos.novas} linhas novas, ${r.pedidos.atualizadas} atualizadas.`);
      reload();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <PageTitle title="Status da integração">
        <button className="btn" onClick={syncNow} disabled={busy}>{busy ? "Sincronizando…" : "Sincronizar agora"}</button>
      </PageTitle>
      {error && <Notice tone="error">{error}</Notice>}
      {msg && <Notice tone="ok">{msg}</Notice>}
      {data && (
        <div className="grid gap-4 md:grid-cols-2">
          <div className="card">
            <div className="card-title">Jodda AI</div>
            <dl className="space-y-2 text-sm">
              <Row label="Chave da API">{data.jodda_configurada ? "configurada" : <span className="text-red-400">ausente no .env</span>}</Row>
              <Row label="Sincronização">{data.workers_enabled ? "ativa" : "desligada (WORKERS_ENABLED=false)"}</Row>
              <Row label="Última resposta OK">{when(data.health.last_ok_at)}</Row>
              <Row label="Pedidos (última busca)">
                {data.pedidos_ultima_sync ? `${when(data.pedidos_ultima_sync.at)} · ${data.pedidos_ultima_sync.novas} novas` : "—"}
              </Row>
              <Row label="Resumos (mês, hoje, Ads)">{when(data.resumos_ultima_sync?.at)}</Row>
              {data.health.consecutive_errors > 0 && (
                <Row label="Último erro"><span className="text-red-400">{data.health.last_error}</span></Row>
              )}
            </dl>
          </div>
          <div className="card">
            <div className="card-title">Pedidos guardados</div>
            <dl className="space-y-2 text-sm">
              <Row label="Linhas de pedido">{data.linhas_pedido.toLocaleString("pt-BR")}</Row>
              <Row label="Período">{data.primeiro_dia ?? "—"} a {data.ultimo_dia ?? "—"}</Row>
              {Object.entries(data.por_marketplace).map(([mk, n]) => <Row key={mk} label={mk}>{n.toLocaleString("pt-BR")} linhas</Row>)}
              <Row label="Carga histórica">{data.carga_historica ? `${data.carga_historica.from} a ${data.carga_historica.to}` : "—"}</Row>
            </dl>
          </div>
          <div className="card md:col-span-2 text-sm text-slate-400">
            TV: abra <span className="font-mono text-slate-200">{tvKeyHint}</span> com a TV_ACCESS_KEY do .env.
            A Jodda só tem dados a partir de novembro/2026; o histórico cresce daqui para frente.
          </div>
        </div>
      )}
    </>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-4 border-b border-ink-800 pb-2">
      <dt className="text-slate-400">{label}</dt>
      <dd className="text-right text-slate-100">{children}</dd>
    </div>
  );
}
