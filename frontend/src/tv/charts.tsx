import { brl, brlAxis } from "./fmt";

/*
 * Gráficos SVG próprios (leves para o Fire TV). Regras seguidas:
 * - um único eixo de valores por gráfico (nunca eixo duplo): visitas e vendas, de escalas muito diferentes,
 *   ficam em gráficos separados, cada um com a própria régua; a conversão entra como rótulo seletivo;
 * - colunas ≤ 24 px com ponta arredondada de 4 px e base reta; linhas de 3 px (TV a 3–4 m);
 * - grade em linha fina e discreta; domingos marcados com uma linha vertical fina;
 * - rótulo direto só no ponto atual; texto nunca usa a cor da série.
 */

function niceStep(raw: number): number {
  const pow = 10 ** Math.floor(Math.log10(Math.max(raw, 1e-9)));
  const n = raw / pow;
  return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 2.5 ? 2.5 : n <= 5 ? 5 : 10) * pow;
}

function scale(minV: number, maxV: number, ticksWanted = 3) {
  const step = niceStep((maxV - minV) / ticksWanted || 1);
  const lo = Math.floor(minV / step) * step;
  const hi = Math.max(Math.ceil(maxV / step) * step, lo + step);
  const ticks: number[] = [];
  for (let v = lo; v <= hi + step / 2; v += step) ticks.push(v);
  return { lo, hi, ticks };
}

export type Guide = { index: number; strong?: boolean };

/** Anel de progresso da meta (medidor de uma série só: preenchimento dourado sobre trilha do mesmo tom). */
export function GoalRing({ pctBp, size = 210 }: { pctBp: number | null; size?: number }) {
  const stroke = 20;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const frac = Math.max(0, Math.min(1, (pctBp ?? 0) / 10000));
  const achieved = pctBp !== null && pctBp >= 10000;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ flex: "none" }} aria-hidden>
      <defs>
        <linearGradient id="tv-gold" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#f0d070" />
          <stop offset="100%" stopColor="#c08a1e" />
        </linearGradient>
      </defs>
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--gold-track)" strokeWidth={stroke} />
      {frac > 0 && (
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="url(#tv-gold)" strokeWidth={stroke}
          strokeLinecap="round" strokeDasharray={`${c * frac} ${c}`} transform={`rotate(-90 ${size / 2} ${size / 2})`} />
      )}
      <text x="50%" y="47%" textAnchor="middle" dominantBaseline="middle" fill={achieved ? "var(--good)" : "var(--ink)"}
        style={{ fontSize: 50, fontWeight: 700 }}>
        {pctBp === null ? "—" : `${Math.round(pctBp / 100)}%`}
      </text>
      <text x="50%" y="66%" textAnchor="middle" fill={achieved ? "var(--good)" : "var(--muted)"}
        style={{ fontSize: 17, letterSpacing: "0.08em", fontWeight: achieved ? 700 : 400 }}>
        {achieved ? "✓ META BATIDA" : "DA META"}
      </text>
    </svg>
  );
}

function GuideLines({ guides, x, top, bottom }: { guides: Guide[]; x: (i: number) => number; top: number; bottom: number }) {
  return (
    <>
      {guides.map((g) => (
        <line key={`g${g.index}`} x1={x(g.index)} x2={x(g.index)} y1={top} y2={bottom}
          stroke={g.strong ? "var(--axis)" : "var(--guide)"} strokeWidth={1} />
      ))}
    </>
  );
}

function XLabels({ labels, x, y, current }: { labels: (string | null)[]; x: (i: number) => number; y: number; current: number }) {
  return (
    <>
      {labels.map((label, i) => label && (
        <text key={`x${i}`} x={x(i)} y={y} textAnchor="middle" fill={i === current ? "var(--gold-hi)" : "var(--muted)"}
          style={{ fontSize: 16, fontWeight: i === current ? 700 : 400 }}>{label}</text>
      ))}
    </>
  );
}

export type BarPoint = { key: string; bar: number; line: number | null };

