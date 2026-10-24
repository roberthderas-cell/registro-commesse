import { useApp } from "../App";
import { eur, kE, ore, pct } from "../fmt";
import { useDati } from "../hooks";
import type { Avviso } from "../types";

interface DatiCruscotto {
  kpi: { portafoglio: number; n_attive: number; margine: number; marg_pct: number; da_fatturare: number; credito: number; wip: number; scaduto: number };
  flusso: { k: string; l: string; v: number; f: string; s: string; c: string }[];
  commesse: { cod: string; cliente: string; stato: number; ricavo: number; eac: number; fatturato: number; incassato: number; marg_pct: number }[];
  avvisi: Avviso[];
  incassi: { k: string; l: string; a: number; b: number }[];
}

const fmtF = (v: number, f: string) => (f === "int" ? String(v) : f === "h" ? ore(v) : eur(v));

export default function Cruscotto() {
  const { meta, apri, vai } = useApp();
  const { dati, errore } = useDati<DatiCruscotto>("/api/cruscotto");
  if (errore) return <div className="panel pad">{errore}</div>;
  if (!dati) return <div className="muted">Caricamento…</div>;
  const { kpi, flusso, commesse, avvisi, incassi } = dati;
  const fase = (s: number) => meta.fasi.find((f) => f.st.includes(s))!.v;
  const max = Math.max(1, ...commesse.map((c) => Math.max(c.ricavo, c.eac)));
  const maxI = Math.max(1, ...incassi.map((b) => b.a + b.b));
  const soglia = Number(meta.cfg.sogliaMarg) / 100;

  const K = (k: string, col: string, l: string, v: string, s: React.ReactNode) => (
    <div className="kpi" key={k} style={{ ["--kc" as string]: `var(${col})` }}>
      <div className="k-h"><span className="lbl">{l}</span></div>
      <div className="v">{v}</div>
      <div className="s">{s}</div>
      <span className="spark" />
    </div>
  );

  return (
    <div className="stack">
      <div className="hello"><div className="pgt"><h2>Cruscotto</h2><p>Portafoglio, margini, crediti e avvisi in un colpo d'occhio</p></div></div>
      <div className="kpis">
        {K("port", "--c-ricavo", "Portafoglio", eur(kpi.portafoglio), `${kpi.n_attive} commesse aperte`)}
        {K("marg", "--c-inc", "Margine previsto", pct(kpi.marg_pct), eur(kpi.margine) + " a finire")}
        {K("daf", "--ph-appr", "Maturato da fatturare", eur(Math.max(0, kpi.wip)), "lavoro fatto, non fatturato")}
        {K("resid", "--ph-prog", "Ancora da fatturare", eur(kpi.da_fatturare), "sul portafoglio aperto")}
        {K("cred", "--ph-cant", "Crediti aperti", eur(kpi.credito), kpi.scaduto ? <span className="neg">di cui scaduti {eur(kpi.scaduto)}</span> : "nessuno scaduto")}
      </div>

      <section className="panel pad">
        <div className="sec-h"><h2>Il ciclo delle commesse</h2><p className="muted">Dal contratto all'incasso, tutte le commesse</p></div>
        <div className="flow">
          {flusso.map((n) => (
            <button key={n.k} className="fnode" style={{ ["--kc" as string]: `var(${n.c})` }} onClick={() => vai("pipeline")}>
              <span className="fh"><span className="fdot" /><span className="lbl">{n.l}</span></span>
              <span className="fv">{fmtF(n.v, n.f)}</span>
              <span className="fs">{n.s}</span>
            </button>
          ))}
        </div>
      </section>

      <div className="dash">
        <div className="stack">
          <section className="panel pad">
            <div className="sec-h"><h2>Commesse a confronto</h2>
              <div className="legend">
                <span style={{ ["--c" as string]: "var(--c-ricavo)" }}><i />Ricavo</span>
                <span style={{ ["--c" as string]: "var(--c-costi)" }}><i />Costo a finire</span>
                <span style={{ ["--c" as string]: "var(--c-fatt)" }}><i />Fatturato</span>
                <span style={{ ["--c" as string]: "var(--c-inc)" }}><i />Incassato</span>
              </div>
            </div>
            <div className="cmp">
              {commesse.map((c) => (
                <button key={c.cod} className="cmp-r" onClick={() => apri(c.cod, "riepilogo")}>
                  <span className="cmp-n">
                    <b>{c.cod}</b><span>{c.cliente}</span>
                    <span><span className="pill ph" style={{ ["--pc" as string]: `var(${fase(c.stato)})`, marginTop: 4 }}>{meta.stati[c.stato]}</span></span>
                    <span className={c.marg_pct < soglia ? "neg" : "pos"} style={{ fontSize: 12 }}>margine {pct(c.marg_pct)}</span>
                  </span>
                  <span className="cmp-b">
                    {([["ricavo", "--c-ricavo"], ["eac", "--c-costi"], ["fatturato", "--c-fatt"], ["incassato", "--c-inc"]] as const).map(([k, col]) => (
                      <span className="hb" key={k}><i style={{ ["--c" as string]: `var(${col})`, width: `${Math.max(0.5, (c[k] / max) * 100)}%` }} /><span>{eur(c[k])}</span></span>
                    ))}
                  </span>
                </button>
              ))}
            </div>
          </section>

          <section className="panel pad">
            <div className="sec-h"><h2>Incassi attesi</h2>
              <div className="legend">
                <span style={{ ["--c" as string]: "var(--c-fatt)" }}><i />Fatture emesse</span>
                <span style={{ ["--c" as string]: "color-mix(in srgb,var(--c-fatt) 35%,var(--sunk))" }}><i />Da fatturare subito</span>
                <span style={{ ["--c" as string]: "var(--bad)" }}><i />Scaduto</span>
              </div>
            </div>
            <div className="cash">
              {incassi.map((b, i) => {
                const t = b.a + b.b;
                return (
                  <div className="cc" key={b.k} title={`${b.l}: ${eur(t)}`}>
                    <span className="cv">{t ? kE(t) : ""}</span>
                    <span className="cb">
                      {b.a > 0 && <i style={{ height: `${(b.a / maxI) * 100}%`, background: `var(${i === 0 ? "--bad" : "--c-fatt"})` }} />}
                      {b.b > 0 && <i style={{ height: `${(b.b / maxI) * 100}%`, background: "color-mix(in srgb,var(--c-fatt) 35%,var(--sunk))" }} />}
                    </span>
                    <span className="cl">{b.l}</span>
                  </div>
                );
              })}
            </div>
            <p className="muted" style={{ margin: "10px 0 0", fontSize: 12 }}>
              Totale atteso {eur(incassi.reduce((s, b) => s + b.a + b.b, 0))} · le rate fatturabili sono stimate a {meta.cfg.ggPag} giorni
            </p>
          </section>
        </div>

        <section className="panel">
          <div className="pad" style={{ paddingBottom: 6 }}>
            <div className="sec-h" style={{ margin: 0 }}><h2>Da gestire</h2>
              <span className={`pill ${avvisi.some((a) => a.sev === "bad") ? "bad" : "warn"}`}>{avvisi.length} avvisi</span>
            </div>
          </div>
          <div className="alerts" style={{ maxHeight: 720 }}>
            {avvisi.map((a, i) => (
              <div key={i} className={`al ${a.sev}`}>
                <span className="sv">{a.sev === "bad" ? "!" : a.sev === "warn" ? "△" : "i"}</span>
                <div style={{ minWidth: 0 }}>
                  <div className="tt">{a.tit}</div>
                  <div className="dd">{a.cod && <span className="mono">{a.cod} · </span>}{a.det}</div>
                </div>
                <button className="btn sm" onClick={() => (a.go.view === "sdi" ? vai("sdi") : a.cod && apri(a.cod, a.go.tab))}>Apri</button>
              </div>
            ))}
            {!avvisi.length && <div className="pad muted">Nessuna segnalazione aperta.</div>}
          </div>
        </section>
      </div>
    </div>
  );
}
