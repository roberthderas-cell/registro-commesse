import { useState } from "react";
import { api, type Ruolo } from "../api";
import { useApp } from "../App";
import { fts } from "../fmt";
import { useAzione, useDati } from "../hooks";

interface RigaUtente {
  id: number; username: string; nome: string; ruolo: Ruolo; deve_cambiare_password: boolean; attivo: boolean;
  creato: string; ultimo_accesso: string | null; bloccato_fino: string | null; password_temporanea?: string;
}

export default function Utenti() {
  const { meta, io } = useApp();
  const { dati } = useDati<RigaUtente[]>("/api/utenti");
  const azione = useAzione();
  const [nuovo, setNuovo] = useState({ username: "", nome: "", ruolo: "commerciale" as Ruolo });
  const [modifica, setModifica] = useState<RigaUtente | null>(null);
  const [consegna, setConsegna] = useState<{ u: RigaUtente; pwd: string } | null>(null);
  if (!dati) return <div className="muted">Caricamento…</div>;
  const ruoli = Object.keys(meta.ruoli) as Ruolo[];

  const crea = async (e: React.FormEvent) => {
    e.preventDefault();
    const r = await azione(() => api.post<RigaUtente>("/api/utenti", nuovo), "Utente creato");
    if (r) { setConsegna({ u: r, pwd: r.password_temporanea! }); setNuovo({ ...nuovo, username: "", nome: "" }); }
  };
  const reimposta = async (u: RigaUtente) => {
    if (!confirm(`Reimpostare la password di ${u.nome}? Verrà scollegato da tutti i dispositivi.`)) return;
    const r = await azione(() => api.post<RigaUtente>(`/api/utenti/${u.id}/reimposta-password`), "Password reimpostata");
    if (r) setConsegna({ u: r, pwd: r.password_temporanea! });
  };

  return (
    <div className="stack">
      <div className="hello"><div className="pgt"><h2>Utenti e accessi</h2><p>Chi può entrare nel registro e con quale ruolo</p></div></div>

      <section className="panel pad">
        <div className="tw"><table className="t">
          <thead><tr><th>Utente</th><th>Ruolo</th><th>Stato</th><th>Ultimo accesso</th><th /></tr></thead>
          <tbody>{dati.map((u) => (
            <tr key={u.id} style={{ opacity: u.attivo ? 1 : 0.55 }}>
              <td><b>{u.nome}</b>{u.id === io.id && <span className="muted"> (tu)</span>}<div className="mono muted" style={{ fontSize: 12 }}>{u.username}</div></td>
              <td><span className="pill" style={{ background: `color-mix(in srgb,var(--r-${u.ruolo}) 15%,transparent)`, color: `var(--r-${u.ruolo})` }}>{meta.ruoli[u.ruolo].l}</span></td>
              <td>
                {!u.attivo ? <span className="pill">disattivato</span>
                  : u.bloccato_fino && u.bloccato_fino > new Date().toISOString().slice(0, 19) ? <span className="pill bad">bloccato per tentativi</span>
                  : u.deve_cambiare_password ? <span className="pill warn">primo accesso da fare</span>
                  : <span className="pill good">attivo</span>}
              </td>
              <td className="muted">{u.ultimo_accesso ? fts(u.ultimo_accesso) : "mai"}</td>
              <td><span className="row" style={{ justifyContent: "flex-end" }}>
                <button className="btn sm" onClick={() => setModifica(u)}>Modifica</button>
                <button className="btn sm" onClick={() => reimposta(u)}>Reimposta password</button>
              </span></td>
            </tr>
          ))}</tbody>
        </table></div>
      </section>

      <form className="panel pad stack" onSubmit={crea}>
        <div className="sec-h" style={{ margin: 0 }}><h2>Nuovo utente</h2><span className="muted" style={{ fontSize: 12 }}>Riceverai una password temporanea da consegnare: al primo accesso la cambierà</span></div>
        <div className="row">
          <input className="search" style={{ flex: "1 1 150px" }} placeholder="Nome utente (es. g.rossi)" required pattern="[a-zA-Z0-9._\-]{3,60}" title="Lettere, numeri, punto, trattino; almeno 3 caratteri"
            value={nuovo.username} onChange={(e) => setNuovo({ ...nuovo, username: e.target.value })} />
          <input className="search" style={{ flex: "2 1 180px" }} placeholder="Nome mostrato (es. G. Rossi)" required minLength={2} value={nuovo.nome} onChange={(e) => setNuovo({ ...nuovo, nome: e.target.value })} />
          <select className="search" style={{ flex: "1 1 160px" }} value={nuovo.ruolo} onChange={(e) => setNuovo({ ...nuovo, ruolo: e.target.value as Ruolo })}>
            {ruoli.map((r) => <option key={r} value={r}>{meta.ruoli[r].l}</option>)}
          </select>
          <button className="btn pri">Crea utente</button>
        </div>
        {nuovo.ruolo === "capocantiere" && <p className="muted" style={{ margin: 0, fontSize: 12 }}>Il capocantiere vede le commesse in cui il campo «Capocantiere» è uguale al nome mostrato.</p>}
      </form>

      {modifica && <ModificaUtente u={modifica} onClose={() => setModifica(null)} />}

      {consegna && (
        <div className="ov">
          <div className="mo">
            <h3>Password temporanea di {consegna.u.nome}</h3>
            <p className="muted" style={{ margin: 0 }}>Consegnala di persona o per un canale sicuro. Non verrà più mostrata: al primo accesso {consegna.u.nome} dovrà sceglierne una nuova.</p>
            <dl className="kv"><dt>Nome utente</dt><dd className="mono">{consegna.u.username}</dd><dt>Password</dt><dd className="mono" style={{ fontSize: 17, fontWeight: 600 }}>{consegna.pwd}</dd></dl>
            <div className="row" style={{ justifyContent: "flex-end" }}>
              <button className="btn" onClick={() => navigator.clipboard?.writeText(consegna.pwd)}>Copia password</button>
              <button className="btn pri" onClick={() => setConsegna(null)}>Fatto</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function ModificaUtente({ u, onClose }: { u: RigaUtente; onClose: () => void }) {
  const { meta } = useApp();
  const azione = useAzione();
  const [f, setF] = useState({ nome: u.nome, ruolo: u.ruolo, attivo: u.attivo });
  const salva = async (e: React.FormEvent) => {
    e.preventDefault();
    if (await azione(() => api.patch(`/api/utenti/${u.id}`, f), "Utente aggiornato")) onClose();
  };
  return (
    <div className="ov" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <form className="mo" onSubmit={salva}>
        <h3>Modifica {u.username}</h3>
        <label className="fld"><span className="lbl">Nome mostrato</span><input required minLength={2} value={f.nome} onChange={(e) => setF({ ...f, nome: e.target.value })} /></label>
        <label className="fld"><span className="lbl">Ruolo</span>
          <select value={f.ruolo} onChange={(e) => setF({ ...f, ruolo: e.target.value as Ruolo })}>
            {(Object.keys(meta.ruoli) as Ruolo[]).map((r) => <option key={r} value={r}>{meta.ruoli[r].l}</option>)}
          </select></label>
        <label className="row" style={{ gap: 8 }}><input type="checkbox" checked={f.attivo} onChange={(e) => setF({ ...f, attivo: e.target.checked })} /> Utente attivo (può accedere)</label>
        {(f.ruolo !== u.ruolo || !f.attivo) && <div className="fmsg">{!f.attivo ? "L'utente verrà scollegato subito." : "Il nuovo ruolo vale dal prossimo accesso: l'utente verrà scollegato."}</div>}
        {u.ruolo === "capocantiere" && f.nome !== u.nome && <div className="note">Il nome verrà aggiornato anche sulle commesse di cui è capocantiere.</div>}
        <div className="row" style={{ justifyContent: "flex-end" }}><button type="button" className="btn" onClick={onClose}>Annulla</button><button className="btn pri">Salva</button></div>
      </form>
    </div>
  );
}
