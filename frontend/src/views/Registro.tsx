import { useState } from "react";
import { useApp } from "../App";
import { fts } from "../fmt";
import { useDati } from "../hooks";

const COL: Record<string, string> = { Amministrazione: "--r-admin", Direzione: "--r-direzione", Commerciale: "--r-commerciale", "Ufficio tecnico": "--r-tecnico",
  "Ufficio cantiere": "--r-cantiere", Capocantiere: "--r-capocantiere", "Sistema SDI": "--r-sdi", Banca: "--r-banca" };

export default function Registro() {
  const { apri } = useApp();
  const { dati } = useDati<{ id: number; ts: string; chi: string; ruolo: string; cod: string | null; t: string }[]>("/api/log");
  const [q, setQ] = useState("");
  if (!dati) return <div className="muted">Caricamento…</div>;
  const ql = q.trim().toLowerCase();
  return (
    <div className="stack">
      <div className="hello"><div className="pgt"><h2>Registro attività</h2><p>Chi ha fatto cosa, su quale commessa, e da quale fonte sono arrivati i dati</p></div></div>
      <input className="search" style={{ maxWidth: 360 }} type="search" placeholder="Filtra per testo, commessa o autore" value={q} onChange={(e) => setQ(e.target.value)} />
      <section className="panel feed" style={{ maxHeight: "none" }}>
        {dati.filter((l) => !ql || `${l.t} ${l.cod} ${l.chi}`.toLowerCase().includes(ql)).map((l) => (
          <div key={l.id} className="fi" style={{ ["--tc" as string]: `var(${l.ruolo ? `--r-${l.ruolo}` : COL[l.chi] || "--muted"})` }}>
            <span className="ic">{l.chi.slice(0, 2).toUpperCase()}</span>
            <div><b>{l.t}</b><div>{l.chi}{l.cod && <> · <button className="btn sm" style={{ padding: "0 6px" }} onClick={() => apri(l.cod!, "registro")}>{l.cod}</button></>}</div></div>
            <span className="tm">{fts(l.ts)}</span>
          </div>
        ))}
      </section>
    </div>
  );
}
