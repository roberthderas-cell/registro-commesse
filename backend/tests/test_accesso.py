from conftest import PASSWORD, accedi

from app.auth import hash_password, verifica_password


def test_password_hash_non_reversibile():
    h = hash_password("una-password-lunga")
    assert h.startswith("scrypt$") and "una-password-lunga" not in h
    assert verifica_password("una-password-lunga", h)
    assert not verifica_password("un-altra-password", h)
    assert hash_password("una-password-lunga") != h  # sale diverso a ogni hash


def test_senza_accesso_tutto_chiuso(anonimo):
    for url in ("/api/meta", "/api/commesse", "/api/cruscotto", "/api/fonti", "/api/utenti"):
        assert anonimo.get(url).status_code == 401, url
    assert anonimo.get("/api/salute").status_code == 200


def test_login_logout(anonimo):
    r = anonimo.post("/api/accesso/login", json={"username": "admin", "password": "sbagliata"})
    assert r.status_code == 401 and r.json()["detail"] == "Nome utente o password non corretti"
    r = anonimo.post("/api/accesso/login", json={"username": "nessuno", "password": "sbagliata"})
    assert r.json()["detail"] == "Nome utente o password non corretti"  # stesso messaggio: non rivela chi esiste
    io = accedi(anonimo, "ADMIN ")  # maiuscole e spazi non contano
    assert io["ruolo"] == "admin"
    cookie = anonimo.cookies.get("rc_sessione")
    assert cookie and len(cookie) > 30
    assert anonimo.get("/api/meta").json()["ruolo"] == "admin"
    anonimo.post("/api/accesso/logout")
    assert anonimo.get("/api/meta").status_code == 401
    # il vecchio token non vale più nemmeno se qualcuno lo ha copiato
    anonimo.cookies.set("rc_sessione", cookie)
    assert anonimo.get("/api/meta").status_code == 401


def test_il_ruolo_viene_dall_utente_non_dalla_richiesta(anonimo):
    accedi(anonimo, "tecnico")
    assert anonimo.get("/api/cruscotto", headers={"X-Ruolo": "admin"}).status_code == 403
    assert anonimo.get("/api/meta").json()["ruolo"] == "tecnico"


def test_blocco_dopo_troppi_tentativi(anonimo):
    for _ in range(5):
        anonimo.post("/api/accesso/login", json={"username": "direzione", "password": "sbagliata"})
    r = anonimo.post("/api/accesso/login", json={"username": "direzione", "password": PASSWORD})
    assert r.status_code == 401 and "Troppi tentativi" in r.json()["detail"]


def test_ciclo_di_vita_utente(client):
    # l'amministrazione crea un capocantiere: riceve una password temporanea da consegnare
    r = client.post("/api/utenti", json={"username": "G.Rossi", "nome": "G. Rossi", "ruolo": "capocantiere"})
    assert r.status_code == 201, r.text
    nuovo = r.json()
    assert nuovo["username"] == "g.rossi" and nuovo["deve_cambiare_password"]
    temp = nuovo["password_temporanea"]
    assert client.post("/api/utenti", json={"username": "g.rossi", "nome": "Altro", "ruolo": "tecnico"}).status_code == 409

    # al primo accesso deve cambiare password prima di poter fare altro
    io = accedi(client, "g.rossi", temp)
    assert io["deve_cambiare_password"]
    assert client.get("/api/commesse").status_code == 403
    debole = client.post("/api/accesso/password", json={"attuale": temp, "nuova": "corta"})
    assert debole.status_code == 422
    assert client.post("/api/accesso/password", json={"attuale": temp, "nuova": "Cantiere-sicuro-2026"}).status_code == 200
    assert client.get("/api/commesse").json() == []  # nessuna commessa assegnata a G. Rossi

    # disattivato dall'amministrazione: la sessione aperta smette di funzionare
    accedi(client, "admin")
    admin_cookie = client.cookies.get("rc_sessione")
    accedi(client, "g.rossi", "Cantiere-sicuro-2026")
    sess_rossi = client.cookies.get("rc_sessione")
    client.cookies.set("rc_sessione", admin_cookie)
    assert client.patch(f"/api/utenti/{nuovo['id']}", json={"attivo": False}).status_code == 200
    client.cookies.set("rc_sessione", sess_rossi)
    assert client.get("/api/meta").status_code == 401
    r = client.post("/api/accesso/login", json={"username": "g.rossi", "password": "Cantiere-sicuro-2026"})
    assert r.status_code == 401 and "disattivato" in r.json()["detail"]


def test_rinomina_capocantiere_aggiorna_le_commesse(client):
    ferrari = next(u for u in client.get("/api/utenti").json() if u["username"] == "capocantiere")
    client.patch(f"/api/utenti/{ferrari['id']}", json={"nome": "Mario Ferrari"})
    assert client.get("/api/commesse/C-2026-018").json()["capo"] == "Mario Ferrari"
    accedi(client, "capocantiere")
    assert {c["cod"] for c in client.get("/api/commesse").json()} == {"C-2026-018", "C-2026-009"}


def test_resta_sempre_un_amministratore(client):
    admin = next(u for u in client.get("/api/utenti").json() if u["username"] == "admin")
    r = client.patch(f"/api/utenti/{admin['id']}", json={"ruolo": "direzione"})
    assert r.status_code == 409


def test_solo_admin_gestisce_utenti(client):
    accedi(client, "direzione")
    assert client.get("/api/utenti").status_code == 403
    assert client.post("/api/utenti", json={"username": "x.y", "nome": "X Y", "ruolo": "admin"}).status_code == 403


def test_reimposta_password(client):
    tec = next(u for u in client.get("/api/utenti").json() if u["username"] == "tecnico")
    temp = client.post(f"/api/utenti/{tec['id']}/reimposta-password").json()["password_temporanea"]
    r = client.post("/api/accesso/login", json={"username": "tecnico", "password": PASSWORD})
    assert r.status_code == 401
    assert accedi(client, "tecnico", temp)["deve_cambiare_password"]


def test_registro_con_nome_della_persona(client):
    accedi(client, "commerciale")
    client.post("/api/commesse/C-2026-018/varianti", json={"descr": "Prova", "importo": 1000})
    accedi(client, "admin")
    ultimo = client.get("/api/log?cod=C-2026-018").json()[0]
    assert ultimo["chi"] == "L. Bianchi" and ultimo["ruolo"] == "commerciale"


def test_freno_per_indirizzo_ip(anonimo):
    from app import auth
    auth._falliti_ip.clear()
    for i in range(auth.MAX_FALLITI_IP):
        anonimo.post("/api/accesso/login", json={"username": f"inventato{i}", "password": "x"})
    r = anonimo.post("/api/accesso/login", json={"username": "admin", "password": PASSWORD})
    assert r.status_code == 429
    auth._falliti_ip.clear()
    assert anonimo.post("/api/accesso/login", json={"username": "admin", "password": PASSWORD}).status_code == 200


def test_modello_csv_richiede_accesso(anonimo):
    assert anonimo.get("/api/fonti/modello/ordine.csv").status_code == 401
