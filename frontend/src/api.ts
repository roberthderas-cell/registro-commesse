// Accesso alle API del backend. L'utente è riconosciuto dal cookie di sessione (HttpOnly) impostato al login:
// il browser lo invia da solo, il codice JavaScript non lo vede.

export type Ruolo = "admin" | "direzione" | "commerciale" | "tecnico" | "cantiere" | "capocantiere";

export interface Io { id: number; username: string; nome: string; ruolo: Ruolo; deve_cambiare_password: boolean }

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

// Chiamata quando il backend risponde 401 (sessione scaduta o chiusa altrove): l'app torna al login
let suNonAutenticato: () => void = () => {};
export const quandoNonAutenticato = (fn: () => void) => { suNonAutenticato = fn; };

async function call<T>(method: string, path: string, body?: unknown): Promise<T> {
  const init: RequestInit = { method, credentials: "same-origin", headers: {} };
  if (body instanceof FormData) init.body = body;
  else if (body !== undefined) {
    init.body = JSON.stringify(body);
    (init.headers as Record<string, string>)["Content-Type"] = "application/json";
  }
  const r = await fetch(path, init);
  if (!r.ok) {
    let msg = r.statusText;
    try {
      const j = await r.json();
      msg = typeof j.detail === "string" ? j.detail : Array.isArray(j.detail) ? j.detail.map((d: { msg: string }) => d.msg).join("; ") : JSON.stringify(j.detail);
    } catch {
      /* risposta non JSON */
    }
    if (r.status === 401 && !path.startsWith("/api/accesso/")) suNonAutenticato();
    throw new ApiError(r.status, msg);
  }
  return r.json();
}

export const api = {
  get: <T>(p: string) => call<T>("GET", p),
  post: <T>(p: string, b?: unknown) => call<T>("POST", p, b),
  put: <T>(p: string, b?: unknown) => call<T>("PUT", p, b),
  patch: <T>(p: string, b?: unknown) => call<T>("PATCH", p, b),
  del: <T>(p: string) => call<T>("DELETE", p),
};

function localStorageGet(k: string): string | null {
  try {
    return localStorage.getItem(k);
  } catch {
    return null;
  }
}
function localStorageSet(k: string, v: string) {
  try {
    localStorage.setItem(k, v);
  } catch {
    /* archiviazione non disponibile */
  }
}
export { localStorageGet, localStorageSet };
