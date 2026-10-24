import { useEffect, useState } from "react";
import { api, type Ruolo } from "../api";
import { useApp } from "../App";
import { eur, fd, fts, pct } from "../fmt";
import { useAzione, useDati } from "../hooks";
import type { Dettaglio, Sintesi } from "../types";

const TUTTE = ["tempo", "riepilogo", "ordini", "cantiere", "fatturazione", "documenti", "registro"];
const TABS: Record<Ruolo, string[]> = {
  admin: TUTTE, direzione: TUTTE,
  commerciale: ["tempo", "riepilogo", "fatturazione", "documenti", "registro"],
  tecnico: ["tempo", "riepilogo", "ordini", "cantiere", "documenti", "registro"],
  cantiere: ["tempo", "ordini", "cantiere", "documenti", "registro"],
  capocantiere: ["tempo", "cantiere", "ordini", "documenti"],
};
const TABL: Record<string, string> = { tempo: "Linea del tempo", riepilogo: "Riepilogo", ordini: "Ordini fornitori", cantiere: "Cantiere", fatturazione: "Fatturazione e incassi", documenti: "Documenti", registro: "Registro" };
const NEXT_BY: Ruolo[][] = [["commerciale"], ["tecnico"], ["tecnico"], ["cantiere"], ["capocantiere", "cantiere"], ["tecnico"], ["admin"], ["admin"]];

export default function Commesse({ sel, tab, onSel }: { sel: string | null; tab: string; onSel: (cod: string, tab?: string) => void }) {
  const { meta } = useApp();
  const { dati } = useDati<Sintesi[]>("/api/commesse");
  const [q, setQ] = useState("");
  const cod = dati && (dati.some((c) => c.cod === sel) ? sel : dati[0]?.cod);
  if (!dati) return <div className="muted">Caricamento…</div>;
  if (!dati.length) return <div className="panel pad muted">Nessuna commessa assegnata a questo ruolo.</div>;
  const ql = q.trim().toLowerCase();
  const fase = (s: number) => meta.fasi.find((f) => f.st.includes(s))!.v;
  return (
    <div className="layout">
      <div className="stack" style={{ gap: 10 }}>
        <input className="search" type="search" placeholder="Cerca commessa, cliente, cantiere" value={q} onChange={(e) => setQ(e.target.value)} />
        <nav className="panel clist" aria-label="Elenco commesse">
          {dati.filter((c) => !ql || `${c.cod} ${c.cliente} ${c.oggetto} ${c.cantiere}`.toLowerCase().includes(ql)).map((c) => (
            <button key={c.cod} className="ci" style={{ ["--pc" as string]: `var(${fase(c.stato)})` }} aria-current={cod === c.cod} onClick={() => onSel(c.cod)}>
              <span className="l1"><span className="cod">{c.cod}</span>{c.fonte !== "manuale" && c.fonte !== "esempio" && <span className="pill info">{c.fonte}</span>}</span>
              <span className="cl">{c.cliente}</span>
              <span className="ob">{c.oggetto}</span>
              <span className="mini"><i style={{ width: `${c.kpi.avanz}%` }} /></span>
              <span className="l1"><span className="pill ph">{c.bloccata ? "Bloccata · " : ""}{meta.stati[c.stato]}</span><span className="ob mono">{c.kpi.avanz}%</span></span>
            </button>
          ))}
        </nav>
      </div>
      <div className="stack" style={{ minWidth: 0 }}>{cod && <Fascicolo cod={cod} tab={tab} onTab={(t) => onSel(cod, t)} />}</div>
    </div>
  );
}

