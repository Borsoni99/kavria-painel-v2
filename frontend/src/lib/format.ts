const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
const num = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

/** Centavos → "R$ 1.234,56" (ou "—" se ausente). */
export function money(cents: number | null | undefined): string {
  return cents === null || cents === undefined ? "—" : brl.format(cents / 100);
}

/** Centavos → "1234,56" para preencher campos de edição. */
export function moneyInput(cents: number | null | undefined): string {
  return cents === null || cents === undefined ? "" : num.format(cents / 100).replace(/\./g, "");
}

/** Pontos-base → "18,4%". */
export function pct(bp: number | null | undefined, digits = 1): string {
  if (bp === null || bp === undefined) return "—";
  return `${(bp / 100).toLocaleString("pt-BR", { minimumFractionDigits: digits, maximumFractionDigits: digits })}%`;
}

export function dateBR(iso: string | null | undefined): string {
  if (!iso) return "—";
  const [y, m, d] = iso.slice(0, 10).split("-");
  return `${d}/${m}/${y}`;
}

export function monthLabel(key: string): string {
  const [y, m] = key.split("-").map(Number);
  const name = new Date(y, m - 1, 1).toLocaleDateString("pt-BR", { month: "long" });
  return `${name.charAt(0).toUpperCase()}${name.slice(1)} ${y}`;
}

export function currentMonthKey(offset = 0): string {
  const now = new Date();
  const d = new Date(now.getFullYear(), now.getMonth() + offset, 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

export type MarginTone = "green" | "yellow" | "red" | "none";

export function marginTone(bp: number | null | undefined, greenBp: number, yellowBp: number): MarginTone {
  if (bp === null || bp === undefined) return "none";
  if (bp >= greenBp) return "green";
  if (bp >= yellowBp) return "yellow";
  return "red";
}

export const toneText: Record<MarginTone, string> = {
  green: "text-emerald-400",
  yellow: "text-amber-300",
  red: "text-red-400",
  none: "text-slate-400",
};
