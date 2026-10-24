// Accesso alle API del backend. Il ruolo scelto nell'interfaccia viaggia nell'intestazione X-Ruolo
// (provvisorio, finché non c'è un login vero).

export type Ruolo = "admin" | "direzione" | "commerciale" | "tecnico" | "cantiere" | "capocantiere";

let ruoloCorrente: Ruolo = (localStorageGet("rc-ruolo") as Ruolo) || "admin";
export const setRuolo = (r: Ruolo) => {
  ruoloCorrente = r;
  localStorageSet("rc-ruolo", r);
};
export const getRuolo = () => ruoloCorrente;

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function call<T>(method: string, path: string, body?: unknown): Promise<T> {
  const init: RequestInit = { method, headers: { "X-Ruolo": ruoloCorrente } };
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
      msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
    } catch {
      /* risposta non JSON */
    }
    throw new ApiError(r.status, msg);
  }
  return r.json();
}

export const api = {
  get: <T>(p: string) => call<T>("GET", p),
  post: <T>(p: string, b?: unknown) => call<T>("POST", p, b),
  put: <T>(p: string, b?: unknown) => call<T>("PUT", p, b),
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
