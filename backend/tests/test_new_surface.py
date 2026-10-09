"""
Yeni yüzey — w3-grouped-settings-api + w3-bulk-cost-entry sözleşmelerini kilitler.
Saf yerel DB işlemleridir, Trendyol'a hiçbir çağrı yapılmaz.
"""
import csv
import io

from tests.conftest import make_store, auth_headers


def _csv_bytes(rows: list) -> bytes:
    """Türkçe Excel formatında (UTF-8-BOM, ';' ayraç) CSV bayt dizisi üretir.
    Elle noktalı virgül saymaktan kaçınmak için csv.writer kullanılır."""
    out = io.StringIO()
    writer = csv.writer(out, delimiter=";")
    writer.writerows(rows)
    return out.getvalue().encode("utf-8-sig")


HEADER = [
    "content_id", "product_id", "urun_adi", "kategori", "bedenler",
    "varyant_sayisi", "mevcut_maliyet", "mevcut_desi", "yeni_maliyet", "yeni_desi",
]


def _make_products(temp_db, store_id):
    from database.models import Product

    db = temp_db["SessionLocal"]()
    try:
        db.add_all([
            # content_id=CID1: 3 varyant, maliyetler KARIŞIK (10, 20, 10) -> cost_mixed
            Product(store_id=store_id, product_id="V1", product_name="Ürün A", category="Cat",
                    barcode="V1", current_price=100.0, default_cost=10.0, desi=1.0, content_id="CID1"),
            Product(store_id=store_id, product_id="V2", product_name="Ürün A", category="Cat",
                    barcode="V2", current_price=100.0, default_cost=20.0, desi=1.0, content_id="CID1"),
            Product(store_id=store_id, product_id="V3", product_name="Ürün A", category="Cat",
                    barcode="V3", current_price=100.0, default_cost=10.0, desi=1.0, content_id="CID1"),
            # content_id yok -> kendi tekil grubu
            Product(store_id=store_id, product_id="SOLO1", product_name="Ürün B", category="Cat",
                    barcode="SOLO1", current_price=50.0, default_cost=5.0, desi=0.5, content_id=None),
        ])
        db.commit()
    finally:
        db.close()


def test_grouped_settings_groups_by_content_id(client, temp_db):
    """53 satırın 397'ye değil, content_id'ye göre gruplandığı sözleşmesinin
    genel kuralını (N varyant -> 1 grup, content_id yoksa kendi tekil grubu) kilitler."""
    store_id, token = make_store(temp_db, "grouped@test.local")
    _make_products(temp_db, store_id)

    resp = client.get("/api/products/settings/grouped", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["count"] == 2  # CID1 grubu + SOLO1 tekil grubu, 4 Product satırı DEĞİL

    cid1 = next(g for g in data["products"] if g["content_id"] == "CID1")
    assert cid1["variant_count"] == 3
    assert cid1["cost_mixed"] is True  # 10,20,10 karışık
    assert cid1["desi_mixed"] is False  # 1,1,1 aynı
    assert set(cid1["variant_product_ids"]) == {"V1", "V2", "V3"}

    solo = next(g for g in data["products"] if g["content_id"] is None)
    assert solo["variant_count"] == 1
    assert solo["variant_product_ids"] == ["SOLO1"]


def test_group_put_updates_all_variants(client, temp_db):
    from database.models import Product

    store_id, token = make_store(temp_db, "group-put@test.local")
    _make_products(temp_db, store_id)

    resp = client.put(
        "/api/products/settings/group/CID1",
        json={"default_cost": 77.5, "desi": 3.0},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"updated_count": 3, "content_id": "CID1"}

    db = temp_db["SessionLocal"]()
    try:
        rows = db.query(Product).filter(Product.store_id == store_id, Product.content_id == "CID1").all()
        assert len(rows) == 3
        assert all(p.default_cost == 77.5 and p.desi == 3.0 for p in rows)
        # SOLO1'e dokunulmadı
        solo = db.query(Product).filter(Product.store_id == store_id, Product.product_id == "SOLO1").first()
        assert solo.default_cost == 5.0
    finally:
        db.close()


def test_group_put_unknown_content_id_returns_404(client, temp_db):
    _, token = make_store(temp_db, "group-404@test.local")
    resp = client.put(
        "/api/products/settings/group/does-not-exist",
        json={"default_cost": 1, "desi": 1},
        headers=auth_headers(token),
    )
    assert resp.status_code == 404


def test_template_csv_format(client, temp_db):
    """hive/docs/bulk-cost-csv.md sözleşmesi: UTF-8-BOM, ';' ayraç, kolon sırası."""
    store_id, token = make_store(temp_db, "template@test.local")
    _make_products(temp_db, store_id)

    resp = client.get("/api/products/settings/template.csv", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    raw = resp.content
    assert raw.startswith(b"\xef\xbb\xbf"), "UTF-8 BOM eksik"

    text = raw.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text), delimiter=";")
    rows = list(reader)
    assert rows[0] == HEADER
    assert len(rows) == 3  # başlık + 2 grup (CID1 + SOLO1)


