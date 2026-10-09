"""
w3-write-audit-trail: maliyet/desi/fiyat yazan uçların değişim geçmişi
bırakması + store izolasyonu + gerçek "değişiklik yok" durumunda kayıt
ÜRETMEMESİ. Saf yerel DB işlemleridir, Trendyol'a hiçbir çağrı yapılmaz.
"""
from tests.conftest import make_store, auth_headers


def _make_product(temp_db, store_id, product_id="P1", content_id=None, cost=10.0, desi=1.0, price=100.0):
    from database.models import Product

    db = temp_db["SessionLocal"]()
    try:
        db.add(Product(
            store_id=store_id, product_id=product_id, product_name="Ürün",
            category="Cat", barcode=product_id, current_price=price,
            default_cost=cost, desi=desi, content_id=content_id,
        ))
        db.commit()
    finally:
        db.close()


def test_single_update_records_old_and_new_value(client, temp_db):
    store_id, token = make_store(temp_db, "hist-single@test.local")
    _make_product(temp_db, store_id, product_id="P1", cost=10.0, desi=1.0)

    resp = client.put(
        "/api/products/settings/P1",
        json={"default_cost": 25.0, "desi": 2.5},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text

    hist = client.get("/api/products/change-history", headers=auth_headers(token)).json()
    changes = {c["field"]: c for c in hist["changes"]}
    assert changes["default_cost"]["old_value"] == 10.0
    assert changes["default_cost"]["new_value"] == 25.0
    assert changes["default_cost"]["source"] == "single"
    assert changes["desi"]["old_value"] == 1.0
    assert changes["desi"]["new_value"] == 2.5


def test_group_update_records_one_row_per_variant(client, temp_db):
    store_id, token = make_store(temp_db, "hist-group@test.local")
    _make_product(temp_db, store_id, product_id="V1", content_id="CID1", cost=10.0, desi=1.0)
    _make_product(temp_db, store_id, product_id="V2", content_id="CID1", cost=10.0, desi=1.0)

    resp = client.put(
        "/api/products/settings/group/CID1",
        json={"default_cost": 40.0, "desi": 4.0},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text

    hist = client.get("/api/products/change-history?source=group", headers=auth_headers(token)).json()
    assert hist["count"] == 4  # 2 varyant x (default_cost + desi)
    product_ids = {c["product_id"] for c in hist["changes"]}
    assert product_ids == {"V1", "V2"}
    assert all(c["old_value"] == 10.0 or c["old_value"] == 1.0 for c in hist["changes"])


def test_bulk_csv_write_records_history_with_correct_old_value(client, temp_db):
    import csv
    import io

    store_id, token = make_store(temp_db, "hist-bulk@test.local")
    _make_product(temp_db, store_id, product_id="P1", content_id=None, cost=5.0, desi=0.5)

    out = io.StringIO()
    writer = csv.writer(out, delimiter=";")
    writer.writerow(["content_id", "product_id", "urun_adi", "kategori", "bedenler",
                      "varyant_sayisi", "mevcut_maliyet", "mevcut_desi", "yeni_maliyet", "yeni_desi"])
    writer.writerow(["", "P1", "Ürün", "Cat", "P1", "1", "5,00", "0,50", "12,00", "1,50"])
    csv_bytes = out.getvalue().encode("utf-8-sig")

    resp = client.post(
        "/api/products/settings/bulk?dry_run=false",
        files={"file": ("template.csv", csv_bytes, "text/csv")},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text

    hist = client.get("/api/products/change-history?source=bulk_csv", headers=auth_headers(token)).json()
    changes = {c["field"]: c for c in hist["changes"]}
    assert changes["default_cost"]["old_value"] == 5.0
    assert changes["default_cost"]["new_value"] == 12.0
    assert changes["desi"]["old_value"] == 0.5
    assert changes["desi"]["new_value"] == 1.5


def test_writing_same_value_does_not_create_history_row(client, temp_db):
    """Gerçek bir değişiklik yoksa (aynı değer tekrar yazılırsa) kayıt ÜRETİLMEMELİ —
    aksi halde hacim gereksiz şişer (kart, 3b maddesi)."""
    store_id, token = make_store(temp_db, "hist-noop@test.local")
    _make_product(temp_db, store_id, product_id="P1", cost=10.0, desi=1.0)

    resp = client.put(
        "/api/products/settings/P1",
        json={"default_cost": 10.0, "desi": 1.0},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text

    hist = client.get("/api/products/change-history", headers=auth_headers(token)).json()
    assert hist["count"] == 0


def test_change_history_isolated_between_stores(client, temp_db):
    store_a, token_a = make_store(temp_db, "hist-a@test.local")
    store_b, token_b = make_store(temp_db, "hist-b@test.local")
    _make_product(temp_db, store_a, product_id="P1", cost=10.0)
    _make_product(temp_db, store_b, product_id="P1", cost=10.0)

    resp = client.put(
        "/api/products/settings/P1",
        json={"default_cost": 99.0, "desi": 1.0},
        headers=auth_headers(token_a),
    )
    assert resp.status_code == 200, resp.text

    hist_a = client.get("/api/products/change-history", headers=auth_headers(token_a)).json()
    hist_b = client.get("/api/products/change-history", headers=auth_headers(token_b)).json()
    assert hist_a["count"] == 1
    assert hist_b["count"] == 0


def test_bulk_price_update_records_current_price_history(client, temp_db):
    store_id, token = make_store(temp_db, "hist-price@test.local")
    _make_product(temp_db, store_id, product_id="P1", cost=10.0, price=100.0)

    resp = client.post(
        "/api/financial/profit-margin-list/bulk-price-update",
        json={"items": [{"product_id": "P1", "new_price": 149.9}]},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text

    hist = client.get("/api/products/change-history?source=bulk_price_update", headers=auth_headers(token)).json()
    assert hist["count"] == 1
    change = hist["changes"][0]
    assert change["field"] == "current_price"
    assert change["old_value"] == 100.0
    assert change["new_value"] == 149.9
