from conftest import accedi, carica


def esiti(res):
    return [(x["esito"], x["m"]) for x in res["righe"]]


def test_indicatori_come_nel_prototipo(client):
    d = client.get("/api/commesse/C-2026-018").json()
    assert round(d["kpi"]["margine"]) == 58400
    assert d["blocco"] == "Il cantiere deve dichiarare l'avanzamento al 100%"
    cr = client.get("/api/cruscotto").json()
    assert cr["kpi"]["portafoglio"] == 778500
    assert len(cr["avvisi"]) == 11


def test_ruoli(client):
    accedi(client, "capocantiere")
    capo = client.get("/api/commesse").json()
    assert {c["cod"] for c in capo} == {"C-2026-018", "C-2026-009"}
    assert "ricavo" not in capo[0]["kpi"] and "margine" not in capo[0]["kpi"]
    accedi(client, "tecnico")
    assert client.get("/api/cruscotto").status_code == 403
    accedi(client, "admin")
    assert client.post("/api/commesse/C-2026-018/avanza").status_code == 409  # cantiere non al 100%


def test_excel_anteprima_non_scrive_e_salva_una_volta(client):
    prima = len(client.get("/api/commesse/C-2026-022").json()["ordini"])
    res = carica(client, "tabelle", "ordini.csv", tipo="ordine")
    assert res["ok"] == 2 and res["errori"] == 1
    assert "inesistente" in res["righe"][-1]["m"]
    assert len(client.get("/api/commesse/C-2026-022").json()["ordini"]) == prima
    carica(client, "tabelle", "ordini.csv", tipo="ordine", salva=True)
    assert len(client.get("/api/commesse/C-2026-022").json()["ordini"]) == prima + 1
    # seconda importazione dello stesso file: nessun doppione
    di_nuovo = carica(client, "tabelle", "ordini.csv", tipo="ordine", salva=True)
    assert di_nuovo["riepilogo"].get("creato") is None
    assert len(client.get("/api/commesse/C-2026-022").json()["ordini"]) == prima + 1
    # 38.500 € stanno nel residuo Materiali di C-2026-027 (44.000 €): l'ordine non va in autorizzazione
    o = next(o for o in client.get("/api/commesse/C-2026-027").json()["ordini"] if o["id"] == "ODA-26-0160")
    assert o["stato"] == "Ordinato"


def test_rapportini_da_excel(client):
    carica(client, "tabelle", "rapportini.csv", tipo="rapportino", salva=True)
    assert client.get("/api/commesse/C-2026-018").json()["kpi"]["avanz"] == 81


def test_fatturapa_passiva_va_in_casella_sdi_e_si_registra(client):
    res = carica(client, "fatturapa", "fattura_passiva_IT09876540151_00A1B.xml", salva=True)
    assert res["righe"][0]["esito"] == "creata", esiti(res)
    f = next(x for x in client.get("/api/sdi").json() if x["num"] == "31/26")
    assert f["importo"] == 11000 and f["rif_ordine"] == "ODA-26-0144" and f["rif_commessa"] == "C-2026-018"
    r = client.post(f"/api/sdi/{f['id']}/registra", json={"commessa": "C-2026-018"})
    assert r.status_code == 200, r.text
    assert all(x["num"] != "31/26" for x in client.get("/api/sdi").json())
    fp = client.get("/api/commesse/C-2026-018").json()["fp"]
    assert any(x["num"] == "31/26" and x["categoria"] == "Posa e subappalti" for x in fp)


def test_fatturapa_attiva_si_abbina_alla_rata(client):
    res = carica(client, "fatturapa", "fattura_attiva_IT01234560157_00F01.xml", salva=True)
    assert res["righe"][0]["esito"] == "abbinata", esiti(res)
    r1 = client.get("/api/commesse/C-2026-027").json()["piano"][0]
    assert r1["fattura_num"] == "FA 2026/205" and r1["fattura_scad"] == "2026-12-21"


def test_banca_camt_e_csv(client):
    res = carica(client, "banca", "camt053.xml", salva=True)
    assert [x["esito"] for x in res["righe"]] == ["abbinato", "non abbinato"]
    assert client.get("/api/commesse/C-2026-031").json()["piano"][0]["incasso_data"] == "2026-10-23"
    res = carica(client, "banca", "estratto_conto.csv", salva=True)
    assert [x["esito"] for x in res["righe"]] == ["abbinato", "abbinato", "non abbinato"], esiti(res)
    c9 = client.get("/api/commesse/C-2026-009").json()
    assert c9["piano"][1]["incasso_data"] == "2026-10-21"
    pagata = next(f for f in client.get("/api/commesse/C-2026-018").json()["fp"] if f["num"] == "27/26")
    assert pagata["pagamento"] == "2026-10-22"
    # stesso estratto una seconda volta: niente doppi incassi
    assert {x["esito"] for x in carica(client, "banca", "camt053.xml", salva=True)["righe"]} == {"invariato"}


def test_sincronizzazione_erp(client):
    fonti = client.get("/api/fonti").json()
    assert fonti["erp"][0]["nome"] == "gestionale_demo"
    res = client.post("/api/fonti/erp/gestionale_demo?salva=true").json()
    assert res["errori"] == 0, esiti(res)
    ordini = {o["id"]: o for o in client.get("/api/commesse/C-2026-031").json()["ordini"]}
    assert ordini["ODA-26-0172"]["stato"] == "Consegnato"
    assert any(f["num"] == "FT 2026/470" for f in client.get("/api/commesse/C-2026-031").json()["fp"])
    # rilanciare la sincronizzazione aggiorna, non duplica
    res2 = client.post("/api/fonti/erp/gestionale_demo?salva=true").json()
    assert "creato" not in res2["riepilogo"] and "creata" not in res2["riepilogo"]


def test_flusso_manuale_ordine_oltre_budget_e_autorizzazione(client):
    accedi(client, "cantiere")
    r = client.post("/api/commesse/C-2026-027/ordini", json={"fornitore": "Metalfer Lombarda S.r.l.", "categoria": "Trasporti", "importo": 5000})
    assert r.status_code == 200, r.text
    o = next(o for o in r.json()["ordini"] if o["fornitore"] == "Metalfer Lombarda S.r.l.")
    assert o["stato"] == "Autorizzazione richiesta"
    assert client.post(f"/api/commesse/C-2026-027/ordini/{o['id']}/autorizza").status_code == 403
    accedi(client, "direzione")
    ok = client.post(f"/api/commesse/C-2026-027/ordini/{o['id']}/autorizza")
    assert next(x for x in ok.json()["ordini"] if x["id"] == o["id"])["stato"] == "Ordinato"
