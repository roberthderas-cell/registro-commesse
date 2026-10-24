import type { Ruolo } from "./api";

export interface Fase { l: string; st: number[]; v: string }
export interface DocSpec { k: string; l: string; fase: number; chi: string }
export interface Meta {
  stati: string[];
  fasi: Fase[];
  cats: string[];
  docs: DocSpec[];
  ruoli: Record<Ruolo, { l: string; i: string }>;
  trig: Record<string, string>;
  oggi: string;
  vede: ("r" | "c" | "m")[];
  utente: string;
  ruolo: Ruolo;
  cfg: Record<string, number | string>;
}

export interface Voce { k: string; budget: number; imp: number; sost: number; eac: number; residuo: number }
export interface Kpi {
  ore: number; avanz: number;
  ricavo?: number; var_appr?: number; fatturato?: number; incassato?: number; credito?: number; maturato?: number; wip?: number;
  budget?: number; impegnato?: number; sostenuto?: number; eac?: number; mo?: number; cats?: Voce[];
  margine?: number; marg_pct?: number; c2c?: number;
}

export interface Sintesi {
  cod: string; cliente: string; oggetto: string; sistema: string; cantiere: string; commerciale: string; capo: string;
  contratto: string | null; stato: number; fase: string; bloccata: boolean; collaudo_ok: boolean; fonte: string;
  n_avvisi_doc: number; n_ordini_aut: number; kpi: Kpi;
}

export interface Ordine {
  id: string; fornitore: string; categoria: string; descr: string; importo?: number; data: string; stato: string;
  consegna: string | null; nota?: string | null; fonte?: string; fatturato?: number;
}
export interface FatturaPassiva { id: number; num: string; fornitore: string; ordine: string | null; categoria: string; importo: number; data: string; pagamento: string | null; fonte: string }
export interface Rata {
  id: number; codice: string; descr: string; importo: number; trigger: string; fattura_num: string | null; fattura_data: string | null;
  fattura_scad: string | null; incasso_data: string | null; stato: { t: string; cls: string; fb?: boolean; late?: number };
}
export interface Dettaglio extends Sintesi {
  collaudo_data: string | null; piva_cliente: string | null; blocco: string | null; puo_avanzare: boolean;
  varianti: { id: number; codice: string; descr: string; importo: number | null; stato: string; da: string; data: string }[];
  rapportini: { id: number; data: string; chi: string; ore: number; avanz: number; nota: string; fonte: string }[];
  documenti: { k: string; l: string; fase: number; chi: string; file?: string; data?: string; caricato_da?: string }[];
  ordini: Ordine[];
  fp?: FatturaPassiva[];
  piano?: Rata[];
}

export interface Avviso { sev: "bad" | "warn" | "info"; cod: string | null; tit: string; det: string; go: { view?: string; tab?: string } }

export interface EsitoImport {
  righe: { riga: string; tipo?: string; esito: string; m: string }[];
  ok: number; errori: number; riepilogo: Record<string, number>;
}
