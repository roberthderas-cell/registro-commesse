import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, getRuolo, localStorageGet, localStorageSet, setRuolo, type Ruolo } from "./api";
import type { Meta } from "./types";
import Cruscotto from "./views/Cruscotto";
import Pipeline from "./views/Pipeline";
import Commesse from "./views/Commesse";
import Sdi from "./views/Sdi";
import Fonti from "./views/Fonti";
import Registro from "./views/Registro";
import Impostazioni from "./views/Impostazioni";

export type View = "cruscotto" | "pipeline" | "commesse" | "sdi" | "fonti" | "log" | "impostazioni";

const VIEWS: { id: View; l: string; ruoli: Ruolo[] | null; icon: string }[] = [
  { id: "cruscotto", l: "Cruscotto", ruoli: ["admin", "direzione"], icon: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/>' },
  { id: "pipeline", l: "Pipeline", ruoli: null, icon: '<rect x="3" y="3" width="5" height="18" rx="1"/><rect x="10" y="3" width="5" height="12" rx="1"/><rect x="17" y="3" width="4" height="8" rx="1"/>' },
  { id: "commesse", l: "Commesse", ruoli: null, icon: '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>' },
  { id: "sdi", l: "Fatture SDI", ruoli: ["admin"], icon: '<path d="M3 13l3-8h12l3 8v6H3zM3 13h5l1 3h6l1-3h5"/>' },
  { id: "fonti", l: "Fonti dati", ruoli: ["admin"], icon: '<path d="M12 16V4M7 9l5-5 5 5M4 20h16"/>' },
  { id: "log", l: "Registro attività", ruoli: ["admin", "direzione"], icon: '<path d="M8 6h13M8 12h13M8 18h13M3.5 6h.01M3.5 12h.01M3.5 18h.01"/>' },
  { id: "impostazioni", l: "Impostazioni", ruoli: ["admin"], icon: '<path d="M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12"/><circle cx="16" cy="6" r="2"/><circle cx="10" cy="12" r="2"/><circle cx="18" cy="18" r="2"/>' },
];
const GRUPPI: [string, View[]][] = [["Controllo", ["cruscotto", "pipeline", "commesse"]], ["Contabilità", ["sdi", "fonti"]], ["Sistema", ["log", "impostazioni"]]];

interface Ctx {
  meta: Meta;
  versione: number; // cresce a ogni modifica: le viste ricaricano i dati
  aggiorna: () => void;
  apri: (cod: string, tab?: string) => void;
  vai: (v: View) => void;
  toast: (m: string, tipo?: "good" | "bad") => void;
  vede: (k: "r" | "c" | "m") => boolean;
  ruolo: Ruolo;
}
const AppCtx = createContext<Ctx>(null as unknown as Ctx);
export const useApp = () => useContext(AppCtx);

type Tema = "system" | "light" | "dark";

export default function App() {
  const [ruolo, setR] = useState<Ruolo>(getRuolo());
  const [meta, setMeta] = useState<Meta | null>(null);
  const [errore, setErrore] = useState<string | null>(null);
  const [view, setView] = useState<View>((localStorageGet("rc-view") as View) || "cruscotto");
  const [sel, setSel] = useState<{ cod: string | null; tab: string }>({ cod: null, tab: "tempo" });
  const [versione, setVersione] = useState(0);
  const [msg, setMsg] = useState<{ m: string; tipo: string } | null>(null);
  const [tema, setTema] = useState<Tema>((localStorageGet("rc-tema") as Tema) || "system");

  useEffect(() => {
    if (tema === "system") document.documentElement.removeAttribute("data-theme");
    else document.documentElement.setAttribute("data-theme", tema);
    localStorageSet("rc-tema", tema);
  }, [tema]);

  useEffect(() => {
    api.get<Meta>("/api/meta").then((m) => { setMeta(m); setErrore(null); }).catch((e) => setErrore(String(e.message || e)));
  }, [ruolo, versione]);

  const visibili = VIEWS.filter((v) => !v.ruoli || v.ruoli.includes(ruolo));
  const attiva = visibili.some((v) => v.id === view) ? view : visibili[0].id;
  useEffect(() => localStorageSet("rc-view", attiva), [attiva]);

  const toast = useCallback((m: string, tipo: "good" | "bad" = "good") => {
    setMsg({ m, tipo });
    window.setTimeout(() => setMsg((x) => (x?.m === m ? null : x)), 4200);
  }, []);

  const ctx = useMemo<Ctx | null>(() => meta && {
    meta, versione, ruolo, toast,
    aggiorna: () => setVersione((v) => v + 1),
    apri: (cod, tab) => { setSel((s) => ({ cod, tab: tab || s.tab })); setView("commesse"); },
    vai: (v) => setView(v),
    vede: (k) => meta.vede.includes(k),
  }, [meta, versione, ruolo, toast]);

  const cambiaRuolo = (r: Ruolo) => { setRuolo(r); setR(r); };

  if (errore) return <div className="gut" style={{ padding: 40 }}><div className="panel pad"><h2>Backend non raggiungibile</h2><p className="muted">{errore}</p><p className="muted">Avvia il backend con <code>./avvia.sh</code> oppure <code>uvicorn app.main:app</code> nella cartella backend.</p></div></div>;
  if (!ctx) return <div className="gut muted" style={{ padding: 40 }}>Caricamento…</div>;

  const titolo = VIEWS.find((v) => v.id === attiva)!.l;
  return (
    <AppCtx.Provider value={ctx}>
      <div className="shell">
        <aside className="side" aria-label="Navigazione">
          <div className="brand">
            <div className="logo empty" title="Logo aziendale">BOVEMA</div>
            <div className="bt"><h1>Registro Commesse</h1><div className="sub">Dal contratto all'incasso</div></div>
          </div>
          <nav className="nav" aria-label="Sezioni">
            {GRUPPI.map(([g, ids]) => {
              const items = visibili.filter((v) => ids.includes(v.id));
              if (!items.length) return null;
              return (
                <div key={g}>
                  <div className="ng">{g}</div>
                  {items.map((v) => (
                    <button key={v.id} aria-current={attiva === v.id} onClick={() => setView(v.id)} title={v.l}>
                      <svg viewBox="0 0 24 24" aria-hidden="true" dangerouslySetInnerHTML={{ __html: v.icon }} />
                      {v.l}
                    </button>
                  ))}
                </div>
              );
            })}
          </nav>
          <div className="side-roles">
            <div className="roles" aria-label="Ruolo">
              <span className="rl">Ruolo attivo</span>
              {(Object.keys(meta!.ruoli) as Ruolo[]).map((k) => (
                <button key={k} className="rchip" style={{ ["--rc" as string]: `var(--r-${k})` }} aria-pressed={ruolo === k} onClick={() => cambiaRuolo(k)}>
                  <span className="av">{meta!.ruoli[k].i}</span>{meta!.ruoli[k].l}
                </button>
              ))}
            </div>
          </div>
        </aside>
        <div className="mainc">
          <header className="topbar">
            <div className="crumb"><i style={{ ["--rc" as string]: `var(--r-${ruolo})` }} /><span>{meta!.utente}</span><span>/</span><b>{titolo}</b></div>
            <div className="tools">
              <button className="bbtn" onClick={() => setTema(tema === "system" ? "light" : tema === "light" ? "dark" : "system")}>
                ◐ {tema === "system" ? "Sistema" : tema === "light" ? "Chiaro" : "Scuro"}
              </button>
            </div>
          </header>
          <main className="gut" id="app">
            {attiva === "cruscotto" && <Cruscotto />}
            {attiva === "pipeline" && <Pipeline />}
            {attiva === "commesse" && <Commesse sel={sel.cod} tab={sel.tab} onSel={(cod, tab) => setSel((s) => ({ cod, tab: tab || s.tab }))} />}
            {attiva === "sdi" && <Sdi />}
            {attiva === "fonti" && <Fonti />}
            {attiva === "log" && <Registro />}
            {attiva === "impostazioni" && <Impostazioni />}
          </main>
          <footer className="gut statusbar"><span>Registro Commesse · dati al {meta!.oggi.split("-").reverse().join("/")}</span><span>Ruolo: {meta!.ruoli[ruolo].l}</span></footer>
        </div>
      </div>
      {msg && <div className="toast" role="status" style={{ ["--tc" as string]: msg.tipo === "bad" ? "var(--bad)" : "var(--good)" }}><i />{msg.m}</div>}
    </AppCtx.Provider>
  );
}
