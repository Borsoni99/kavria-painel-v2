import { useEffect, useLayoutEffect, useRef, useState } from "react";
import logoUrl from "../assets/kavria-logo-h.png";
import { marginTone } from "../lib/format";
import { GoalRing, StackedBarChart, type Guide } from "./charts";
import { ago, brl, brlCents, clock, hhmm, longDate, pctTv } from "./fmt";
import { soundFor, useSaleSounds } from "./sounds";
import "./tv.css";

// ---------------------------------------------------------------- tipos do snapshot (backend: finance/tv_data.py)

type Channel = {
  marketplace: string; faturamento_c: number; pedidos: number; lucro_c: number; margem_bp: number | null;
  participacao_bp: number | null; hoje_c: number; hoje_pedidos: number; ads_c: number;
};
type FeedItem = {
  order_id: string; grupo: string; ts: string; marketplace: string; title: string | null; sku: string; qtd: number;
  bruto_c: number; lucro_c: number; margem_bp: number | null; logistic_type: string | null;
};
type Snapshot = {
  month: string; today: string; build: string;
  settings: { margin_green_bp: number; margin_yellow_bp: number; sound_enabled: boolean; sound_threshold_c: number; sound_volume: number };
  totals: { faturamento_c: number; pedidos: number; ticket_medio_c: number | null; lucro_c: number | null; lucro_antes_ads_c: number | null;
    margem_bp: number | null; margem_pos_ads_bp: number | null; cancelados_mes: number };
  goal: { goal_c: number | null; atingido_bp: number | null; projecao_c: number | null; projecao_bp: number | null;
    falta_por_dia_c: number | null; dias_restantes: number };
  hoje: { bruto_c: number; vendas: number; ticket_medio_c: number | null; lucro_c: number; margem_bp: number | null };
  ads: { disponivel: boolean; investimento_c: number; receita_ads_c: number | null; acos_bp: number | null; roas_x100: number | null;
    tacos_bp: number | null; por_canal: { marketplace: string; gasto_c: number }[] };
  channels: Channel[];
  rolling: { day: string; total_c: number; lucro_c: number; por_canal: Record<string, number> }[];
  feed: FeedItem[];
  top_produtos: { sku: string; descricao: string; faturamento: number; unidades: number; margem_pct: number | null }[];
  status: { last_sync_at: string | null; consecutive_errors: number; account_connected: boolean; reauth_required: boolean };
};

/** Cor fixa por canal (validada: modo escuro, superfície #15120d) — a cor segue o canal, nunca a posição. */
const CHANNEL: Record<string, { color: string; short: string }> = {
  "Mercado Livre": { color: "#c09020", short: "Mercado Livre" },
  Amazon: { color: "#3987e5", short: "Amazon" },
  Shopee: { color: "#e8553a", short: "Shopee" },
  "Tiktok Shop": { color: "#22a383", short: "TikTok Shop" },
};
const STACK_ORDER = ["Mercado Livre", "Amazon", "Shopee", "Tiktok Shop"];
const chColor = (m: string) => CHANNEL[m]?.color ?? "#958c7b";
const chName = (m: string) => CHANNEL[m]?.short ?? m;

const RELOAD_EVERY_MS = 6 * 60 * 60 * 1000;
const FEED_ROWS = 3;
const MONTHS_ABBR = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];

const params = new URLSearchParams(window.location.search);
const key = params.get("key");
const noStream = params.has("nostream");
const withKey = (path: string) => (key ? `${path}?key=${encodeURIComponent(key)}` : path);
const intBR = (n: number | null | undefined) => (n === null || n === undefined ? "—" : n.toLocaleString("pt-BR"));
const roas = (x100: number | null) =>
  x100 === null ? "—" : `${(x100 / 100).toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 })}x`;

function useScale() {
  const [box, setBox] = useState({ scale: 1, x: 0, y: 0 });
  useLayoutEffect(() => {
    const fit = () => {
      const scale = Math.min(window.innerWidth / 1920, window.innerHeight / 1080);
      setBox({ scale, x: (window.innerWidth - 1920 * scale) / 2, y: (window.innerHeight - 1080 * scale) / 2 });
    };
    fit();
    window.addEventListener("resize", fit);
    return () => window.removeEventListener("resize", fit);
  }, []);
  return box;
}