function Fascicolo({ cod, tab, onTab }: { cod: string; tab: string; onTab: (t: string) => void }) {
  const { meta, ruolo, vede } = useApp();
  const { dati: c } = useDati<Dettaglio>(`/api/commesse/${encodeURIComponent(cod)}`);
  const azione = useAzione();
  if (!c || c.cod !== cod) return <div className="panel pad muted">Caricamento…</div>;
  const k = c.kpi;
  const pv = meta.fasi.find((f) => f.st.includes(c.stato))!.v;
  const tabs = TABS[ruolo];
  const t = tabs.includes(tab) ? tab : tabs[0];
  const post = (p: string, ok: string) => azione(() => api.post(`/api/commesse/${cod}${p}`), ok);
  const soglia = Number(meta.cfg.sogliaMarg) / 100;

  return (
    <>
      <section className="panel pad dossier" style={{ ["--pc" as string]: `var(${pv})` }}>
        <div className="dh">
          <div style={{ minWidth: 0 }}>
            <span className="badge"><span className="dot" />{c.cod} · {meta.stati[c.stato]}</span>
            <h2>{c.cliente}</h2>
            <div className="muted">{c.oggetto}</div>
            <div className="chips">
              <span><b>Sistema</b>{c.sistema}</span><span><b>Cantiere</b>{c.cantiere}</span><span><b>Contratto</b>{fd(c.contratto)}</span>
              <span><b>Commerciale</b>{c.commerciale}</span><span><b>Capocantiere</b>{c.capo || "da assegnare"}</span>
            </div>
          </div>
          <div className="dring">
            <div className="rg" title="Avanzamento lavori">
              <svg viewBox="0 0 76 76" aria-hidden="true"><circle cx="38" cy="38" r="32" fill="none" stroke="var(--line)" strokeWidth="7" />
                <circle className="pr" cx="38" cy="38" r="32" fill="none" stroke={`var(${pv})`} strokeWidth="7" strokeLinecap="round" strokeDasharray="201.1" strokeDashoffset={(201.1 * (1 - k.avanz / 100)).toFixed(1)} /></svg>
              <b>{k.avanz}%</b>
            </div>
            {vede("r") && (
              <div className="big-r"><div className="lbl">Ricavo totale</div><div className="v">{eur(k.ricavo)}</div>
                {vede("m") && <div className={(k.marg_pct ?? 0) < soglia ? "neg" : "pos"} style={{ fontSize: 13, fontWeight: 600 }}>margine previsto {pct(k.marg_pct)}</div>}
              </div>
            )}
          </div>
        </div>
        {vede("r") && (
          <div className="dstrip">
            <div className="dk"><span>Fatturato</span><b>{eur(k.fatturato)}</b><i><u style={{ width: `${k.ricavo ? Math.min(100, (k.fatturato! / k.ricavo) * 100) : 0}%` }} /></i></div>
            <div className="dk"><span>Incassato</span><b>{eur(k.incassato)}</b><i><u style={{ width: `${k.fatturato ? Math.min(100, (k.incassato! / k.fatturato) * 100) : 0}%` }} /></i></div>
            {vede("m") && <div className="dk"><span>Costi sostenuti</span><b>{eur(k.sostenuto)}</b><i><u style={{ width: `${k.eac ? Math.min(100, (k.sostenuto! / k.eac) * 100) : 0}%` }} /></i></div>}
            <div className="dk"><span>Credito aperto</span><b>{eur(k.credito)}</b></div>
          </div>
        )}
        {c.bloccata && <div className="blk">Commessa bloccata dall'amministrazione: niente nuovi ordini né cambi di stato.</div>}
        <ol className="steps">
          {meta.stati.map((s, i) => (
            <li key={s} className={i < c.stato ? "done" : i === c.stato ? "cur" : ""} style={{ ["--pc" as string]: `var(${meta.fasi.find((f) => f.st.includes(i))!.v})` }}><i />{s}</li>
          ))}
        </ol>
        <div className="stbar">
          {c.stato < 8 ? (
            c.puo_avanzare ? (
              <>
                <button className="btn pri" disabled={!!c.blocco} onClick={() => post("/avanza", `Stato: ${meta.stati[c.stato + 1]}`)}>Avanza a «{meta.stati[c.stato + 1]}» →</button>
                {c.blocco && <span className="reason">{c.blocco}</span>}
              </>
            ) : (
              <span className="muted" style={{ fontSize: 13 }}>Il passaggio a «{meta.stati[c.stato + 1]}» spetta a: {NEXT_BY[c.stato].map((r) => meta.ruoli[r].l).join(" o ")}</span>
            )
          ) : <span className="pill good">Commessa chiusa</span>}
          {c.stato === 5 && !c.collaudo_ok && ["admin", "tecnico"].includes(ruolo) && <button className="btn" onClick={() => post("/collaudo", "Collaudo registrato")}>Registra collaudo e DICH.IMP.</button>}
          {ruolo === "admin" && <button className={`btn ${c.bloccata ? "" : "dang"}`} onClick={() => post(`/blocca?bloccata=${!c.bloccata}`, c.bloccata ? "Commessa sbloccata" : "Commessa bloccata")}>{c.bloccata ? "Sblocca commessa" : "Blocca commessa"}</button>}
        </div>
      </section>
      <section className="panel pad">
        <div className="tabs" role="tablist">{tabs.map((x) => <button key={x} aria-current={t === x} onClick={() => onTab(x)}>{TABL[x]}</button>)}</div>
        <div style={{ paddingTop: 18 }}>
          {t === "tempo" && <TabTempo c={c} />}
          {t === "riepilogo" && <TabRiepilogo c={c} />}
          {t === "ordini" && <TabOrdini c={c} />}
          {t === "cantiere" && <TabCantiere c={c} />}
          {t === "fatturazione" && <TabFatturazione c={c} />}
          {t === "documenti" && <TabDocumenti c={c} />}
          {t === "registro" && <TabRegistro cod={c.cod} />}
        </div>
      </section>
    </>
  );
}

const TT: Record<string, { l: string; v: string; ic: string }> = {
  contratto: { l: "Contratto", v: "--ph-avvio", ic: "C" }, variante: { l: "Varianti", v: "--ph-fatt", ic: "V" }, ordine: { l: "Ordini", v: "--ph-appr", ic: "O" },
  consegna: { l: "Consegne", v: "--ph-prog", ic: "D" }, cantiere: { l: "Cantiere", v: "--ph-cant", ic: "R" }, fpass: { l: "Fatture passive", v: "--c-costi", ic: "P" },
  fatt: { l: "Fatture emesse", v: "--c-ricavo", ic: "F" }, incasso: { l: "Incassi", v: "--c-inc", ic: "€" }, stato: { l: "Stati", v: "--muted", ic: "S" }, doc: { l: "Documenti", v: "--r-tecnico", ic: "▤" },
};

function TabTempo({ c }: { c: Dettaglio }) {
  const { meta, vede } = useApp();
  const [off, setOff] = useState<Record<string, boolean>>({});
  type Ev = { d: string; ty: string; t: string; s: string; fut?: boolean; late?: boolean };
  const E: Ev[] = [];
  if (c.contratto) E.push({ d: c.contratto, ty: "contratto", t: "Contratto firmato", s: c.commerciale });
  c.varianti.forEach((v) => E.push({ d: v.data, ty: "variante", t: `Variante ${v.codice} ${v.stato}`, s: v.descr + (v.importo != null ? " · " + eur(v.importo) : "") }));
  c.ordini.forEach((o) => {
    E.push({ d: o.data, ty: "ordine", t: `Ordine ${o.id}`, s: `${o.fornitore} · ${o.descr}${o.importo != null ? " · " + eur(o.importo) : ""}${o.stato === "Autorizzazione richiesta" ? " · in attesa di autorizzazione" : ""}` });
    if (o.consegna) E.push({ d: o.consegna, ty: "consegna", t: `Consegna in cantiere ${o.id}`, s: o.fornitore });
  });
  c.documenti.forEach((d) => d.data && E.push({ d: d.data, ty: "doc", t: `Documento caricato: ${d.l}`, s: `${d.caricato_da} · ${d.file}` }));
  c.rapportini.forEach((r) => E.push({ d: r.data, ty: "cantiere", t: `Rapportino · avanzamento ${r.avanz}%`, s: `${r.chi} · ${r.ore} h · ${r.nota}` }));
  c.fp?.forEach((f) => E.push({ d: f.data, ty: "fpass", t: `Fattura passiva ${f.num}`, s: `${f.fornitore} · ${eur(f.importo)}` }));
  if (c.collaudo_data) E.push({ d: c.collaudo_data, ty: "stato", t: "Collaudo e DICH.IMP. registrati", s: "Ufficio tecnico" });
  c.piano?.forEach((p) => {
    if (p.fattura_num && p.fattura_data) E.push({ d: p.fattura_data, ty: "fatt", t: `Fattura ${p.fattura_num}`, s: `${p.descr} · ${eur(p.importo)}` });
    if (p.incasso_data) E.push({ d: p.incasso_data, ty: "incasso", t: `Incasso ${p.fattura_num}`, s: eur(p.importo) });
    if (p.fattura_num && !p.incasso_data && p.fattura_scad)
      E.push({ d: p.fattura_scad, ty: "incasso", t: p.stato.late ? `Incasso scaduto da ${p.stato.late} giorni` : `Incasso atteso entro il ${fd(p.fattura_scad)}`, s: `${p.fattura_num} · ${eur(p.importo)}`, fut: true, late: !!p.stato.late });
  });
  E.sort((a, b) => (a.d < b.d ? -1 : a.d > b.d ? 1 : 0));
  const tipi = [...new Set(E.map((e) => e.ty))];
  return (
    <>
      <div className="tlf">{tipi.map((ty) => (
        <button key={ty} style={{ ["--tc" as string]: `var(${TT[ty].v})` }} aria-pressed={!off[ty]} onClick={() => setOff({ ...off, [ty]: !off[ty] })}><i />{TT[ty].l}</button>
      ))}</div>
      <ol className="tl">
        {E.filter((e) => !off[e.ty]).map((e, i) => (
          <li key={i} className={`${e.fut || e.d > meta.oggi ? "fut" : ""} ${e.late ? "late" : ""}`} style={{ ["--tc" as string]: `var(${TT[e.ty].v})` }}>
            <span className="ic">{TT[e.ty].ic}</span><span className="d">{fd(e.d)}</span><div className="x"><b>{e.t}</b><div>{e.s}</div></div>
          </li>
        ))}
      </ol>
      {!vede("c") && <p className="muted" style={{ fontSize: 12 }}>Gli importi dei costi non sono visibili per il tuo ruolo.</p>}
    </>
  );
}

function TabRiepilogo({ c }: { c: Dettaglio }) {
  const { vede, ruolo } = useApp();
  const azione = useAzione();
  const [v, setV] = useState({ descr: "", importo: "" });
  const k = c.kpi;
  return (
    <div className="stack">
      <div className="figs">
        {vede("r") && <div className="fig"><span className="lbl">Ricavo con varianti</span><span className="v big">{eur(k.ricavo)}</span></div>}
        {vede("c") && <div className="fig"><span className="lbl">Budget costi</span><span className="v">{eur(k.budget)}</span></div>}
        {vede("c") && <div className="fig"><span className="lbl">Impegnato (ordini)</span><span className="v">{eur(k.impegnato)}</span></div>}
        {vede("c") && <div className="fig"><span className="lbl">Sostenuto (fatture)</span><span className="v">{eur(k.sostenuto)}</span></div>}
        {vede("c") && <div className="fig"><span className="lbl">Costo a finire</span><span className="v">{eur(k.eac)}</span></div>}
        {vede("m") && <div className="fig"><span className="lbl">Margine previsto</span><span className={`v big ${(k.margine ?? 0) < 0 ? "neg" : "pos"}`}>{eur(k.margine)} · {pct(k.marg_pct)}</span></div>}
        {vede("m") && <div className="fig"><span className="lbl">Avanzamento economico</span><span className="v">{pct(k.c2c)} <span className="muted" style={{ fontSize: 12 }}>cantiere {k.avanz}%</span></span></div>}
      </div>
      {k.cats && (
        <div className="tw"><table className="t">
          <thead><tr><th>Voce di costo</th><th className="num">Budget</th><th className="num">Impegnato</th><th className="num">Sostenuto</th><th className="num">A finire</th><th className="num">Residuo</th><th style={{ width: 140 }}>Consumo</th></tr></thead>
          <tbody>{k.cats.map((x) => (
            <tr key={x.k}><td>{x.k}</td><td className="num">{eur(x.budget)}</td><td className="num">{eur(x.imp)}</td><td className="num">{eur(x.sost)}</td><td className="num">{eur(x.eac)}</td>
              <td className={`num ${x.residuo < 0 ? "neg" : ""}`}>{eur(x.residuo)}</td>
              <td><div className="bar"><i style={{ width: `${x.budget ? Math.min(100, (Math.max(x.imp, x.sost) / x.budget) * 100) : x.imp ? 100 : 0}%`, ["--c" as string]: Math.max(x.imp, x.sost) > x.budget ? "var(--bad)" : "var(--ph-prog)" }} /></div></td></tr>
          ))}</tbody>
          <tfoot><tr><td>Totale</td><td className="num">{eur(k.budget)}</td><td className="num">{eur(k.impegnato)}</td><td className="num">{eur(k.sostenuto)}</td><td className="num">{eur(k.eac)}</td><td className="num">{eur((k.budget ?? 0) - (k.impegnato ?? 0))}</td><td /></tr></tfoot>
        </table></div>
      )}
      <div>
        <h3 style={{ fontSize: 15, marginBottom: 8 }}>Varianti</h3>
        {c.varianti.length ? (
          <div className="tw"><table className="t"><thead><tr><th>Variante</th><th>Descrizione</th><th className="num">Importo</th><th>Stato</th><th /></tr></thead>
            <tbody>{c.varianti.map((x) => (
              <tr key={x.id}><td className="mono">{x.codice}</td><td>{x.descr}<div className="muted" style={{ fontSize: 12 }}>{x.da} · {fd(x.data)}</div></td><td className="num">{eur(x.importo)}</td>
                <td><span className={`pill ${x.stato === "approvata" ? "good" : x.stato === "respinta" ? "bad" : "warn"}`}>{x.stato}</span></td>
                <td>{x.stato === "proposta" && ["admin", "direzione"].includes(ruolo) && (
                  <span className="row"><button className="btn sm pri" onClick={() => azione(() => api.post(`/api/commesse/${c.cod}/varianti/${x.id}/approva`), "Variante approvata")}>Approva</button>
                    <button className="btn sm dang" onClick={() => azione(() => api.post(`/api/commesse/${c.cod}/varianti/${x.id}/respingi`), "Variante respinta")}>Respingi</button></span>)}</td></tr>
            ))}</tbody></table></div>
        ) : <p className="muted">Nessuna variante.</p>}
        {["admin", "commerciale"].includes(ruolo) && c.stato < 8 && (
          <form className="row" style={{ marginTop: 10 }} onSubmit={async (e) => { e.preventDefault(); if (await azione(() => api.post(`/api/commesse/${c.cod}/varianti`, { descr: v.descr, importo: Number(v.importo.replace(/\./g, "").replace(",", ".")) }), "Variante proposta")) setV({ descr: "", importo: "" }); }}>
            <input className="search" style={{ flex: "2 1 220px" }} placeholder="Descrizione variante" required value={v.descr} onChange={(e) => setV({ ...v, descr: e.target.value })} />
            <input className="search" style={{ flex: "1 1 110px" }} placeholder="Importo €" required inputMode="decimal" value={v.importo} onChange={(e) => setV({ ...v, importo: e.target.value })} />
            <button className="btn">Proponi variante</button>
          </form>
        )}
      </div>
    </div>
  );
}

function TabOrdini({ c }: { c: Dettaglio }) {
  const { meta, ruolo, vede } = useApp();
  const azione = useAzione();
  const [f, setF] = useState({ fornitore: "", categoria: meta.cats[0], descrizione: "", importo: "" });
  const az = (oid: string, a: string, ok: string) => azione(() => api.post(`/api/commesse/${c.cod}/ordini/${oid}/${a}`), ok);
  const puoOrdinare = ["admin", "tecnico", "cantiere"].includes(ruolo) && c.stato < 8 && !c.bloccata;
  return (
    <div className="stack">
      <div className="tw"><table className="t">
        <thead><tr><th>Ordine</th><th>Fornitore e descrizione</th><th>Voce</th>{vede("c") && <th className="num">Importo</th>}{vede("c") && <th className="num">Fatturato</th>}<th>Stato</th><th /></tr></thead>
        <tbody>{c.ordini.map((o) => (
          <tr key={o.id}>
            <td className="mono">{o.id}<div className="muted" style={{ fontSize: 12 }}>{fd(o.data)}</div>{o.fonte && o.fonte !== "manuale" && o.fonte !== "esempio" && <span className="pill info">{o.fonte}</span>}</td>
            <td>{o.fornitore}<div className="muted" style={{ fontSize: 12 }}>{o.descr}{o.nota ? ` · ${o.nota}` : ""}</div></td>
            <td>{o.categoria}</td>
            {vede("c") && <td className="num">{eur(o.importo)}</td>}
            {vede("c") && <td className="num">{eur(o.fatturato)}</td>}
            <td><span className={`pill ${o.stato === "Consegnato" ? "good" : o.stato === "Autorizzazione richiesta" ? "warn" : o.stato === "Respinto" ? "bad" : "info"}`}>{o.stato}</span>{o.consegna && <div className="muted" style={{ fontSize: 12 }}>{fd(o.consegna)}</div>}</td>
            <td>
              {o.stato === "Autorizzazione richiesta" && ["admin", "direzione"].includes(ruolo) && (
                <span className="row"><button className="btn sm pri" onClick={() => az(o.id, "autorizza", `Ordine ${o.id} autorizzato`)}>Autorizza</button>
                  <button className="btn sm dang" onClick={() => az(o.id, "respingi", `Ordine ${o.id} respinto`)}>Respingi</button></span>)}
              {o.stato === "Ordinato" && ["admin", "cantiere", "capocantiere", "tecnico"].includes(ruolo) && <button className="btn sm" onClick={() => az(o.id, "consegna", `Consegna di ${o.id} registrata`)}>Segna consegnato</button>}
            </td>
          </tr>
        ))}
        {!c.ordini.length && <tr><td colSpan={7} className="muted">Nessun ordine emesso.</td></tr>}</tbody>
      </table></div>
      {puoOrdinare && (
        <form className="panel pad" style={{ background: "var(--sunk)" }} onSubmit={async (e) => {
          e.preventDefault();
          if (await azione(() => api.post(`/api/commesse/${c.cod}/ordini`, { ...f, importo: Number(f.importo.replace(/\./g, "").replace(",", ".")) }), "Ordine registrato")) setF({ ...f, fornitore: "", descrizione: "", importo: "" });
        }}>
          <div className="sec-h"><h2 style={{ fontSize: 15 }}>Nuovo ordine fornitore</h2><span className="muted" style={{ fontSize: 12 }}>Oltre il residuo di budget va in autorizzazione</span></div>
          <div className="row">
            <input className="search" style={{ flex: "2 1 200px" }} placeholder="Fornitore" required value={f.fornitore} onChange={(e) => setF({ ...f, fornitore: e.target.value })} />
            <select className="search" style={{ flex: "1 1 160px" }} value={f.categoria} onChange={(e) => setF({ ...f, categoria: e.target.value })}>{meta.cats.filter((x) => x !== "Manodopera interna").map((x) => <option key={x}>{x}</option>)}</select>
            <input className="search" style={{ flex: "2 1 200px" }} placeholder="Descrizione" value={f.descrizione} onChange={(e) => setF({ ...f, descrizione: e.target.value })} />
            <input className="search" style={{ flex: "1 1 110px" }} placeholder="Importo €" required inputMode="decimal" value={f.importo} onChange={(e) => setF({ ...f, importo: e.target.value })} />
            <button className="btn pri">Emetti ordine</button>
          </div>
        </form>
      )}
      {c.fp && (
        <div>
          <h3 style={{ fontSize: 15, marginBottom: 8 }}>Fatture passive registrate</h3>
          <div className="tw"><table className="t">
            <thead><tr><th>Fattura</th><th>Fornitore</th><th>Ordine</th><th>Voce</th><th className="num">Importo</th><th>Pagata</th><th>Fonte</th></tr></thead>
            <tbody>{c.fp.map((x) => (
              <tr key={x.id}><td className="mono">{x.num}<div className="muted" style={{ fontSize: 12 }}>{fd(x.data)}</div></td><td>{x.fornitore}</td><td className="mono">{x.ordine || "—"}</td><td>{x.categoria}</td>
                <td className="num">{eur(x.importo)}</td><td>{x.pagamento ? fd(x.pagamento) : <span className="pill warn">da pagare</span>}</td><td><span className="pill">{x.fonte}</span></td></tr>
            ))}
            {!c.fp.length && <tr><td colSpan={7} className="muted">Nessuna fattura passiva.</td></tr>}</tbody>
          </table></div>
        </div>
      )}
    </div>
  );
}

function TabCantiere({ c }: { c: Dettaglio }) {
  const { ruolo, meta } = useApp();
  const azione = useAzione();
  const [f, setF] = useState({ ore: "", avanzamento: String(c.kpi.avanz), nota: "" });
  useEffect(() => setF((x) => ({ ...x, avanzamento: String(c.kpi.avanz) })), [c.kpi.avanz]);
  const puo = ["admin", "cantiere", "capocantiere"].includes(ruolo) && c.stato === 4;
  return (
    <div className="stack">
      <div className="figs">
        <div className="fig"><span className="lbl">Avanzamento dichiarato</span><span className="v big">{c.kpi.avanz}%</span></div>
        <div className="fig"><span className="lbl">Ore di cantiere</span><span className="v">{c.kpi.ore} h</span></div>
        {c.kpi.mo != null && <div className="fig"><span className="lbl">Costo manodopera</span><span className="v">{eur(c.kpi.mo)}</span><span className="muted" style={{ fontSize: 12 }}>a {meta.cfg.costoOra} €/h</span></div>}
      </div>
      <div className="tw"><table className="t">
        <thead><tr><th>Data</th><th>Chi</th><th className="num">Ore</th><th className="num">Avanzamento</th><th>Nota</th><th>Fonte</th></tr></thead>
        <tbody>{c.rapportini.map((r) => <tr key={r.id}><td>{fd(r.data)}</td><td>{r.chi}</td><td className="num">{r.ore}</td><td className="num">{r.avanz}%</td><td>{r.nota}</td><td><span className="pill">{r.fonte}</span></td></tr>)}
          {!c.rapportini.length && <tr><td colSpan={6} className="muted">Nessun rapportino.</td></tr>}</tbody>
      </table></div>
      {puo ? (
        <form className="row" onSubmit={async (e) => {
          e.preventDefault();
          if (await azione(() => api.post(`/api/commesse/${c.cod}/rapportini`, { ore: Number(f.ore.replace(",", ".")), avanzamento: Number(f.avanzamento), nota: f.nota }), "Rapportino registrato")) setF({ ...f, ore: "", nota: "" });
        }}>
          <input className="search" style={{ flex: "1 1 90px" }} placeholder="Ore" required inputMode="decimal" value={f.ore} onChange={(e) => setF({ ...f, ore: e.target.value })} />
          <label className="row" style={{ flex: "2 1 220px", gap: 8 }}><span className="muted" style={{ fontSize: 13 }}>Avanzamento {f.avanzamento}%</span>
            <input type="range" min={c.kpi.avanz} max={100} value={f.avanzamento} onChange={(e) => setF({ ...f, avanzamento: e.target.value })} style={{ flex: 1 }} /></label>
          <input className="search" style={{ flex: "3 1 220px" }} placeholder="Lavori eseguiti" value={f.nota} onChange={(e) => setF({ ...f, nota: e.target.value })} />
          <button className="btn pri">Invia rapportino</button>
        </form>
      ) : c.stato !== 4 && <p className="muted" style={{ fontSize: 13 }}>I rapportini si inseriscono quando la commessa è in «Posa in cantiere».</p>}
    </div>
  );
}

function TabFatturazione({ c }: { c: Dettaglio }) {
  const { ruolo, meta } = useApp();
  const azione = useAzione();
  if (!c.piano) return <p className="muted">Non visibile per il tuo ruolo.</p>;
  return (
    <div className="tw"><table className="t">
      <thead><tr><th>Rata</th><th>Condizione</th><th className="num">Importo</th><th>Fattura</th><th>Scadenza</th><th>Stato</th><th /></tr></thead>
      <tbody>{c.piano.map((p) => (
        <tr key={p.id}>
          <td>{p.descr}</td><td className="muted">{meta.trig[p.trigger]}</td><td className="num">{eur(p.importo)}</td>
          <td className="mono">{p.fattura_num || "—"}{p.fattura_data && <div className="muted" style={{ fontSize: 12 }}>{fd(p.fattura_data)}</div>}</td>
          <td>{fd(p.fattura_scad)}</td>
          <td><span className={`pill ${p.stato.cls}`}>{p.stato.t}</span>{p.incasso_data && <div className="muted" style={{ fontSize: 12 }}>{fd(p.incasso_data)}</div>}</td>
          <td>{ruolo === "admin" && (p.stato.fb
            ? <button className="btn sm pri" onClick={() => azione(() => api.post(`/api/commesse/${c.cod}/rate/${p.id}/fattura`), "Fattura emessa")}>Emetti fattura</button>
            : p.fattura_num && !p.incasso_data && <button className="btn sm" onClick={() => azione(() => api.post(`/api/commesse/${c.cod}/rate/${p.id}/incasso`), "Incasso registrato")}>Registra incasso</button>)}</td>
        </tr>
      ))}</tbody>
      <tfoot><tr><td colSpan={2}>Totale</td><td className="num">{eur(c.piano.reduce((s, p) => s + p.importo, 0))}</td><td colSpan={4} /></tr></tfoot>
    </table></div>
  );
}

function TabDocumenti({ c }: { c: Dettaglio }) {
  const { ruolo, meta } = useApp();
  const azione = useAzione();
  const dovuto = (fase: number) => (fase < 5 ? fase <= c.stato : c.stato >= 6);
  const carica = (tipo: string, file: File) => {
    const fd_ = new FormData();
    fd_.append("file", file);
    return azione(() => api.post(`/api/commesse/${c.cod}/documenti/${tipo}`, fd_), "Documento caricato");
  };
  const presenti = c.documenti.filter((d) => d.file).length;
  return (
    <div className="stack">
      <div className="docmeter"><span>{presenti} di {c.documenti.length} documenti</span><div className="bar"><i style={{ width: `${(presenti / c.documenti.length) * 100}%`, ["--c" as string]: "var(--good)" }} /></div></div>
      <div className="docs">{c.documenti.map((d) => {
        const manca = !d.file && dovuto(d.fase);
        const puo = ruolo === "admin" || meta.ruoli[ruolo].l === d.chi;
        return (
          <div key={d.k} className={`doc ${d.file ? "ok" : manca ? "miss" : ""}`}>
            <span className="di">{d.file ? "✓" : manca ? "!" : "·"}</span>
            <div style={{ minWidth: 0 }}><div className="dn">{d.l}</div>
              <div className="dm">{d.file ? <><span className="fn">{d.file}</span> · {d.caricato_da} · {fd(d.data)}</> : `Fase: ${meta.stati[d.fase]} · a cura di ${d.chi}`}</div></div>
            <div className="row">{puo && (
              <label className="btn sm">{d.file ? "Sostituisci" : "Carica"}<input type="file" hidden onChange={(e) => e.target.files?.[0] && carica(d.k, e.target.files[0])} /></label>
            )}</div>
          </div>
        );
      })}</div>
    </div>
  );
}

function TabRegistro({ cod }: { cod: string }) {
  const { dati } = useDati<{ id: number; ts: string; chi: string; t: string }[]>(`/api/log?cod=${encodeURIComponent(cod)}`);
  if (!dati) return <div className="muted">Caricamento…</div>;
  return (
    <div className="feed">{dati.map((l) => (
      <div key={l.id} className="fi" style={{ ["--tc" as string]: "var(--ph-avvio)" }}><span className="ic">{l.chi.slice(0, 2).toUpperCase()}</span><div><b>{l.t}</b><div>{l.chi}</div></div><span className="tm">{fts(l.ts)}</span></div>
    ))}{!dati.length && <p className="muted">Nessuna attività registrata.</p>}</div>
  );
}