/** Colunas de faturamento + linha de lucro no mesmo eixo em R$. */
export function BarLineChart({ points, labels, currentIndex, refLine, width, height, guides = [], directLabel = true, highlights = [] }: {
  points: BarPoint[];
  labels: (string | null)[];
  currentIndex: number;
  refLine?: number | null;
  width: number;
  height: number;
  guides?: Guide[];
  /** Valor escrito ao lado da coluna atual (desligar quando o número já aparece em outro card). */
  directLabel?: boolean;
  /** Colunas em destaque (ex.: dias de ofertas 9/9, 10/10): rótulo acima da coluna. */
  highlights?: { index: number; text: string }[];
}) {
  const m = { l: 84, r: 12, t: 26, b: 30 };
  const iw = width - m.l - m.r;
  const ih = height - m.t - m.b;
  const values = points.flatMap((p) => [p.bar, p.line ?? 0]);
  const { lo, hi, ticks } = scale(Math.min(0, ...values), Math.max(1, refLine ?? 0, ...values));
  const y = (v: number) => m.t + ih - ((v - lo) / (hi - lo)) * ih;
  const slot = iw / points.length;
  const bw = Math.min(24, slot * 0.62);
  const cx = (i: number) => m.l + i * slot + slot / 2;
  const base = y(0);

  const bar = (i: number, v: number) => {
    const top = y(Math.max(v, 0));
    const h = base - top;
    if (h <= 0.5) return "";
    const x = cx(i) - bw / 2;
    const r = Math.min(4, h, bw / 2);
    return `M${x},${base} V${top + r} Q${x},${top} ${x + r},${top} H${x + bw - r} Q${x + bw},${top} ${x + bw},${top + r} V${base} Z`;
  };
  const linePts = points.map((p, i) => (p.line === null ? null : `${cx(i)},${y(p.line)}`)).filter(Boolean).join(" ");
  const cur = points[currentIndex];
  const labelRight = currentIndex < points.length - 3;

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} style={{ display: "block" }}>
      {ticks.map((t) => (
        <g key={t}>
          <line x1={m.l} x2={width - m.r} y1={y(t)} y2={y(t)} stroke={t === 0 ? "var(--axis)" : "var(--grid)"} strokeWidth={1} />
          <text x={m.l - 12} y={y(t)} textAnchor="end" dominantBaseline="middle" fill="var(--muted)"
            style={{ fontSize: 16, fontVariantNumeric: "tabular-nums" }}>{brlAxis(t)}</text>
        </g>
      ))}
      <GuideLines guides={guides} x={cx} top={m.t} bottom={base} />
      {points.map((p, i) => <path key={p.key} d={bar(i, p.bar)} fill={i === currentIndex ? "var(--gold)" : "var(--gold-series)"} />)}
      {refLine ? (
        <line x1={m.l} x2={width - m.r} y1={y(refLine)} y2={y(refLine)} stroke="var(--ink-2)" strokeWidth={1.5}
          strokeDasharray="6 6" opacity={0.7} />
      ) : null}
      {points.filter((p) => p.line !== null).length > 1 && (
        <polyline points={linePts} fill="none" stroke="var(--blue)" strokeWidth={3} strokeLinejoin="round" strokeLinecap="round" />
      )}
      {cur && (
        <>
          {cur.line !== null && <circle cx={cx(currentIndex)} cy={y(cur.line)} r={6} fill="var(--blue)" stroke="var(--card)" strokeWidth={2} />}
          {directLabel && (
            <text x={labelRight ? cx(currentIndex) + bw / 2 + 8 : cx(currentIndex) - bw / 2 - 8} y={y(Math.max(cur.bar, 0)) - 4}
              textAnchor={labelRight ? "start" : "end"} fill="var(--ink)" stroke="var(--card)" strokeWidth={5}
              paintOrder="stroke" style={{ fontSize: 18, fontWeight: 600 }}>{brl(cur.bar)}</text>
          )}
        </>
      )}
      {highlights.map((h) => {
        const top = points[h.index] ? y(Math.max(points[h.index].bar, 0)) : base;
        return (
          <text key={`ht${h.index}`} x={cx(h.index)} y={Math.max(top - 8, 16)} textAnchor="middle" fill="var(--spike)"
            stroke="var(--card)" strokeWidth={4} paintOrder="stroke" style={{ fontSize: 15, fontWeight: 700 }}>{h.text}</text>
        );
      })}
      <XLabels labels={labels} x={cx} y={height - 7} current={currentIndex} />
    </svg>
  );
}

type Extreme = { i: number; kind: "peak" | "valley" };

/**
 * Picos e vales "relevantes" de uma série: extremos locais numa janela de ±2 dias, ordenados
 * pela proeminência e espaçados entre si — rótulo seletivo, nunca um número em cada ponto.
 */
