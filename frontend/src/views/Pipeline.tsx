import { useState } from "react";
import { api } from "../api";
import { useApp } from "../App";
import { eur } from "../fmt";
import { useAzione, useDati } from "../hooks";
import type { Sintesi } from "../types";
import NuovaCommessa from "./NuovaCommessa";

export default function Pipeline() {
  const { meta, apri, vede, ruolo } = useApp();
  const { dati } = useDati<Sintesi[]>("/api/commesse");
  const azione = useAzione();
  const [q, setQ] = useState("");
  const [drag, setDrag] = useState<string | null>(null);
  const [over, setOver] = useState<number | null>(null);
  const [nuova, setNuova] = useState(false);
  if (!dati) return <div className="muted">Caricamento…</div>;
  const ql = q.trim().toLowerCase();
  const vis = dati.filter((c) => !ql || `${c.cod} ${c.cliente} ${c.oggetto} ${c.cantiere} ${c.sistema}`.toLowerCase().includes(ql));

  const drop = async (fi: number) => {
    setOver(null);
    const c = dati.find((x) => x.cod === drag);
    setDrag(null);
    if (!c) return;
    // si avanza di un solo stato: la colonna di arrivo deve contenere lo stato successivo
    if (!meta.fasi[fi].st.includes(c.stato + 1)) return;
    await azione(() => api.post(`/api/commesse/${c.cod}/avanza`), `${c.cod}: stato «${meta.stati[c.stato + 1]}»`);
  };

  return (
    <div className="stack">
      <div className="hello">
        <div className="pgt"><h2>Pipeline delle commesse</h2><p>Le commesse per fase, dal contratto alla chiusura</p></div>
        {["admin", "commerciale", "direzione"].includes(ruolo) && <button className="btn pri" onClick={() => setNuova(true)}>+ Nuova commessa</button>}
      </div>
      <div className="ptools">
        <input className="search" type="search" placeholder="Cerca commessa, cliente, cantiere" value={q} onChange={(e) => setQ(e.target.value)} />
        <span className="muted hint">Trascina una scheda nella fase successiva per farla avanzare · clic per aprire il fascicolo</span>
      </div>
      <div className="pipe">
        {meta.fasi.map((f, fi) => {
          const cs = vis.filter((c) => f.st.includes(c.stato));
          return (
            <section key={f.l} className={`col ${over === fi ? "over" : ""}`} style={{ ["--pc" as string]: `var(${f.v})` }}
              onDragOver={(e) => { e.preventDefault(); setOver(fi); }} onDragLeave={() => setOver(null)} onDrop={() => drop(fi)}>
              <header><span className="dot" />{f.l}<span className="n">{cs.length}</span></header>
              {vede("r") && cs.length > 0 && <div className="tot muted mono" style={{ fontSize: 12, padding: "0 4px" }}>{eur(cs.reduce((s, c) => s + (c.kpi.ricavo || 0), 0))}</div>}
              {cs.map((c) => (
                <button key={c.cod} className={`pcard ${drag === c.cod ? "dragging" : ""}`} draggable onDragStart={() => setDrag(c.cod)} onDragEnd={() => setDrag(null)} onClick={() => apri(c.cod)}>
                  <span className="t1"><span className="cod">{c.cod}</span>{c.bloccata && <span className="pill bad">Bloccata</span>}</span>
                  <span className="cl">{c.cliente}</span>
                  <span className="ob">{c.oggetto}</span>
                  <span className="mini"><i style={{ width: `${c.kpi.avanz}%` }} /></span>
                  <span className="ft"><span>{meta.stati[c.stato]} · {c.kpi.avanz}%</span><span className="mono">{vede("r") ? eur(c.kpi.ricavo) : ""}</span></span>
                </button>
              ))}
              {!cs.length && <p className="empty">Nessuna commessa</p>}
            </section>
          );
        })}
      </div>
      {nuova && <NuovaCommessa onClose={() => setNuova(false)} />}
    </div>
  );
}
