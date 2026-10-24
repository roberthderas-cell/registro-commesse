import { useState } from "react";
import { api } from "../api";
import { useApp } from "../App";
import { useAzione } from "../hooks";

export default function NuovaCommessa({ onClose }: { onClose: () => void }) {
  const { meta, apri } = useApp();
  const azione = useAzione();
  const [f, setF] = useState({ cliente: "", oggetto: "", sistema: "", cantiere: "", ricavo: "" });
  const [budget, setBudget] = useState<Record<string, string>>({});
  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement>) => setF({ ...f, [k]: e.target.value });
  const num = (s: string) => Number(String(s).replace(/\./g, "").replace(",", ".")) || 0;

  const salva = async (e: React.FormEvent) => {
    e.preventDefault();
    const ricavo = num(f.ricavo);
    const r = await azione(() => api.post<{ cod: string }>("/api/commesse", {
      ...f, ricavo,
      budget: Object.fromEntries(meta.cats.map((k) => [k, num(budget[k] || "0")])),
      piano: [
        { descr: "Anticipo 30% alla firma", importo: Math.round(ricavo * 0.3 * 100) / 100, trigger: "contratto" },
        { descr: "SAL 1, 40%", importo: Math.round(ricavo * 0.4 * 100) / 100, trigger: "avanz50" },
        { descr: "Saldo 30% a collaudo", importo: Math.round((ricavo - Math.round(ricavo * 0.3 * 100) / 100 - Math.round(ricavo * 0.4 * 100) / 100) * 100) / 100, trigger: "collaudo" },
      ],
    }), "Commessa creata");
    if (r) { onClose(); apri(r.cod, "riepilogo"); }
  };

  return (
    <div className="ov" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <form className="mo" onSubmit={salva}>
        <h3>Nuova commessa</h3>
        <label className="fld"><span className="lbl">Cliente</span><input required value={f.cliente} onChange={set("cliente")} /></label>
        <label className="fld"><span className="lbl">Oggetto</span><input value={f.oggetto} onChange={set("oggetto")} /></label>
        <div className="two">
          <label className="fld"><span className="lbl">Sistema</span><input value={f.sistema} onChange={set("sistema")} placeholder="ENFC, SEFFC, PDS…" /></label>
          <label className="fld"><span className="lbl">Cantiere</span><input value={f.cantiere} onChange={set("cantiere")} /></label>
        </div>
        <label className="fld"><span className="lbl">Valore del contratto (€)</span><input required inputMode="decimal" value={f.ricavo} onChange={set("ricavo")} /></label>
        <div className="lbl">Budget dei costi</div>
        <div className="two">
          {meta.cats.map((k) => (
            <label className="fld" key={k}><span className="muted" style={{ fontSize: 12 }}>{k}</span>
              <input inputMode="decimal" value={budget[k] || ""} onChange={(e) => setBudget({ ...budget, [k]: e.target.value })} /></label>
          ))}
        </div>
        <p className="muted" style={{ margin: 0, fontSize: 12 }}>Piano di fatturazione proposto: 30% alla firma, 40% al 50% di cantiere, 30% a collaudo.</p>
        <div className="row" style={{ justifyContent: "flex-end" }}>
          <button type="button" className="btn" onClick={onClose}>Annulla</button>
          <button className="btn pri">Crea commessa</button>
        </div>
      </form>
    </div>
  );
}
