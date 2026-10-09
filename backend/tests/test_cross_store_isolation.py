"""
Çapraz-mağaza izolasyonu — en değerli test grubu (w3-hardening'te 3 gerçek
sızıntı bulundu: images.py, barcode.py'nin ProductImageMapping sorgusu,
automation.py CRUD). Bu dosya o sızıntıların KAPANDIĞINI kilitler.

Trendyol'a hiçbir çağrı yapılmaz: automation.py CRUD ve product-images
endpoint'leri saf yerel DB işlemleridir; bağlı-olmayan-mağaza testleri
resolve_trendyol_creds'in daha canlı çağrı YAPILMADAN 409 fırlattığı ilk
adımda durur.
"""
import pytest

from tests.conftest import make_store, auth_headers


def test_automation_rules_isolated_read_and_write(client, temp_db):
    """w3-automation-leak'in kapandığını kilitler: automation_rules artık
    store_id ile anahtarlı, tek global dict DEĞİL."""
    _, token_a = make_store(temp_db, "auto-a@test.local")
    _, token_b = make_store(temp_db, "auto-b@test.local")

    body = {
        "name": "leak-test",
        "rule_type": "price_update",
        "enabled": True,
        "conditions": {"min_sales": 1},
        "actions": {"price_change_type": "fixed", "price_change_value": 1},
    }
    r = client.post("/api/automation/rules", json=body, headers=auth_headers(token_a))
    assert r.status_code == 200, r.text
    rule_id = r.json()["rule"]["id"]

    r = client.get("/api/automation/rules", headers=auth_headers(token_a))
    assert r.json()["total"] == 1

    # store B'nin listesi BOŞ olmalı — store A'nın kuralını GÖRMEMELİ.
    r = client.get("/api/automation/rules", headers=auth_headers(token_b))
    assert r.json() == {"rules": [], "total": 0}

    # store B doğrudan id ile de erişemez.
    r = client.get(f"/api/automation/rules/{rule_id}", headers=auth_headers(token_b))
    assert r.status_code == 404

    # store B silemez (yazma izolasyonu).
    r = client.delete(f"/api/automation/rules/{rule_id}", headers=auth_headers(token_b))
    assert r.status_code == 404

    # store A'da kural hâlâ duruyor (store B'nin denemesi etkisiz kaldı).
    r = client.get(f"/api/automation/rules/{rule_id}", headers=auth_headers(token_a))
    assert r.status_code == 200


def test_product_image_mapping_isolated(client, temp_db):
    """w2c-retrofit-remainder'da bulunan images.py/barcode.py ProductImageMapping
    sızıntısının AYNI tablosunu, güvenli/canlı-çağrısız bir yüzeyden (product_images.py
    CRUD) test eder — barcode.py'nin scan_order_barcode'u canlı Trendyol siparişi
    gerektirdiği için burada tetiklenemez, ama store_id filtresi AYNI modeldedir."""
    _, token_a = make_store(temp_db, "img-a@test.local")
    _, token_b = make_store(temp_db, "img-b@test.local")

    body = {"product_code": "LEAK-TEST-CODE", "image_urls": ["https://example.com/x.jpg"]}
    r = client.post("/api/product-images/", json=body, headers=auth_headers(token_a))
    assert r.status_code == 200, r.text

    r = client.get("/api/product-images/", headers=auth_headers(token_b))
    assert r.status_code == 200
    assert r.json() == []

    r = client.get("/api/product-images/search?product_code=LEAK-TEST-CODE", headers=auth_headers(token_b))
    assert r.status_code == 200
    assert r.json()["found"] is False

    r = client.get("/api/product-images/search?product_code=LEAK-TEST-CODE", headers=auth_headers(token_a))
    assert r.status_code == 200
    assert r.json()["found"] is True


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/api/cargo/"),
        ("GET", "/api/reports/daily"),
        ("GET", "/api/customers/"),
        ("GET", "/api/bulk/products"),
        ("GET", "/api/customer-qa/"),
    ],
)
def test_unconnected_store_gets_clean_409_not_500_or_leak(client, temp_db, method, path):
    """Bağlı olmayan bir mağaza için bu uçlar Trendyol'a HİÇ ÇAĞRI YAPMADAN
    (resolve_trendyol_creds ilk adımda durur) temiz 409 dönmeli — 500 değil,
    ve kesinlikle başka bir mağazanın verisi de değil (bu uçların hepsi canlı-API
    passthrough'tur, yerel DB'ye yazmaz — tek sızıntı yolu creds-resolution'ın
    atlanmasıdır, bu test tam onu kilitler)."""
    _, token = make_store(temp_db, f"unconnected-{hash(path)}@test.local")
    resp = client.request(method, path, headers=auth_headers(token))
    assert resp.status_code == 409, f"{method} {path} -> {resp.status_code}: {resp.text}"
