"""
w3-automation-persist: AutomationRule artık salt bellekte DEĞİL, DB'de kalıcı.
Asıl iddia "process restart'ta kaybolmuyor" — bunu API üzerinden değil,
API'nin yazdığı satırı DOĞRUDAN yeni bir DB session'ıyla (temp_db["SessionLocal"])
sorgulayarak kanıtlıyoruz: TestClient'in kendi in-memory nesnesini değil,
gerçekten SQL tablosunu okuyoruz.
"""
from tests.conftest import make_store, auth_headers

RULE_BODY = {
    "name": "persist-test",
    "rule_type": "price_update",
    "enabled": True,
    "conditions": {"min_sales": 5},
    "actions": {"price_change_type": "fixed", "price_change_value": 2},
}


def test_create_rule_is_actually_a_db_row(client, temp_db):
    """API çağrısı sonrası satırın GERÇEKTEN automation_rules tablosunda
    olduğunu, TestClient'in kendi nesnesi değil DOĞRUDAN SQL sorgusuyla kanıtlar."""
    from database.models import AutomationRuleRecord

    store_id, token = make_store(temp_db, "auto-persist-a@test.local")
    resp = client.post("/api/automation/rules", json=RULE_BODY, headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    rule_id = resp.json()["rule"]["id"]

    db = temp_db["SessionLocal"]()
    try:
        rec = db.query(AutomationRuleRecord).filter(AutomationRuleRecord.id == rule_id).first()
        assert rec is not None
        assert rec.store_id == store_id
        assert rec.name == "persist-test"
        assert rec.enabled is True
    finally:
        db.close()


def test_rule_survives_a_fresh_db_session(client, temp_db):
    """'Restart'ı simüle eder: API'nin kullandığı session KAPANDIKTAN sonra
    TAMAMEN YENİ bir SessionLocal() ile aynı satırı okur — Python nesnesi
    değil, dosyadaki veri kalıcı mı diye bakar."""
    from database.models import AutomationRuleRecord

    store_id, token = make_store(temp_db, "auto-persist-b@test.local")
    resp = client.post("/api/automation/rules", json=RULE_BODY, headers=auth_headers(token))
    rule_id = resp.json()["rule"]["id"]

    # Yeni, bağımsız bir session — API çağrısının kullandığı session'dan FARKLI.
    fresh_db = temp_db["SessionLocal"]()
    try:
        rec = fresh_db.query(AutomationRuleRecord).filter(AutomationRuleRecord.id == rule_id).first()
        assert rec is not None
        assert rec.conditions_json == '{"min_sales": 5}' or __import__("json").loads(rec.conditions_json) == {"min_sales": 5}
    finally:
        fresh_db.close()


def test_update_and_toggle_persist_to_db(client, temp_db):
    from database.models import AutomationRuleRecord

    store_id, token = make_store(temp_db, "auto-persist-c@test.local")
    rule_id = client.post("/api/automation/rules", json=RULE_BODY, headers=auth_headers(token)).json()["rule"]["id"]

    updated_body = dict(RULE_BODY)
    updated_body["name"] = "renamed"
    updated_body["conditions"] = {"min_sales": 99}
    resp = client.put(f"/api/automation/rules/{rule_id}", json=updated_body, headers=auth_headers(token))
    assert resp.status_code == 200, resp.text

    resp = client.post(f"/api/automation/rules/{rule_id}/toggle", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    assert resp.json()["rule"]["enabled"] is False

    db = temp_db["SessionLocal"]()
    try:
        rec = db.query(AutomationRuleRecord).filter(AutomationRuleRecord.id == rule_id).first()
        assert rec.name == "renamed"
        assert rec.enabled is False
        import json
        assert json.loads(rec.conditions_json) == {"min_sales": 99}
    finally:
        db.close()


def test_delete_actually_removes_db_row(client, temp_db):
    from database.models import AutomationRuleRecord

    store_id, token = make_store(temp_db, "auto-persist-d@test.local")
    rule_id = client.post("/api/automation/rules", json=RULE_BODY, headers=auth_headers(token)).json()["rule"]["id"]

    resp = client.delete(f"/api/automation/rules/{rule_id}", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text

    db = temp_db["SessionLocal"]()
    try:
        rec = db.query(AutomationRuleRecord).filter(AutomationRuleRecord.id == rule_id).first()
        assert rec is None
    finally:
        db.close()
