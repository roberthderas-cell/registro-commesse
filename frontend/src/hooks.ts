import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import { useApp } from "./App";

/** Carica un endpoint e lo ricarica quando cambiano ruolo o dati (versione). */
export function useDati<T>(path: string | null) {
  const { versione, ruolo } = useApp();
  const [dati, setDati] = useState<T | null>(null);
  const [errore, setErrore] = useState<string | null>(null);
  const carica = useCallback(() => {
    if (!path) return;
    api.get<T>(path).then((d) => { setDati(d); setErrore(null); }).catch((e) => setErrore(e.message));
  }, [path]);
  useEffect(() => { carica(); }, [carica, versione, ruolo]);
  return { dati, errore, setDati };
}

/** Esegue un'azione sul backend con messaggio di esito e aggiornamento delle viste. */
export function useAzione() {
  const { toast, aggiorna } = useApp();
  return async <T,>(fn: () => Promise<T>, ok?: string): Promise<T | undefined> => {
    try {
      const r = await fn();
      if (ok) toast(ok);
      aggiorna();
      return r;
    } catch (e) {
      toast((e as Error).message, "bad");
      return undefined;
    }
  };
}
