import { useState } from "react";
import { api } from "../api";
import { useApp } from "../App";
import { eur, fd } from "../fmt";
import { useAzione, useDati } from "../hooks";
import type { Sintesi } from "../types";

interface FatturaSdi {
  id: number; sdi_id: string | null; fornitore: string; piva: string | null; num: string; data: string; scadenza: string | null; importo: number;
  rif_ordine: string | null; rif_commessa: string | null; descrizione: string | null; file: string | null; fonte: string;
  ordine: { commessa: string; categoria: string; importo: number; fornitore: string; fatturato: number } | null;
}

export default function Sdi() {
  const { meta, vai } = useApp();
  const { dati } = useDati<FatturaSdi[]>("/api/sdi");
  const { dati: commesse } = useDati<Sintesi[]>("/api/commesse");
  const azione = useAzione();
  const [scelte, setScelte] = useState<Record<number, { commessa: string; categoria: string }>>({});
  if (!dati || !commesse) return <div className="muted">Caricamento…</div>;
  const aperte = commesse.filter((c) => c.stato < 8);

  return (
    <div className="stack">
      <div className="hello">
        <div className="pgt"><h2>Fatture SDI da registrare</h2><p>Fatture passive ricevute dallo SDI: abbinale alla commessa per registrarne il costo</p></div>
        <button className="btn" onClick={() => vai("fonti")}>Carica fatture XML</button>
      </div>
      {!dati.length && <div className="panel pad muted">Nessuna fattura in attesa. Le nuove fatture arrivano dalla sezione Fonti dati (file XML/P7M o zip dal cassetto fiscale).</div>}
      <div className="sdi">
        {dati.map((f) => {
          const s = scelte[f.id] || { commessa: f.ordine?.commessa || f.rif_commessa || "", categoria: f.ordine?.categoria || "" };
          const set = (x: Partial<typeof s>) => setScelte({ ...scelte, [f.id]: { ...s, ...x } });
          const residuo = f.ordine ? f.ordine.importo - f.ordine.fatturato : null;
          return (
            <article key={f.id} className="panel pad">
              <div className="sec-h" style={{ margin: 0 }}><h2 style={{ fontSize: 15 }}>{f.fornitore}</h2><span className="mono" style={{ fontWeight: 600 }}>{eur(f.importo)}</span></div>
              <dl className="kv">
                <dt>Numero</dt><dd className="mono">{f.num} del {fd(f.data)}</dd>
                {f.piva && <><dt>P.IVA</dt><dd className="mono">{f.piva}</dd></>}
                {f.scadenza && <><dt>Scadenza</dt><dd>{fd(f.scadenza)}</dd></>}
                <dt>Riferimento</dt><dd>{f.rif_ordine ? <span className="mono">{f.rif_ordine}</span> : <span className="pill warn">nessun ordine indicato</span>}</dd>
                <dt>Origine</dt><dd>{f.file || f.sdi_id || f.fonte}</dd>
              </dl>
              {f.descrizione && <div className="note">{f.descrizione}</div>}
              {f.ordine && (
                <div className="sdichk">
                  <div className={f.ordine.fornitore === f.fornitore ? "" : "x"}>Fornitore {f.ordine.fornitore === f.fornitore ? "coerente con l'ordine" : `diverso dall'ordine (${f.ordine.fornitore})`}</div>
                  <div className={residuo != null && f.importo <= residuo + 0.01 ? "" : "x"}>Importo {residuo != null && f.importo <= residuo + 0.01 ? "entro" : "oltre"} il residuo dell'ordine ({eur(residuo)})</div>
                </div>
              )}
              <div className="two">
                <label className="fld"><span className="lbl">Commessa</span>
                  <select value={s.commessa} onChange={(e) => set({ commessa: e.target.value })}>
                    <option value="">Scegli…</option>{aperte.map((c) => <option key={c.cod} value={c.cod}>{c.cod} · {c.cliente}</option>)}
                  </select></label>
                <label className="fld"><span className="lbl">Voce di costo</span>
                  <select value={s.categoria} disabled={!!f.ordine && s.commessa === f.ordine.commessa} onChange={(e) => set({ categoria: e.target.value })}>
                    <option value="">{f.ordine ? "dall'ordine" : "Scegli…"}</option>{meta.cats.filter((x) => x !== "Manodopera interna").map((x) => <option key={x}>{x}</option>)}
                  </select></label>
              </div>
              <div className="row" style={{ justifyContent: "space-between" }}>
                <button className="btn sm dang" onClick={() => confirm(`Scartare la fattura ${f.num} di ${f.fornitore}? Va usato per le fatture non di commessa (es. spese generali).`) &&
                  azione(() => api.del(`/api/sdi/${f.id}`), "Fattura scartata dalla casella")}>Non è di commessa</button>
                <button className="btn pri" disabled={!s.commessa} onClick={() => azione(() => api.post(`/api/sdi/${f.id}/registra`, {
                  commessa: s.commessa, categoria: s.categoria || null, ordine: f.ordine && s.commessa === f.ordine.commessa ? f.rif_ordine : "",
                }), `Fattura ${f.num} registrata su ${s.commessa}`)}>Registra sulla commessa</button>
              </div>
            </article>
          );
        })}
      </div>
    </div>
  );
}