function useNow(intervalMs: number) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = window.setInterval(() => setNow(Date.now()), intervalMs);
    return () => window.clearInterval(t);
  }, [intervalMs]);
  return now;
}

export default function TvPage() {
  const box = useScale();
  const now = useNow(10_000);
  const [data, setData] = useState<Snapshot | null>(null);
  const [online, setOnline] = useState(true);
  const [unauthorized, setUnauthorized] = useState(false);
  const [newIds, setNewIds] = useState<Set<string>>(new Set());
  const seen = useRef<Set<string> | null>(null);
  const firstBuild = useRef<string | null>(null);
  const sounds = useSaleSounds(data?.settings.sound_enabled ?? true, (data?.settings.sound_volume ?? 80) / 100);
  const playRef = useRef(sounds.play);
  playRef.current = sounds.play;

  useEffect(() => {
    document.title = "Kavria · TV multicanal";
    const reload = window.setTimeout(() => window.location.reload(), RELOAD_EVERY_MS);
    let source: EventSource | null = null;

    const apply = (snap: Snapshot) => {
      if (firstBuild.current === null) firstBuild.current = snap.build;
      else if (snap.build !== firstBuild.current) {
        window.location.reload();
        return;
      }
      const ids = snap.feed.map((f) => f.order_id);
      if (seen.current === null) {
        seen.current = new Set(ids);
      } else {
        const fresh = ids.filter((id) => !seen.current!.has(id));
        fresh.forEach((id) => seen.current!.add(id));
        if (fresh.length) {
          setNewIds(new Set(fresh));
          window.setTimeout(() => setNewIds(new Set()), 7000);
          if (snap.settings.sound_enabled) {
            const vals = snap.feed.filter((f) => fresh.includes(f.order_id)).reverse().map((f) => f.bruto_c);
            playRef.current(vals.map((v) => soundFor(v, snap.settings.sound_threshold_c)));
          }
        }
      }
      setData(snap);
    };

    (async () => {
      const res = await fetch(withKey("/api/tv/snapshot"), { credentials: "same-origin" }).catch(() => null);
      if (res?.status === 401) {
        setUnauthorized(true);
        return;
      }
      if (res?.ok) apply(await res.json());
      if (noStream) return;
      source = new EventSource(withKey("/api/tv/stream"));
      source.addEventListener("snapshot", (e) => {
        setOnline(true);
        apply(JSON.parse((e as MessageEvent).data));
      });
      source.onopen = () => setOnline(true);
      source.onerror = () => setOnline(false);
    })();

    return () => {
      window.clearTimeout(reload);
      source?.close();
    };
  }, []);

  return (
    <div className="tv-root">
      {unauthorized ? (
        <div className="tv-message">
          <img src={logoUrl} alt="Kavria" style={{ height: 80 }} />
          Chave da TV inválida ou ausente.
          <span style={{ fontSize: 22, color: "var(--muted)" }}>Abra o endereço com ?key=… (TV_ACCESS_KEY do .env).</span>
        </div>
      ) : !data ? (
        <div className="tv-message"><img src={logoUrl} alt="Kavria" style={{ height: 80 }} />Carregando…</div>
      ) : (
        <div className="tv-canvas" style={{ transform: `translate(${box.x}px, ${box.y}px) scale(${box.scale})` }}>
          <Header data={data} online={online} now={now} soundBlocked={sounds.blocked && data.settings.sound_enabled} />
          <div className="tv-kpis">
            <MonthCard data={data} />
            <TodayCard data={data} />
            <MarginCard data={data} />
            <AdsCard data={data} />
          </div>
          <div className="v2-bottom">
            <div className="v2-mid">
              <ChannelsCard data={data} />
              <DailyCard data={data} />
            </div>
            <div className="v2-low">
              <Feed data={data} newIds={newIds} />
              <TopProducts data={data} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function monthTitle(monthKey: string) {
  const [y, m] = monthKey.split("-").map(Number);
  const name = new Date(y, m - 1, 1).toLocaleDateString("pt-BR", { month: "long" });
  return `${name.charAt(0).toUpperCase()}${name.slice(1)} ${y}`;
}

function toneOf(bp: number | null, s: Snapshot["settings"]) {
  const tone = marginTone(bp, s.margin_green_bp, s.margin_yellow_bp);
  return {
    color: { green: "var(--good)", yellow: "var(--warn)", red: "var(--crit)", none: "var(--muted)" }[tone],
    label: { green: "✓ Saudável", yellow: "! Atenção", red: "✕ Crítica", none: "Sem dados" }[tone],
  };
}

function syncLevel(data: Snapshot, online: boolean, now: number) {
  const s = data.status;
  const age = ago(s.last_sync_at, now);
  if (!online) return { color: "var(--crit)", text: "Sem conexão com o servidor" };
  if (!s.account_connected) return { color: "var(--crit)", text: "Jodda não configurada" };
  if (s.reauth_required) return { color: "var(--crit)", text: "Chave da Jodda recusada" };
  if (age.seconds > 1800 || s.consecutive_errors >= 5) return { color: "var(--crit)", text: `Sem resposta da Jodda · ${age.text}` };
  if (age.seconds > 600 || s.consecutive_errors > 0) return { color: "var(--warn)", text: `Sincronização atrasada · ${age.text}` };
  return { color: "var(--good)", text: `Sincronizado ${age.text}` };
}

function Header({ data, online, now, soundBlocked }: { data: Snapshot; online: boolean; now: number; soundBlocked: boolean }) {
  const level = syncLevel(data, online, now);
  const date = new Date(now);
  return (
    <div className="tv-header">
      <div className="tv-header-left">
        <div style={{ flex: "none" }}>
          <div className="tv-month">{monthTitle(data.month)}</div>
        </div>
        <div className="tv-alerts">
          <span className="v2-tag">Multicanal</span>
          {soundBlocked && <span className="tv-pill tv-pill-warn">🔇 Som: aperte OK no controle</span>}
        </div>
      </div>
      <img className="tv-logo" src={logoUrl} alt="Kavria" />
      <div className="tv-header-right">
        <span className="tv-status"><span className="tv-dot" style={{ background: level.color }} />{level.text}</span>
        <div>
          <div className="tv-clock">{clock(date)}</div>
          <div className="tv-date">{longDate(date)}</div>
        </div>
      </div>
    </div>
  );
}

function MonthCard({ data }: { data: Snapshot }) {
  const t = data.totals;
  const g = data.goal;
  return (
    <div className="tv-card tv-hero">
      <GoalRing pctBp={g.goal_c ? g.atingido_bp : null} />
      <div style={{ minWidth: 0 }}>
        <div className="tv-label">Faturamento do mês · 4 canais</div>
        <div key={t.faturamento_c} className="tv-hero-value tv-flash">{brl(t.faturamento_c)}</div>
        <div className="tv-hero-goal">{g.goal_c ? <>meta {brl(g.goal_c)}</> : "meta não definida"}</div>
        <div className="tv-pair" style={{ marginTop: 16 }}>
          <div>
            <div className="tv-label-sm">Projeção</div>
            <div className="tv-stat-value">{brl(g.projecao_c)}</div>
            <div className="tv-stat-note" style={g.projecao_bp !== null && g.projecao_bp >= 10000 ? { color: "var(--good)", fontWeight: 600 } : undefined}>
              {g.projecao_bp !== null ? `${g.projecao_bp >= 10000 ? "✓ " : ""}${pctTv(g.projecao_bp, 0)} da meta` : "previsão da Jodda"}
            </div>
          </div>
          <div>
            <div className="tv-label-sm">Falta por dia</div>
            <div className="tv-stat-value">{g.falta_por_dia_c === null ? "—" : g.falta_por_dia_c === 0 ? "Batida!" : brl(g.falta_por_dia_c)}</div>
            <div className="tv-stat-note">{g.dias_restantes ? `${g.dias_restantes} dias, com hoje` : ""}</div>
          </div>
        </div>
      </div>
    </div>
  );
}

function TodayCard({ data }: { data: Snapshot }) {
  const h = data.hoje;
  const tone = toneOf(h.margem_bp, data.settings);
  return (
    <div className="tv-card">
      <div className="tv-label">Hoje · faturamento</div>
      <div key={h.bruto_c} className="tv-today-value tv-flash">{brl(h.bruto_c)}</div>
      <div className="tv-pair" style={{ marginTop: 22 }}>
        <div><div className="tv-label-sm">Pedidos</div><div className="tv-stat-value">{intBR(h.vendas)}</div></div>
        <div><div className="tv-label-sm">Ticket médio</div><div className="tv-stat-value">{brl(h.ticket_medio_c)}</div></div>
        <div><div className="tv-label-sm">Lucro</div><div className="tv-stat-value">{brl(h.lucro_c)}</div></div>
        <div><div className="tv-label-sm">Margem do dia</div><div className="tv-stat-value" style={{ color: tone.color }}>{pctTv(h.margem_bp)}</div></div>
      </div>
    </div>
  );
}

function MarginCard({ data }: { data: Snapshot }) {
  const t = data.totals;
  const tone = toneOf(t.margem_bp, data.settings);
  return (
    <div className="tv-card">
      <div className="tv-label">Margem líquida · mês</div>
      <div className="tv-margin-row">
        <div className="tv-margin-value" style={{ color: tone.color }}>{pctTv(t.margem_bp)}</div>
        <div className="tv-margin-side">
          <div className="tv-chip" style={{ color: tone.color }}>{tone.label}</div>
          {t.margem_pos_ads_bp !== null && (
            <div className="tv-margin-ads">com Ads <b style={{ color: toneOf(t.margem_pos_ads_bp, data.settings).color }}>{pctTv(t.margem_pos_ads_bp)}</b></div>
          )}
        </div>
      </div>
      <div className="tv-pair" style={{ marginTop: 16 }}>
        <div><div className="tv-label-sm">Lucro com Ads</div><div className="tv-stat-value">{brl(t.lucro_c)}</div></div>
        <div><div className="tv-label-sm">Pedidos no mês</div><div className="tv-stat-value">{intBR(t.pedidos)}</div></div>
      </div>
    </div>
  );
}

function AdsCard({ data }: { data: Snapshot }) {
  const a = data.ads;
  return (
    <div className="tv-card">
      <div className="tv-label">Ads · mês</div>
      {!a.disponivel ? <div className="tv-note" style={{ marginTop: 18 }}>Sincronizando Ads…</div> : (
        <>
          <div className="tv-label-sm" style={{ marginTop: 14 }}>Investimento</div>
          <div className="tv-big-value">{brl(a.investimento_c)}</div>
          <div className="tv-pair" style={{ marginTop: 18 }}>
            <div><div className="tv-label-sm">TACOS</div><div className="tv-stat-value">{pctTv(a.tacos_bp)}</div></div>
            <div><div className="tv-label-sm">ROAS</div><div className="tv-stat-value">{roas(a.roas_x100)}</div></div>
          </div>
          <div className="tv-note">{a.por_canal.length ? a.por_canal.map((c) => `${chName(c.marketplace)} ${brl(c.gasto_c)}`).join(" · ") : "sem gasto no mês"}</div>
        </>
      )}
    </div>
  );
}

function ChannelsCard({ data }: { data: Snapshot }) {
  const rows = [...data.channels].sort((a, b) => b.faturamento_c - a.faturamento_c);
  return (
    <div className="tv-card">
      <div className="tv-card-head"><div className="tv-label">Canais · mês</div><div className="tv-legend-note">lucro e margem antes do Ads</div></div>
      <div className="v2-channels">
        {rows.map((c) => (
          <div key={c.marketplace} className="v2-channel" style={{ ["--ch" as string]: chColor(c.marketplace) }}>
            <div className="v2-ch-name"><span className="v2-ch-dot" />{chName(c.marketplace)}</div>
            <div className="v2-ch-value">{brl(c.faturamento_c)}</div>
            <div className="v2-ch-bar"><div style={{ width: `${Math.min(100, (c.participacao_bp ?? 0) / 100)}%` }} /></div>
            <div className="v2-ch-share">{pctTv(c.participacao_bp, 1)} do faturamento</div>
            <div className="v2-ch-stats">
              <div><span>Pedidos</span><b>{intBR(c.pedidos)}</b></div>
              <div><span>Margem</span><b>{pctTv(c.margem_bp)}</b></div>
              <div><span>Hoje</span><b>{brl(c.hoje_c)}</b></div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function rollingAxis(days: string[], minGap = 2) {
  const n = days.length;
  const meta = days.map((iso) => {
    const d = new Date(`${iso}T12:00:00`);
    return { day: d.getDate(), month: d.getMonth(), sunday: d.getDay() === 0 };
  });
  const candidates: { i: number; text: string; priority: number }[] = [];
  meta.forEach((m, i) => {
    if (i === n - 1) candidates.push({ i, text: "hoje", priority: 4 });
    else if (m.day === 1) candidates.push({ i, text: `1 ${MONTHS_ABBR[m.month]}`, priority: 3 });
    else if (i === 0) candidates.push({ i, text: `${m.day} ${MONTHS_ABBR[m.month]}`, priority: 2 });
    else if (m.sunday) candidates.push({ i, text: `dom ${m.day}`, priority: 1 });
  });
  const labels: (string | null)[] = days.map(() => null);
  [...candidates].sort((a, b) => b.priority - a.priority).forEach((c) => {
    if (!labels.some((l, j) => l !== null && Math.abs(j - c.i) <= minGap)) labels[c.i] = c.text;
  });
  const guides: Guide[] = meta.flatMap((m, i) => (m.day === 1 ? [{ index: i, strong: true }] : m.sunday ? [{ index: i }] : []));
  return { labels, guides, current: n - 1 };
}

function DailyCard({ data }: { data: Snapshot }) {
  const rows = data.rolling;
  const axis = rollingAxis(rows.map((r) => r.day));
  const present = STACK_ORDER.filter((m) => rows.some((r) => (r.por_canal[m] ?? 0) > 0));
  return (
    <div className="tv-card">
      <div className="tv-card-head">
        <div className="tv-label">Por dia · últimos {rows.length} dias</div>
        <div className="tv-legend">
          {present.map((m) => (
            <span key={m} className="tv-legend-item"><svg width="14" height="14"><rect width="14" height="14" rx="3" fill={chColor(m)} /></svg>{chName(m)}</span>
          ))}
          <span className="tv-legend-item"><svg width="24" height="14"><line x1="0" x2="24" y1="7" y2="7" stroke="#fff" strokeWidth="2.5" /></svg>Lucro</span>
        </div>
      </div>
      <StackedBarChart days={rows.map((r) => r.day)} series={STACK_ORDER.map((m) => ({ key: m, color: chColor(m) }))}
        values={rows.map((r) => r.por_canal)} line={rows.map((r) => (r.total_c ? r.lucro_c : null))}
        labels={axis.labels} currentIndex={axis.current} guides={axis.guides} width={DAILY_W} height={250} />
    </div>
  );
}
const DAILY_W = 860 - 44;

function Feed({ data, newIds }: { data: Snapshot; newIds: Set<string> }) {
  const rows = data.feed.slice(0, FEED_ROWS);
  return (
    <div className="tv-card">
      <div className="tv-label">Últimas vendas</div>
      <div className="tv-feed">
        {rows.length === 0 && <div className="tv-empty">Nenhuma venda ainda</div>}
        {rows.map((f) => (
          <div key={f.order_id} className={`tv-feed-row v2-feed-row${newIds.has(f.order_id) ? " is-new" : ""}`}>
            <span className="tv-feed-time">{hhmm(f.ts)}</span>
            <span className="v2-badge" style={{ ["--ch" as string]: chColor(f.marketplace) }}>{chName(f.marketplace)}</span>
            <div style={{ minWidth: 0 }}>
              <div className="tv-feed-title tv-truncate">{f.title ?? f.sku}</div>
              <div className="tv-feed-meta tv-truncate">{f.qtd > 1 ? `${f.qtd} un · ` : ""}{f.sku}</div>
            </div>
            <div className="tv-feed-values">
              <div className="tv-feed-value">{brlCents(f.bruto_c)}</div>
              <div className="tv-feed-profit">lucro {brlCents(f.lucro_c)}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function TopProducts({ data }: { data: Snapshot }) {
  const rows = data.top_produtos.slice(0, 4);
  const max = Math.max(1, ...rows.map((r) => r.faturamento));
  return (
    <div className="tv-card">
      <div className="tv-label">Mais vendidos · mês</div>
      <div className="v2-top">
        {rows.length === 0 && <div className="tv-empty">Sem dados ainda</div>}
        {rows.map((p, i) => (
          <div key={p.sku} className="v2-top-row">
            <span className="v2-top-rank">{i + 1}</span>
            <div style={{ minWidth: 0 }}>
              <div className="tv-truncate v2-top-name">{p.descricao}</div>
              <div className="v2-top-bar"><div style={{ width: `${(p.faturamento / max) * 100}%` }} /></div>
            </div>
            <div className="v2-top-values">
              <div>{brl(Math.round(p.faturamento * 100))}</div>
              <span>{intBR(p.unidades)} un · {p.margem_pct === null ? "—" : `${p.margem_pct.toLocaleString("pt-BR", { maximumFractionDigits: 1 })}%`}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