def test_bulk_dry_run_does_not_write(client, temp_db):
    from database.models import Product

    store_id, token = make_store(temp_db, "bulk-dry@test.local")
    _make_products(temp_db, store_id)

    csv_bytes = _csv_bytes([
        HEADER,
        ["CID1", "V1", "Ürün A", "Cat", "V1,V2,V3", "3", "10,00", "1,00", "99,99", "5,00"],
    ])

    resp = client.post(
        "/api/products/settings/bulk?dry_run=true",
        files={"file": ("test.csv", csv_bytes, "text/csv")},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["will_update"] == 1
    assert data["error_count"] == 0
    assert data["preview"][0]["new_cost"] == 99.99

    db = temp_db["SessionLocal"]()
    try:
        v1 = db.query(Product).filter(Product.store_id == store_id, Product.product_id == "V1").first()
        assert v1.default_cost == 10.0, "dry_run YAZMIŞ olamaz"
    finally:
        db.close()


def test_bulk_write_applies_to_group_and_reports_errors(client, temp_db):
    """Kısmi-alan-güncelleme + hata kodları (UNKNOWN_KEY, INVALID_NUMBER) TEK
    yüklemede kilitlenir; hatalı satırlar yazılmaz, geçerli satır yazılır."""
    from database.models import Product

    store_id, token = make_store(temp_db, "bulk-write@test.local")
    _make_products(temp_db, store_id)

    csv_bytes = _csv_bytes([
        HEADER,
        ["CID1", "V1", "Ürün A", "Cat", "V1,V2,V3", "3", "10,00", "1,00", "99,99", "5,00"],
        ["", "UNKNOWN-999", "", "", "", "", "", "", "10", "1"],
        ["", "SOLO1", "Ürün B", "Cat", "SOLO1", "1", "5,00", "0,50", "abc", ""],
    ])

    resp = client.post(
        "/api/products/settings/bulk?dry_run=false",
        files={"file": ("test.csv", csv_bytes, "text/csv")},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["updated_groups"] == 1
    assert data["updated_variants"] == 3
    assert data["error_count"] == 2
    codes = {e["error_code"] for e in data["errors"]}
    assert codes == {"UNKNOWN_KEY", "INVALID_NUMBER"}

    db = temp_db["SessionLocal"]()
    try:
        rows = db.query(Product).filter(Product.store_id == store_id, Product.content_id == "CID1").all()
        assert all(p.default_cost == 99.99 and p.desi == 5.0 for p in rows)
        solo = db.query(Product).filter(Product.store_id == store_id, Product.product_id == "SOLO1").first()
        assert solo.default_cost == 5.0, "INVALID_NUMBER satırı yazılmamalıydı"
    finally:
        db.close()


def test_bulk_encoding_and_delimiter_tolerance(client, temp_db):
    """Türkçe Excel gerçeği: windows-1254 + ',' ayraç + tırnaklı virgül-ondalık
    da kabul edilmeli (dosya UTF-8-BOM/';' olmasa da sessizce patlamamalı)."""
    store_id, token = make_store(temp_db, "bulk-encoding@test.local")
    _make_products(temp_db, store_id)

    content = (
        'content_id,product_id,urun_adi,kategori,bedenler,varyant_sayisi,mevcut_maliyet,mevcut_desi,yeni_maliyet,yeni_desi\n'
        ',SOLO1,Test,Cat,SOLO1,1,"5,00","0,50","12,34","0,75"\n'
    )
    csv_bytes = content.encode("windows-1254")

    resp = client.post(
        "/api/products/settings/bulk?dry_run=true",
        files={"file": ("test_cp1254.csv", csv_bytes, "text/csv")},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["error_count"] == 0
    assert data["will_update"] == 1
    assert data["preview"][0]["new_cost"] == 12.34
    assert data["preview"][0]["new_desi"] == 0.75
