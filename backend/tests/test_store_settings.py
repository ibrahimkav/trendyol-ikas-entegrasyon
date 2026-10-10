"""
Mağaza ayarları (Ayarlar → Kâr Hesaplama / Etiket & Barkod), mağaza adı değiştirme
ve Trendyol bağlantı testi. Trendyol'a gerçek çağrı yapılmaz (probe monkeypatch'lenir).
"""
from tests.conftest import make_store, auth_headers
from utils.store_settings import DEFAULTS, commission_rate_for


def test_defaults_and_partial_update_and_reset(client, temp_db):
    _, token = make_store(temp_db, "ss-a@test.local")
    h = auth_headers(token)
    r = client.get("/api/settings/store-settings", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["cargo_cost"] == DEFAULTS["cargo_cost"]
    assert body["label_discount_code"] == "TRENDYOL15"
    assert not any(body["is_customized"].values())

    r = client.put("/api/settings/store-settings", headers=h, json={
        "cargo_cost": 62.5, "label_discount_code": " yaz20 ", "label_website_url": "https://PenaltiDenim.com/",
        "category_commissions": {"Jean": 21.5, "  Pantolon ": "19"},
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["cargo_cost"] == 62.5
    assert body["label_discount_code"] == "YAZ20"
    assert body["label_website_url"] == "penaltidenim.com"
    assert body["category_commissions"] == {"Jean": 21.5, "Pantolon": 19.0}
    assert body["is_customized"]["cargo_cost"] and not body["is_customized"]["label_brand_text"]

    r = client.delete("/api/settings/store-settings/cargo_cost", headers=h)
    assert r.json()["cargo_cost"] == DEFAULTS["cargo_cost"] and not r.json()["is_customized"]["cargo_cost"]
    assert r.json()["label_discount_code"] == "YAZ20"  # diğer alanlar korunur


def test_validation_errors_are_plain_text(client, temp_db):
    _, token = make_store(temp_db, "ss-b@test.local")
    h = auth_headers(token)
    for payload in ({"cargo_cost": -1}, {"default_commission_rate": 80}, {"label_discount_code": "bad code!"},
                    {"label_discount_percent": 12.5}, {"label_website_url": "not a domain"},
                    {"category_commissions": {"Jean": 99}}, {"label_group_by_product": "yes"},
                    {"unknown_field": 1}, {"cargo_cost": "abc"}):
        r = client.put("/api/settings/store-settings", headers=h, json=payload)
        assert r.status_code == 422, payload
        assert isinstance(r.json()["detail"], str), payload
    # hiçbir şey yazılmamış olmalı
    assert not any(client.get("/api/settings/store-settings", headers=h).json()["is_customized"].values())


def test_settings_are_isolated_per_store(client, temp_db):
    _, ta = make_store(temp_db, "ss-iso-a@test.local")
    _, tb = make_store(temp_db, "ss-iso-b@test.local")
    client.put("/api/settings/store-settings", headers=auth_headers(ta), json={"cargo_cost": 10})
    assert client.get("/api/settings/store-settings", headers=auth_headers(tb)).json()["cargo_cost"] == DEFAULTS["cargo_cost"]
    assert client.get("/api/settings/store-settings").status_code in (401, 403)


def test_commission_rate_lookup_is_case_insensitive():
    s = {"default_commission_rate": 12.0, "category_commissions": {"Jean": 21.5, "İç Giyim": 18}}
    assert commission_rate_for(s, "jean") == 21.5
    assert commission_rate_for(s, "iç giyim") == 18
    assert commission_rate_for(s, "Gömlek") == 12.0
    assert commission_rate_for(s, None) == 12.0


def test_rename_store(client, temp_db):
    store_id, token = make_store(temp_db, "ss-rename@test.local")
    other_id, _ = make_store(temp_db, "ss-rename-other@test.local")
    h = auth_headers(token)
    r = client.patch(f"/api/settings/stores/{store_id}", headers=h, json={"store_name": "  Penaltı Denim "})
    assert r.status_code == 200 and r.json()["store_name"] == "Penaltı Denim"
    assert client.patch(f"/api/settings/stores/{store_id}", headers=h, json={"store_name": " "}).status_code == 422
    assert client.patch(f"/api/settings/stores/{other_id}", headers=h, json={"store_name": "x"}).status_code == 404


def test_trendyol_connection_test_records_result(client, temp_db, monkeypatch):
    import routers.settings as settings_router

    store_id, token = make_store(temp_db, "ss-probe@test.local")
    h = auth_headers(token)
    assert client.post(f"/api/settings/stores/{store_id}/credentials/trendyol/test", headers=h).status_code == 404
    client.post(f"/api/settings/stores/{store_id}/credentials", headers=h,
                json={"platform": "trendyol", "supplier_id": "123", "api_key": "kkkkkk", "api_secret": "ssssss"})

    calls = []

    def fake_probe(supplier_id, api_key, api_secret):
        calls.append((supplier_id, api_key, api_secret))
        return {"status": "auth_failed", "message": "reddedildi"}

    monkeypatch.setattr(settings_router, "_probe_trendyol", fake_probe)
    r = client.post(f"/api/settings/stores/{store_id}/credentials/trendyol/test", headers=h)
    assert r.status_code == 200 and r.json()["status"] == "auth_failed"
    assert calls == [("123", "kkkkkk", "ssssss")]
    creds = client.get(f"/api/settings/stores/{store_id}/credentials", headers=h).json()
    assert creds[0]["last_test"]["status"] == "auth_failed"
    # Anahtar güncellenince eski test sonucu silinir
    client.post(f"/api/settings/stores/{store_id}/credentials", headers=h,
                json={"platform": "trendyol", "supplier_id": "123", "api_key": "yyyyyy", "api_secret": "zzzzzz"})
    assert client.get(f"/api/settings/stores/{store_id}/credentials", headers=h).json()[0]["last_test"] is None
