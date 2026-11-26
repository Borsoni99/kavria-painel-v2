const reais = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 });
const centavos = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

/** Valores grandes na TV: sem centavos ("R$ 15.285"). */
export const brl = (c: number | null | undefined) => (c === null || c === undefined ? "—" : reais.format(c / 100));

/** Valores de uma venda: com centavos ("R$ 65,55"). */
export const brlCents = (c: number | null | undefined) => (c === null || c === undefined ? "—" : centavos.format(c / 100));

/** Eixo do gráfico: "R$ 2 mil", "R$ 1,5 mil", "R$ 800". */
export function brlAxis(c: number): string {
  const v = c / 100;
  if (Math.abs(v) >= 1000) {
    const k = v / 1000;
    return `R$ ${k.toLocaleString("pt-BR", { maximumFractionDigits: Number.isInteger(k) ? 0 : 1 })} mil`;
  }
  return `R$ ${Math.round(v)}`;
}

export const pctTv = (bp: number | null | undefined, digits = 1) =>
  bp === null || bp === undefined
    ? "—"
    : `${(bp / 100).toLocaleString("pt-BR", { minimumFractionDigits: digits, maximumFractionDigits: digits })}%`;

const TZ = "America/Sao_Paulo";
export const clock = (d: Date) => d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit", timeZone: TZ });
export const longDate = (d: Date) =>
  d.toLocaleDateString("pt-BR", { weekday: "long", day: "numeric", month: "long", timeZone: TZ });
export const hhmm = (iso: string) =>
  new Date(iso).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit", timeZone: TZ });

export function ago(iso: string | null, now: number): { text: string; seconds: number } {
  if (!iso) return { text: "nunca", seconds: Infinity };
  const s = Math.max(0, Math.round((now - Date.parse(iso)) / 1000));
  if (s < 60) return { text: `há ${s} s`, seconds: s };
  const m = Math.round(s / 60);
  if (m < 60) return { text: `há ${m} min`, seconds: s };
  return { text: `há ${Math.round(m / 60)} h`, seconds: s };
}

export const LOGISTIC: Record<string, string> = {
  fulfillment: "Full", self_service: "Flex", xd_drop_off: "Agência", cross_docking: "Coleta", drop_off: "Correios",
};
