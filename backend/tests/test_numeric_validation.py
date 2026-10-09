"""
w3-manual-numeric-validation (Phyllis'in UX incelemesi, bulgu #3): tekil PUT,
grup PUT, toplu CSV ve toplu fiyat uçlarının hepsinde negatif/sayı-olmayan/aşırı
büyük değerlerin reddedildiğini, geçerli değerlerin YAZILDIĞINI kilitler.
Saf yerel DB işlemleridir, Trendyol'a hiçbir çağrı yapılmaz.
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


# ---------------------------------------------------------------------------
# Tekil PUT /settings/{product_id}
# ---------------------------------------------------------------------------

def test_single_negative_cost_rejected_with_422(client, temp_db):
    store_id, token = make_store(temp_db, "num-single-neg@test.local")
    _make_product(temp_db, store_id, product_id="P1", cost=10.0)

    resp = client.put(
        "/api/products/settings/P1",
        json={"default_cost": -5.0, "desi": 1.0},
        headers=auth_headers(token),
    )
    assert resp.status_code == 422, resp.text
    assert "negatif" in str(resp.json())


def test_single_huge_cost_rejected_with_422(client, temp_db):
    store_id, token = make_store(temp_db, "num-single-huge@test.local")
    _make_product(temp_db, store_id, product_id="P1", cost=10.0)

    resp = client.put(
        "/api/products/settings/P1",
        json={"default_cost": 50_000_000.0, "desi": 1.0},
        headers=auth_headers(token),
    )
    assert resp.status_code == 422, resp.text


def test_single_non_numeric_cost_rejected_with_422(client, temp_db):
    store_id, token = make_store(temp_db, "num-single-text@test.local")
    _make_product(temp_db, store_id, product_id="P1", cost=10.0)

    resp = client.put(
        "/api/products/settings/P1",
        json={"default_cost": "abc", "desi": 1.0},
        headers=auth_headers(token),
    )
    assert resp.status_code == 422, resp.text


def test_single_zero_cost_is_valid(client, temp_db):
    """Sıfır maliyet GEÇERLİ olmalı — kullanıcı bugün TÜM maliyetleri sıfırladı,
    bu değeri reddetmek yeni bir regresyon olurdu."""
    store_id, token = make_store(temp_db, "num-single-zero@test.local")
    _make_product(temp_db, store_id, product_id="P1", cost=10.0)

    resp = client.put(
        "/api/products/settings/P1",
        json={"default_cost": 0.0, "desi": 0.0},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text


def test_single_valid_value_still_written(client, temp_db):
    store_id, token = make_store(temp_db, "num-single-valid@test.local")
    _make_product(temp_db, store_id, product_id="P1", cost=10.0)

    resp = client.put(
        "/api/products/settings/P1",
        json={"default_cost": 175.5, "desi": 2.5},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["default_cost"] == 175.5


# ---------------------------------------------------------------------------
# Grup PUT /settings/group/{content_id}
# ---------------------------------------------------------------------------

def test_group_negative_desi_rejected_with_422(client, temp_db):
    store_id, token = make_store(temp_db, "num-group-neg@test.local")
    _make_product(temp_db, store_id, product_id="V1", content_id="CID1", cost=10.0)
    _make_product(temp_db, store_id, product_id="V2", content_id="CID1", cost=10.0)

    resp = client.put(
        "/api/products/settings/group/CID1",
        json={"default_cost": 20.0, "desi": -1.0},
        headers=auth_headers(token),
    )
    assert resp.status_code == 422, resp.text


def test_group_huge_desi_rejected_with_422(client, temp_db):
    store_id, token = make_store(temp_db, "num-group-huge@test.local")
    _make_product(temp_db, store_id, product_id="V1", content_id="CID1", cost=10.0)

    resp = client.put(
        "/api/products/settings/group/CID1",
        json={"default_cost": 20.0, "desi": 999_999.0},
        headers=auth_headers(token),
    )
    assert resp.status_code == 422, resp.text


# ---------------------------------------------------------------------------
# Toplu CSV POST /settings/bulk (mevcut NEGATIVE_VALUE + yeni OUT_OF_RANGE)
# ---------------------------------------------------------------------------

def _csv_bytes(rows):
    import csv
    import io

    out = io.StringIO()
    writer = csv.writer(out, delimiter=";")
    writer.writerows(rows)
    return out.getvalue().encode("utf-8-sig")


HEADER = ["content_id", "product_id", "urun_adi", "kategori", "bedenler",
          "varyant_sayisi", "mevcut_maliyet", "mevcut_desi", "yeni_maliyet", "yeni_desi"]


def test_bulk_csv_negative_value_still_rejected(client, temp_db):
    """Regresyon kilidi: bu kural DAHA ÖNCE de vardı, paylaşılan yardımcıya
    taşınırken davranış (error_code dahil) bozulmamalı."""
    store_id, token = make_store(temp_db, "num-bulk-neg@test.local")
    _make_product(temp_db, store_id, product_id="P1", cost=5.0)

    rows = [HEADER, ["", "P1", "Ürün", "Cat", "P1", "1", "5,00", "1,00", "-10,00", "1,00"]]
    resp = client.post(
        "/api/products/settings/bulk?dry_run=false",
        files={"file": ("t.csv", _csv_bytes(rows), "text/csv")},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["error_count"] == 1
    assert data["errors"][0]["error_code"] == "NEGATIVE_VALUE"


def test_bulk_csv_out_of_range_value_rejected(client, temp_db):
    store_id, token = make_store(temp_db, "num-bulk-range@test.local")
    _make_product(temp_db, store_id, product_id="P1", cost=5.0)

    rows = [HEADER, ["", "P1", "Ürün", "Cat", "P1", "1", "5,00", "1,00", "50000000,00", "1,00"]]
    resp = client.post(
        "/api/products/settings/bulk?dry_run=false",
        files={"file": ("t.csv", _csv_bytes(rows), "text/csv")},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["error_count"] == 1
    assert data["errors"][0]["error_code"] == "OUT_OF_RANGE"


# ---------------------------------------------------------------------------
# Toplu fiyat POST /financial/profit-margin-list/bulk-price-update
# ---------------------------------------------------------------------------

def test_bulk_price_update_negative_price_rejected_with_422(client, temp_db):
    store_id, token = make_store(temp_db, "num-price-neg@test.local")
    _make_product(temp_db, store_id, product_id="P1", cost=10.0, price=100.0)

    resp = client.post(
        "/api/financial/profit-margin-list/bulk-price-update",
        json={"items": [{"product_id": "P1", "new_price": -50.0}]},
        headers=auth_headers(token),
    )
    assert resp.status_code == 422, resp.text


def test_bulk_price_update_huge_price_rejected_with_422(client, temp_db):
    store_id, token = make_store(temp_db, "num-price-huge@test.local")
    _make_product(temp_db, store_id, product_id="P1", cost=10.0, price=100.0)

    resp = client.post(
        "/api/financial/profit-margin-list/bulk-price-update",
        json={"items": [{"product_id": "P1", "new_price": 50_000_000.0}]},
        headers=auth_headers(token),
    )
    assert resp.status_code == 422, resp.text


def test_bulk_price_update_valid_price_still_written(client, temp_db):
    store_id, token = make_store(temp_db, "num-price-valid@test.local")
    _make_product(temp_db, store_id, product_id="P1", cost=10.0, price=100.0)

    resp = client.post(
        "/api/financial/profit-margin-list/bulk-price-update",
        json={"items": [{"product_id": "P1", "new_price": 149.9}]},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["updated"][0]["new_price"] == 149.9
