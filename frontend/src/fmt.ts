export const eur = (n: number | null | undefined) => {
  if (n == null) return "—";
  const r = Math.round(n);
  return (r < 0 ? "−" : "") + Math.abs(r).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ".") + " €";
};
export const kE = (v: number) => (v >= 1000 ? Math.round(v / 1000) + " k€" : eur(v));
export const pct = (x: number | null | undefined) => (x == null ? "—" : (Math.round(x * 1000) / 10).toFixed(1).replace(".", ",") + " %");
export const fd = (d: string | null | undefined) => (d ? `${d.slice(8, 10)}/${d.slice(5, 7)}/${d.slice(0, 4)}` : "");
export const fts = (ts: string) => `${fd(ts.slice(0, 10))} ${ts.slice(11, 16)}`;
export const ore = (h: number) => Math.round(h).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ".") + " h";
