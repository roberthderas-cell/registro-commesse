import { useState } from "react";
import { api } from "../api";
import { useApp } from "../App";
import { useAzione } from "../hooks";

const CAMPI: { k: string; l: string; d: string }[] = [
  { k: "costoOra", l: "Costo orario manodopera (€/h)", d: "Valorizza le ore dei rapportini nella voce Manodopera interna" },
  { k: "sogliaMarg", l: "Soglia di margine (%)", d: "Sotto questa soglia la commessa viene segnalata" },
  { k: "sogliaGap", l: "Scarto cantiere/costi (punti %)", d: "Cantiere più avanti dei costi registrati: possibili fatture mancanti" },
  { k: "ggPag", l: "Giorni di pagamento clienti", d: "Scadenza proposta per le fatture emesse" },
  { k: "ggForn", l: "Giorni di pagamento fornitori", d: "Per lo scadenzario dei pagamenti" },
];

export default function Impostazioni() {
  const { meta } = useApp();
  const azione = useAzione();
  const [cfg, setCfg] = useState<Record<string, string>>(Object.fromEntries(Object.entries(meta.cfg).map(([k, v]) => [k, String(v)])));
  return (
    <div className="stack">
      <div className="hello"><div className="pgt"><h2>Impostazioni</h2><p>Parametri di calcolo usati da cruscotto, avvisi e importazioni</p></div></div>
      <form className="panel pad stack" onSubmit={(e) => {
        e.preventDefault();
        azione(() => api.put("/api/impostazioni", { ...Object.fromEntries(CAMPI.map((c) => [c.k, Number(cfg[c.k])])), resp: cfg.resp }), "Impostazioni salvate");
      }}>
        <div className="cfg">
          {CAMPI.map((c) => (
            <label key={c.k} className="fld"><span className="lbl">{c.l}</span><input type="number" step="any" value={cfg[c.k]} onChange={(e) => setCfg({ ...cfg, [c.k]: e.target.value })} /><small>{c.d}</small></label>
          ))}
          <label className="fld"><span className="lbl">Responsabile controllo di gestione</span><input value={cfg.resp} onChange={(e) => setCfg({ ...cfg, resp: e.target.value })} /></label>
        </div>
        <div className="row" style={{ justifyContent: "flex-end" }}><button className="btn pri">Salva impostazioni</button></div>
      </form>
    </div>
  );
}