function pickExtremes(values: (number | null)[], opts: { skipTail: number; minGap: number; max: number }): Extreme[] {
  const n = values.length;
  const cands: (Extreme & { score: number })[] = [];
  for (let i = 1; i < n - opts.skipTail; i++) {
    const v = values[i];
    if (v === null) continue;
    const around = [-2, -1, 1, 2].map((d) => values[i + d]).filter((x): x is number => x !== null && x !== undefined);
    if (!around.length) continue;
    const mean = around.reduce((a, b) => a + b, 0) / around.length;
    if (v >= Math.max(...around) && v > Math.min(...around)) cands.push({ i, kind: "peak", score: v - mean });
    else if (v <= Math.min(...around) && v < Math.max(...around)) cands.push({ i, kind: "valley", score: mean - v });
  }
  const chosen: Extreme[] = [];
  cands.sort((a, b) => b.score - a.score).forEach((c) => {
    if (chosen.length >= opts.max) return;
    // Só afasta rótulos do mesmo lado: o de pico fica acima da linha e o de vale abaixo
    if (chosen.some((e) => e.kind === c.kind && Math.abs(e.i - c.i) < opts.minGap)) return;
    if (chosen.some((e) => Math.abs(e.i - c.i) < 1)) return;
    chosen.push({ i: c.i, kind: c.kind });
  });
  return chosen;
}

/**
 * Uma série por dia (visitas, conversão…) com régua própria a partir de zero, área suave e o valor de
 * hoje escrito na ponta. `format` formata eixo e ponta; `peakLabel` escreve um texto nos picos e vales
 * relevantes (ex.: a quantidade de vendas na linha de conversão).
 */
export function CountLineChart({ values, labels, guides, width, height, color, peakLabel, format, refLine }: {
  values: (number | null)[];
  labels: (string | null)[];
  guides: Guide[];
  width: number;
  height: number;
  color: string;
  peakLabel?: (i: number) => string | null;
  format?: (v: number) => string;
  /** Linha tracejada de referência (ex.: média do período). */
  refLine?: number | null;
}) {
  const m = { l: 62, r: 56, t: 24, b: 30 };
  const iw = width - m.l - m.r;
  const ih = height - m.t - m.b;
  const n = values.length;
  const last = n - 1;
  const x = (i: number) => m.l + (n <= 1 ? iw / 2 : (i / (n - 1)) * iw);
  const defined = values.filter((v): v is number => v !== null);
  const { lo, hi, ticks } = scale(0, Math.max(1, refLine ?? 0, ...defined), 3);
  const y = (v: number) => m.t + ih - ((v - lo) / (hi - lo)) * ih;
  const base = y(0);
  const int = format ?? ((v: number) => Math.round(v).toLocaleString("pt-BR"));

  const pts = values.map((v, i) => (v === null ? null : { i, v })).filter(Boolean) as { i: number; v: number }[];
  const line = pts.map((p) => `${x(p.i)},${y(p.v)}`).join(" ");
  const area = pts.length > 1
    ? `M${x(pts[0].i)},${base} L${pts.map((p) => `${x(p.i)},${y(p.v)}`).join(" L")} L${x(pts[pts.length - 1].i)},${base} Z`
    : "";
  const end = pts[pts.length - 1];
  const marks = peakLabel
    ? pickExtremes(values, { skipTail: 1, minGap: 2, max: 6 }).map((e) => ({ ...e, text: peakLabel(e.i) }))
      .filter((e) => e.text !== null)
    : [];

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} style={{ display: "block" }}>
      {ticks.map((t) => (
        <g key={t}>
          <line x1={m.l} x2={width - m.r} y1={y(t)} y2={y(t)} stroke={t === 0 ? "var(--axis)" : "var(--grid)"} strokeWidth={1} />
          <text x={m.l - 12} y={y(t)} textAnchor="end" dominantBaseline="middle" fill="var(--muted)"
            style={{ fontSize: 15, fontVariantNumeric: "tabular-nums" }}>{int(t)}</text>
        </g>
      ))}
      <GuideLines guides={guides} x={x} top={m.t} bottom={base} />
      {area && <path d={area} fill={color} opacity={0.12} />}
      {refLine ? (
        <line x1={m.l} x2={width - m.r} y1={y(refLine)} y2={y(refLine)} stroke="var(--ink-2)" strokeWidth={1.5}
          strokeDasharray="6 6" opacity={0.7} />
      ) : null}
      {pts.length > 1 && <polyline points={line} fill="none" stroke={color} strokeWidth={3} strokeLinejoin="round" strokeLinecap="round" />}
      {marks.map((e) => {
        const py = y(values[e.i]!);
        const below = e.kind === "valley" && py + 22 < base - 2;
        return (
          <g key={`e${e.i}`}>
            <circle cx={x(e.i)} cy={py} r={4} fill={color} stroke="var(--card)" strokeWidth={2} />
            <text x={x(e.i)} y={below ? py + 20 : py - 11} textAnchor="middle" fill="var(--ink-2)" stroke="var(--card)"
              strokeWidth={4} paintOrder="stroke" style={{ fontSize: 15, fontWeight: 600 }}>{e.text}</text>
          </g>
        );
      })}
      {end && end.i === last && (
        <>
          <circle cx={x(last)} cy={y(end.v)} r={6} fill={color} stroke="var(--card)" strokeWidth={2} />
          <text x={x(last) + 11} y={y(end.v)} dominantBaseline="middle" fill="var(--ink)" stroke="var(--card)" strokeWidth={5}
            paintOrder="stroke" style={{ fontSize: 17, fontWeight: 600 }}>{int(end.v)}</text>
        </>
      )}
      <XLabels labels={labels} x={x} y={height - 7} current={last} />
    </svg>
  );
}

