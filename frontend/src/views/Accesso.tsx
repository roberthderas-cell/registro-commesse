import { useState } from "react";
import { api, type Io } from "../api";

function Cornice({ children }: { children: React.ReactNode }) {
  return (
    <div className="acc-wrap">
      <div className="acc">
        <div className="acc-brand"><div className="logo empty">BOVEMA</div><div><h1>Registro Commesse</h1><div className="sub">Dal contratto all'incasso</div></div></div>
        {children}
      </div>
    </div>
  );
}

export function Login({ onEntra }: { onEntra: (io: Io) => void }) {
  const [username, setU] = useState("");
  const [password, setP] = useState("");
  const [errore, setErrore] = useState<string | null>(null);
  const [attesa, setAttesa] = useState(false);
  const entra = async (e: React.FormEvent) => {
    e.preventDefault();
    setAttesa(true);
    setErrore(null);
    try {
      onEntra(await api.post<Io>("/api/accesso/login", { username, password }));
    } catch (err) {
      setErrore((err as Error).message);
      setP("");
    } finally {
      setAttesa(false);
    }
  };
  return (
    <Cornice>
      <form className="stack" style={{ gap: 14 }} onSubmit={entra}>
        <h2 style={{ fontSize: 19 }}>Accedi</h2>
        <label className="fld"><span className="lbl">Nome utente</span>
          <input autoFocus required autoComplete="username" autoCapitalize="none" spellCheck={false} value={username} onChange={(e) => setU(e.target.value)} /></label>
        <label className="fld"><span className="lbl">Password</span>
          <input required type="password" autoComplete="current-password" value={password} onChange={(e) => setP(e.target.value)} /></label>
        {errore && <div className="fmsg" role="alert">{errore}</div>}
        <button className="btn pri" disabled={attesa} style={{ padding: "9px 12px" }}>{attesa ? "Accesso…" : "Accedi"}</button>
        <p className="muted" style={{ margin: 0, fontSize: 12 }}>Password dimenticata? Chiedi all'amministrazione di reimpostarla.</p>
      </form>
    </Cornice>
  );
}

/** Cambio password: obbligatorio al primo accesso, oppure scelto dall'utente dal menu. */
export function CambioPassword({ io, obbligatorio, onFatto, onAnnulla }: { io: Io; obbligatorio: boolean; onFatto: (io: Io) => void; onAnnulla?: () => void }) {
  const [f, setF] = useState({ attuale: "", nuova: "", conferma: "" });
  const [errore, setErrore] = useState<string | null>(null);
  const [attesa, setAttesa] = useState(false);
  const salva = async (e: React.FormEvent) => {
    e.preventDefault();
    if (f.nuova !== f.conferma) return setErrore("Le due password nuove non coincidono");
    setAttesa(true);
    setErrore(null);
    try {
      onFatto(await api.post<Io>("/api/accesso/password", { attuale: f.attuale, nuova: f.nuova }));
    } catch (err) {
      setErrore((err as Error).message);
    } finally {
      setAttesa(false);
    }
  };
  const modulo = (
    <form className="stack" style={{ gap: 14 }} onSubmit={salva}>
      <h2 style={{ fontSize: 19 }}>{obbligatorio ? `Benvenuto, ${io.nome}` : "Cambia password"}</h2>
      {obbligatorio && <p className="muted" style={{ margin: 0 }}>Prima di continuare scegli una password personale al posto di quella temporanea che hai ricevuto.</p>}
      <input type="text" autoComplete="username" value={io.username} readOnly hidden />
      <label className="fld"><span className="lbl">{obbligatorio ? "Password temporanea" : "Password attuale"}</span>
        <input required type="password" autoComplete="current-password" value={f.attuale} onChange={(e) => setF({ ...f, attuale: e.target.value })} /></label>
      <label className="fld"><span className="lbl">Nuova password</span>
        <input required type="password" autoComplete="new-password" minLength={10} value={f.nuova} onChange={(e) => setF({ ...f, nuova: e.target.value })} />
        <small className="muted">Almeno 10 caratteri, senza il nome utente. Una frase di più parole va benissimo.</small></label>
      <label className="fld"><span className="lbl">Ripeti la nuova password</span>
        <input required type="password" autoComplete="new-password" value={f.conferma} onChange={(e) => setF({ ...f, conferma: e.target.value })} /></label>
      {errore && <div className="fmsg" role="alert">{errore}</div>}
      <div className="row" style={{ justifyContent: "flex-end" }}>
        {onAnnulla && <button type="button" className="btn" onClick={onAnnulla}>{obbligatorio ? "Esci" : "Annulla"}</button>}
        <button className="btn pri" disabled={attesa}>Salva password</button>
      </div>
    </form>
  );
  if (obbligatorio) return <Cornice>{modulo}</Cornice>;
  return <div className="ov" onClick={(e) => e.target === e.currentTarget && onAnnulla?.()}><div className="mo">{modulo}</div></div>;
}
