import { useRef, useState } from "react";
import { api } from "../api";
import { useApp } from "../App";
import { eur, fd, fts } from "../fmt";
import { useAzione, useDati } from "../hooks";
import type { EsitoImport } from "../types";

interface InfoFonti {
  file: { nome: string; etichetta: string; descrizione: string; estensioni: string[]; tipi: string[]; serve_tipo: boolean }[];
  erp: { nome: string; etichetta: string; tipo?: string; dove?: string; tipi: string[]; errore?: string }[];
  tipi: Record<string, { l: string; req: string[]; opt: string[] }>;
}
interface Storico { id: number; ts: string; connettore: string; tipo: string; origine: string; utente: string; ok: number; errori: number }
interface Movimento { id: number; data: string; importo: number; causale: string; controparte: string | null; fonte: string; abbinamento: string | null; abbinato: boolean }

const CLS: Record<string, string> = { errore: "bad", creato: "good", creata: "good", abbinato: "good", abbinata: "good", aggiornato: "info", aggiornata: "info", "non abbinato": "warn", "da verificare": "warn" };

export default function Fonti() {
  const { toast, aggiorna } = useApp();
  const { dati: info } = useDati<InfoFonti>("/api/fonti");
  const { dati: storico } = useDati<Storico[]>("/api/fonti/storico");
  const { dati: movimenti } = useDati<Movimento[]>("/api/movimenti");
  const azione = useAzione();
  const [conn, setConn] = useState("tabelle");
  const [tipo, setTipo] = useState("ordine");
  const [file, setFile] = useState<File | null>(null);
  const [esito, setEsito] = useState<{ da: string; e: EsitoImport; salvato: boolean } | null>(null);
  const [lavoro, setLavoro] = useState(false);
  const inp = useRef<HTMLInputElement>(null);
  if (!info) return <div className="muted">Caricamento…</div>;
  const c = info.file.find((x) => x.nome === conn)!;

  const invia = async (salva: boolean) => {
    if (!file) return;
    const fd_ = new FormData();
    fd_.append("file", file);
    if (c.serve_tipo) fd_.append("tipo", tipo);
    fd_.append("salva", String(salva));
    setLavoro(true);
    try {
      const e = await api.post<EsitoImport>(`/api/fonti/file/${conn}`, fd_);
      setEsito({ da: file.name, e, salvato: salva });
      if (salva) { toast(`Importazione completata: ${e.ok} righe acquisite`); aggiorna(); }
    } catch (err) { toast((err as Error).message, "bad"); } finally { setLavoro(false); }
  };
  const sincronizza = async (nome: string, salva: boolean) => {
    setLavoro(true);
    const e = await azione(() => api.post<EsitoImport>(`/api/fonti/erp/${nome}?salva=${salva}`), salva ? "Sincronizzazione completata" : undefined);
    if (e) setEsito({ da: nome, e, salvato: salva });
    setLavoro(false);
  };

  return (
    <div className="stack">
      <div className="hello"><div className="pgt"><h2>Fonti dati</h2><p>Excel e CSV, fatture elettroniche SDI, estratti conto e gestionale: ogni importazione si controlla in anteprima prima di salvarla</p></div></div>

      <div className="cfg">
        {info.file.map((x) => (
          <button key={x.nome} className="panel pad" style={{ textAlign: "left", cursor: "pointer", borderColor: conn === x.nome ? "var(--ember)" : undefined, boxShadow: conn === x.nome ? "0 0 0 2px var(--glow)" : undefined }}
            onClick={() => { setConn(x.nome); setFile(null); setEsito(null); }}>
            <div className="lbl">{x.estensioni.join(" · ")}</div><h3 style={{ fontSize: 16, margin: "4px 0" }}>{x.etichetta}</h3><small>{x.descrizione}</small>
          </button>
        ))}
      </div>

      <section className="panel pad stack">
        <div className="sec-h" style={{ margin: 0 }}><h2>Carica da: {c.etichetta}</h2></div>
        {c.serve_tipo && (
          <div className="row">
            <span className="lbl">Il file contiene</span>
            <div className="seg">{c.tipi.map((t) => <button key={t} aria-pressed={tipo === t} onClick={() => { setTipo(t); setEsito(null); }}>{info.tipi[t].l}</button>)}</div>
          </div>
        )}
        {c.serve_tipo && (
          <div className="note">
            Colonne obbligatorie: <code>{info.tipi[tipo].req.join(", ")}</code>{info.tipi[tipo].opt.length > 0 && <> · facoltative: <code>{info.tipi[tipo].opt.join(", ")}</code></>}.
            Si accettano anche i nomi più comuni dei gestionali (es. «Imponibile», «N. fattura», «Centro di costo»). Date gg/mm/aaaa, importi all'italiana.{" "}
            <a href={`/api/fonti/modello/${tipo}.csv`}>Scarica il modello CSV</a>
          </div>
        )}
        <div className="row">
          <input ref={inp} type="file" hidden accept={c.estensioni.join(",")} onChange={(e) => { setFile(e.target.files?.[0] || null); setEsito(null); }} />
          <button className="btn" onClick={() => inp.current?.click()}>{file ? "Cambia file" : "Scegli file"}</button>
          {file && <span className="mono" style={{ fontSize: 13 }}>{file.name}</span>}
          <span style={{ flex: 1 }} />
          <button className="btn" disabled={!file || lavoro} onClick={() => invia(false)}>Anteprima</button>
          <button className="btn pri" disabled={!file || lavoro || !esito || esito.salvato || esito.e.ok === 0} onClick={() => invia(true)}>Importa {esito && !esito.salvato ? `${esito.e.ok} righe` : ""}</button>
        </div>
      </section>

      <section className="panel pad stack">
        <div className="sec-h" style={{ margin: 0 }}><h2>Gestionale / ERP</h2><span className="muted" style={{ fontSize: 12 }}>Connessioni configurate in backend/fonti.yaml</span></div>
        {!info.erp.length && <p className="muted">Nessuna connessione configurata. Copia <code>fonti.example.yaml</code> in <code>fonti.yaml</code> e indica database o API del gestionale.</p>}
        {info.erp.map((x) => (
          <div key={x.nome} className="row" style={{ justifyContent: "space-between", borderTop: "1px solid var(--line)", paddingTop: 10 }}>
            <div><b>{x.etichetta}</b> <span className="pill">{x.tipo || "?"}</span>
              <div className="muted" style={{ fontSize: 12 }}>{x.errore || <>{x.dove} · {x.tipi.map((t) => info.tipi[t]?.l || t).join(", ")}</>}</div></div>
            {!x.errore && <div className="row"><button className="btn" disabled={lavoro} onClick={() => sincronizza(x.nome, false)}>Anteprima</button>
              <button className="btn pri" disabled={lavoro} onClick={() => sincronizza(x.nome, true)}>Sincronizza</button></div>}
          </div>
        ))}
      </section>

      {esito && (
        <section className="panel pad">
          <div className="sec-h"><h2>{esito.salvato ? "Esito dell'importazione" : "Anteprima: niente è ancora stato salvato"}</h2>
            <div className="row">{Object.entries(esito.e.riepilogo).map(([k, n]) => <span key={k} className={`pill ${CLS[k] || ""}`}>{n} {k}</span>)}</div></div>
          <p className="muted" style={{ marginTop: 0, fontSize: 13 }}>Da {esito.da}{!esito.salvato && esito.e.ok > 0 && " · le righe con errore verranno saltate, le altre importate"}</p>
          <div className="tw"><table className="t"><thead><tr><th>Posizione</th><th>Esito</th><th>Dettaglio</th></tr></thead>
            <tbody>{esito.e.righe.map((r, i) => <tr key={i}><td className="mono" style={{ whiteSpace: "nowrap" }}>{r.riga}</td><td><span className={`pill ${CLS[r.esito] || ""}`}>{r.esito}</span></td><td>{r.m}</td></tr>)}</tbody>
          </table></div>
        </section>
      )}

      {movimenti && movimenti.length > 0 && (
        <section className="panel pad">
          <div className="sec-h"><h2>Movimenti bancari importati</h2><span className="pill warn">{movimenti.filter((m) => !m.abbinato).length} da abbinare</span></div>
          <div className="tw"><table className="t"><thead><tr><th>Data</th><th>Causale</th><th className="num">Importo</th><th>Abbinamento</th></tr></thead>
            <tbody>{movimenti.map((m) => (
              <tr key={m.id}><td>{fd(m.data)}</td><td>{m.causale}{m.controparte && <div className="muted" style={{ fontSize: 12 }}>{m.controparte}</div>}</td>
                <td className={`num ${m.importo < 0 ? "neg" : "pos"}`}>{eur(m.importo)}</td><td><span className={`pill ${m.abbinato ? "good" : "warn"}`}>{m.abbinamento}</span></td></tr>
            ))}</tbody></table></div>
        </section>
      )}

      <section className="panel pad">
        <div className="sec-h"><h2>Storico importazioni</h2></div>
        {storico && storico.length ? (
          <div className="tw"><table className="t"><thead><tr><th>Quando</th><th>Fonte</th><th>Origine</th><th>Utente</th><th className="num">Acquisite</th><th className="num">Scartate</th></tr></thead>
            <tbody>{storico.map((s) => (
              <tr key={s.id} className="click" onClick={async () => setEsito({ da: s.origine, e: await api.get<EsitoImport>(`/api/fonti/storico/${s.id}`), salvato: true })}>
                <td>{fts(s.ts)}</td><td>{s.connettore}</td><td className="mono" style={{ fontSize: 12 }}>{s.origine}</td><td>{s.utente}</td><td className="num">{s.ok}</td><td className={`num ${s.errori ? "neg" : ""}`}>{s.errori}</td></tr>
            ))}</tbody></table></div>
        ) : <p className="muted">Nessuna importazione ancora.</p>}
      </section>
    </div>
  );
}