export type StackSeries = { key: string; color: string };

/**
 * Barras empilhadas por canal (mesma escala em R$), com 2 px de folga entre os segmentos e o topo
 * arredondado; linha opcional (ex.: lucro total) na MESMA escala — nunca um segundo eixo.
 */
export function StackedBarChart({ days, series, values, line, labels, currentIndex, guides = [], width, height, refLine }: {
  days: string[];
  series: StackSeries[];
  values: Record<string, number>[];
  line?: (number | null)[];
  labels: (string | null)[];
  currentIndex: number;
  guides?: Guide[];
  width: number;
  height: number;
  refLine?: number | null;
}) {
  const m = { l: 84, r: 12, t: 20, b: 30 };
  const iw = width - m.l - m.r;
  const ih = height - m.t - m.b;
  const totals = values.map((v) => series.reduce((s, sr) => s + (v[sr.key] ?? 0), 0));
  const { lo, hi, ticks } = scale(0, Math.max(1, refLine ?? 0, ...totals, ...(line ?? []).map((x) => x ?? 0)));
  const y = (v: number) => m.t + ih - ((v - lo) / (hi - lo)) * ih;
  const slot = iw / Math.max(days.length, 1);
  const bw = Math.min(24, slot * 0.62);
  const cx = (i: number) => m.l + i * slot + slot / 2;
  const base = y(0);
  const linePts = (line ?? []).map((v, i) => (v === null ? null : `${cx(i)},${y(v)}`)).filter(Boolean).join(" ");

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} style={{ display: "block" }}>
      {ticks.map((t) => (
        <g key={t}>
          <line x1={m.l} x2={width - m.r} y1={y(t)} y2={y(t)} stroke={t === 0 ? "var(--axis)" : "var(--grid)"} strokeWidth={1} />
          <text x={m.l - 12} y={y(t)} textAnchor="end" dominantBaseline="middle" fill="var(--muted)"
            style={{ fontSize: 16, fontVariantNumeric: "tabular-nums" }}>{brlAxis(t)}</text>
        </g>
      ))}
      <GuideLines guides={guides} x={cx} top={m.t} bottom={base} />
      {values.map((v, i) => {
        let acc = 0;
        const segs = series.filter((s) => (v[s.key] ?? 0) > 0);
        return (
          <g key={days[i]} opacity={i === currentIndex ? 1 : 0.92}>
            {segs.map((s, k) => {
              const val = v[s.key];
              const yTop = y(acc + val);
              const yBot = y(acc) - (k > 0 ? 2 : 0); // folga de 2 px entre segmentos
              acc += val;
              const h = yBot - yTop;
              if (h <= 0.5) return null;
              const x = cx(i) - bw / 2;
              const isTop = k === segs.length - 1;
              const r = isTop ? Math.min(4, h, bw / 2) : 0;
              const d = r
                ? `M${x},${yBot} V${yTop + r} Q${x},${yTop} ${x + r},${yTop} H${x + bw - r} Q${x + bw},${yTop} ${x + bw},${yTop + r} V${yBot} Z`
                : `M${x},${yBot} V${yTop} H${x + bw} V${yBot} Z`;
              return <path key={s.key} d={d} fill={s.color} />;
            })}
          </g>
        );
      })}
      {refLine ? (
        <line x1={m.l} x2={width - m.r} y1={y(refLine)} y2={y(refLine)} stroke="var(--ink-2)" strokeWidth={1.5} strokeDasharray="6 6" opacity={0.7} />
      ) : null}
      {line && (line.filter((v) => v !== null).length > 1) && (
        <polyline points={linePts} fill="none" stroke="var(--ink)" strokeWidth={2.5} strokeLinejoin="round" strokeLinecap="round" opacity={0.85} />
      )}
      <XLabels labels={labels} x={cx} y={height - 7} current={currentIndex} />
    </svg>
  );
}
