"""
w3-price-writeback-preview (Dilim 1 — salt okuma). GET /api/pricing/writeback-preview
mevcut calculate_suggested_price()'ı (utils/pricing_calc.py) store'un ürünlerine
uygular ve SONUÇ DÖNER — hiçbir yazma yapmaz. Trendyol'a hiçbir çağrı yapılmaz
(bu uç resolve_trendyol_creds'i hiç ÇAĞIRMIYOR — tasarım gereği, aşağıdaki
test bunu doğruluyor).
"""
from tests.conftest import make_store, auth_headers


def _make_product(temp_db, store_id, product_id, cost, price, category="Jeans"):
    from database.models import Product
    db = temp_db["SessionLocal"]()
    try:
        db.add(Product(
            store_id=store_id, product_id=product_id, product_name=f"Ürün {product_id}",
            category=category, barcode=product_id, current_price=price, default_cost=cost,
        ))
        db.commit()
    finally:
        db.close()


def _dump_products(temp_db):
    from database.models import Product
    db = temp_db["SessionLocal"]()
    try:
        rows = db.query(Product).order_by(Product.id).all()
        return [(r.id, r.store_id, r.product_id, r.current_price, r.default_cost) for r in rows]
    finally:
        db.close()


def test_preview_writes_nothing(client, temp_db):
    """En önemli kanıt: önce/sonra Product tablosu (özellikle current_price)
    BİREBİR AYNI kalmalı."""
    store_id, token = make_store(temp_db, "wbp-nowrite@test.local")
    _make_product(temp_db, store_id, "P1", cost=300.0, price=1000.0)

    before = _dump_products(temp_db)

    resp = client.get(
        "/api/pricing/writeback-preview",
        params={"target_mode": "percent", "target_value": 30},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["count"] == 1
    assert data["preview"][0]["product_id"] == "P1"
    assert data["preview"][0]["current_price"] == 1000.0
    assert data["preview"][0]["suggested_price"] > 0
    assert data["preview"][0]["diff"] == round(data["preview"][0]["suggested_price"] - 1000.0, 2)

    after = _dump_products(temp_db)
    assert before == after, "writeback-preview HİÇBİR ŞEY YAZMAMALI ama Product tablosu değişti"


def test_preview_skips_products_without_cost(client, temp_db):
    store_id, token = make_store(temp_db, "wbp-skip@test.local")
    _make_product(temp_db, store_id, "WITH-COST", cost=100.0, price=500.0)
    _make_product(temp_db, store_id, "NO-COST", cost=0.0, price=500.0)

    resp = client.get(
        "/api/pricing/writeback-preview",
        params={"target_mode": "percent", "target_value": 20},
        headers=auth_headers(token),
    )
    data = resp.json()
    assert data["count"] == 1
    assert data["preview"][0]["product_id"] == "WITH-COST"
    assert data["skipped_count"] == 1
    assert data["skipped"][0]["product_id"] == "NO-COST"


def test_preview_isolated_between_stores(client, temp_db):
    """A'nın ürünü B'nin prova listesinde görünmemeli."""
    store_a, token_a = make_store(temp_db, "wbp-a@test.local")
    _, token_b = make_store(temp_db, "wbp-b@test.local")
    _make_product(temp_db, store_a, "A-ONLY", cost=200.0, price=800.0)

    resp_a = client.get(
        "/api/pricing/writeback-preview",
        params={"target_mode": "percent", "target_value": 25},
        headers=auth_headers(token_a),
    )
    assert resp_a.json()["count"] == 1

    resp_b = client.get(
        "/api/pricing/writeback-preview",
        params={"target_mode": "percent", "target_value": 25},
        headers=auth_headers(token_b),
    )
    assert resp_b.json()["count"] == 0


def test_preview_works_for_unconnected_store(client, temp_db, monkeypatch):
    """KASITLI SAPMA (dispatch'in varsayımından, gerekçesiyle): bu uç
    resolve_trendyol_creds'i hiç ÇAĞIRMIYOR (tasarım gereği — sadece yerel
    Product.default_cost/current_price kullanıyor). Bağlı olmayan bir mağaza
    için 409 DEĞİL, normal 200 dönmesi DOĞRU davranıştır — Trendyol bağlantısı
    olmadan da yerel maliyet verisiyle fiyat provası yapılabilmeli. Bunu ayrıca
    resolve_trendyol_creds'in bu istek sırasında HİÇ ÇAĞRILMADIĞINI monkeypatch
    ile de kanıtlıyoruz (çağrılsaydı test patlardı)."""
    import routers.pricing as pricing_module

    def _boom(*a, **kw):
        raise AssertionError("resolve_trendyol_creds ÇAĞRILDI — bu uç Trendyol'a bağımlı olmamalıydı")

    monkeypatch.setattr(pricing_module, "resolve_trendyol_creds", _boom)

    store_id, token = make_store(temp_db, "wbp-unconnected@test.local")
    _make_product(temp_db, store_id, "P1", cost=100.0, price=400.0)

    resp = client.get(
        "/api/pricing/writeback-preview",
        params={"target_mode": "amount", "target_value": 50},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["count"] == 1
