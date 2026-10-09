"""
ikas → fatura taslağı: dosya ayrıştırma, KDV ayrıştırma, indirim yorumu ve
/api/invoices uçlarının mağaza izolasyonu. E-Faturam'a çağrı yapılmaz (henüz yok).
"""
import io

import pandas as pd

from tests.conftest import make_store, auth_headers
from utils.ikas_import import (
    UNKNOWN_TCKN,
    build_invoice_draft,
    match_columns,
    parse_amount,
    parse_orders,
    read_table,
)


def _xlsx(rows):
    buf = io.BytesIO()
    pd.DataFrame(rows).to_excel(buf, index=False)
    return buf.getvalue()


# Satır başına bir ürün; sipariş bilgileri her satırda tekrarlanır
SAMPLE_ROWS = [
    {
        "Sipariş No": "1001", "Sipariş Tarihi": "05.10.2026", "Müşteri Adı": "Ayşe", "Müşteri Soyadı": "Yılmaz",
        "E-Posta": "ayse@example.com", "Telefon": "5551112233", "TC Kimlik No": "12345678901",
        "Fatura Adresi": "Atatürk Cad. No:1", "Fatura İlçe": "Kadıköy", "Fatura İl": "İstanbul",
        "Ürün Adı": "Boyfriend Kot Pantolon", "Varyant": "30/32", "Barkod": "2302G30", "Adet": "1",
        "Birim Fiyat": "1.100,00", "Kargo Ücreti": "0", "Sipariş Toplamı": "1.650,00", "Bilinmeyen Kolon": "x",
    },
    {
        "Sipariş No": "1001", "Sipariş Tarihi": "05.10.2026", "Müşteri Adı": "Ayşe", "Müşteri Soyadı": "Yılmaz",
        "E-Posta": "ayse@example.com", "Telefon": "5551112233", "TC Kimlik No": "12345678901",
        "Fatura Adresi": "Atatürk Cad. No:1", "Fatura İlçe": "Kadıköy", "Fatura İl": "İstanbul",
        "Ürün Adı": "Basic Tişört", "Varyant": "M", "Barkod": "TS-M", "Adet": "1",
        "Birim Fiyat": "550,00", "Kargo Ücreti": "0", "Sipariş Toplamı": "1.650,00", "Bilinmeyen Kolon": "y",
    },
    {
        "Sipariş No": "1002", "Sipariş Tarihi": "06.10.2026", "Müşteri Adı": "Mehmet", "Müşteri Soyadı": "Kaya",
        "E-Posta": "", "Telefon": "", "TC Kimlik No": "",
        "Fatura Adresi": "", "Fatura İlçe": "", "Fatura İl": "Ankara",
        "Ürün Adı": "Mom Jean", "Varyant": "", "Barkod": "MJ1", "Adet": "2",
        "Birim Fiyat": "500", "Kargo Ücreti": "49,90", "Sipariş Toplamı": "1.049,90", "Bilinmeyen Kolon": "",
    },
]


def test_parse_amount_formats():
    assert parse_amount("1.234,56 ₺") == 1234.56
    assert parse_amount("1,234.56") == 1234.56
    assert parse_amount("1234.5") == 1234.5
    assert parse_amount("49,90") == 49.9
    assert parse_amount("1.234.567") == 1234567
    assert parse_amount("%10") == 10
    assert parse_amount("") is None
    assert parse_amount(None) is None
    assert parse_amount(12.0) == 12.0


def test_match_columns_turkish_and_english():
    mapping, ignored = match_columns(["Sipariş No", "MÜŞTERİ ADI", "Ürün Adı", "Adet", "Weird"])
    assert mapping["order_number"] == "Sipariş No"
    # soyad kolonu yokken "Müşteri Adı" tam ad sayılır
    assert mapping["full_name"] == "MÜŞTERİ ADI"
    assert ignored == ["Weird"]

    mapping, _ = match_columns(["Order Number", "First Name", "Last Name", "Product Name", "Quantity"])
    assert mapping["order_number"] == "Order Number"
    assert mapping["first_name"] == "First Name" and mapping["last_name"] == "Last Name"


def test_parse_orders_groups_lines_and_keeps_ids_as_text():
    df = read_table("orders.xlsx", _xlsx(SAMPLE_ROWS))
    parsed = parse_orders(df)
    assert parsed["missing_fields"] == []
    assert parsed["ignored_columns"] == ["Bilinmeyen Kolon"]
    orders = {o["order_number"]: o for o in parsed["orders"]}
    assert set(orders) == {"1001", "1002"}
    assert len(orders["1001"]["lines"]) == 2
    assert orders["1001"]["fields"]["identity_number"] == "12345678901"
    assert orders["1001"]["fields"]["order_total"] == 1650.0


def test_csv_semicolon_turkish_encoding():
    text = "Sipariş No;Ad Soyad;Ürün Adı;Adet;Birim Fiyat\n2001;Ali Veli;Gömlek;1;299,90\n"
    df = read_table("orders.csv", text.encode("cp1254"))
    parsed = parse_orders(df)
    assert parsed["orders"][0]["fields"]["full_name"] == "Ali Veli"
    assert parsed["orders"][0]["lines"][0]["unit_price"] == 299.9


def test_draft_vat_split_and_ready():
    parsed = parse_orders(read_table("o.xlsx", _xlsx(SAMPLE_ROWS)))
    order = next(o for o in parsed["orders"] if o["order_number"] == "1001")
    draft = build_invoice_draft(order, product_vat_rate=10, shipping_vat_rate=20)
    assert draft["ready"], draft["errors"]
    assert draft["buyer_type"] == "bireysel"
    assert draft["tax_id"] == "12345678901"
    assert draft["totals"]["gross"] == 1650.0
    # 1650 / 1.10 = 1500 net, 150 KDV
    assert draft["totals"]["net"] == 1500.0
    assert draft["totals"]["vat"] == 150.0
    assert draft["lines"][0]["name"] == "Boyfriend Kot Pantolon - 30/32"
    assert draft["warnings"] == []


def test_draft_missing_info_and_shipping_line():
    parsed = parse_orders(read_table("o.xlsx", _xlsx(SAMPLE_ROWS)))
    order = next(o for o in parsed["orders"] if o["order_number"] == "1002")
    draft = build_invoice_draft(order, product_vat_rate=10, shipping_vat_rate=20)
    assert not draft["ready"]
    assert "Fatura adresi eksik." in draft["errors"]
    assert "İlçe eksik." in draft["errors"]
    assert draft["tax_id"] == UNKNOWN_TCKN
    shipping = draft["lines"][-1]
    assert shipping["name"] == "Kargo Bedeli" and shipping["vat_rate"] == 20
    assert draft["totals"]["gross"] == 1049.9

    fixed = build_invoice_draft(order, {"address": "Kızılay Mah. 5", "district": "Çankaya"})
    assert fixed["ready"], fixed["errors"]


def test_discount_interpretation_follows_order_total():
    base = {"order_number": "X", "lines": [{"name": "Ürün", "quantity": 1, "unit_price": 1000.0,
                                            "line_total": None, "line_discount": 0, "vat_rate": None}]}
    billing = {"full_name": "A B", "address": "Adres", "district": "İlçe", "city": "İl"}
    # Satır indirimsiz 1000, toplam 900 → indirim satıra dağıtılmalı
    order = {**base, "fields": {**billing, "discount": 100.0, "order_total": 900.0}}
    draft = build_invoice_draft(order)
    assert draft["totals"]["gross"] == 900.0
    assert draft["totals"]["discount_applied"] == 100.0
    # Satır zaten indirimli (toplam = satır) → tekrar düşülmemeli
    order = {**base, "fields": {**billing, "discount": 100.0, "order_total": 1000.0}}
    draft = build_invoice_draft(order)
    assert draft["totals"]["gross"] == 1000.0
    assert draft["totals"]["discount_applied"] == 0.0


def test_company_buyer_requires_vkn_and_tax_office():
    order = {"order_number": "C", "fields": {"company_name": "Örnek Ltd", "address": "a", "district": "b",
                                             "city": "c"},
             "lines": [{"name": "Ürün", "quantity": 1, "unit_price": 100.0}]}
    draft = build_invoice_draft(order)
    assert draft["buyer_type"] == "kurumsal"
    assert not draft["ready"]
    draft = build_invoice_draft(order, {"tax_number": "1234567890", "tax_office": "Kadıköy"})
    assert draft["ready"], draft["errors"]


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

def _upload(client, token, rows=SAMPLE_ROWS, name="ikas.xlsx"):
    return client.post(
        "/api/invoices/ikas/import",
        files={"file": (name, _xlsx(rows), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=auth_headers(token),
    )


def test_requires_auth(client, temp_db):
    assert client.get("/api/invoices/ikas/orders").status_code in (401, 403)
    assert client.post("/api/invoices/ikas/import", files={"file": ("a.csv", b"x")}).status_code in (401, 403)


def test_import_list_edit_and_reimport_keeps_overrides(client, temp_db):
    _, token = make_store(temp_db, "ikas-a@test.local")
    r = _upload(client, token)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["created"] == 2 and body["orders_in_file"] == 2
    assert body["ignored_columns"] == ["Bilinmeyen Kolon"]

    r = client.get("/api/invoices/ikas/orders", headers=auth_headers(token))
    counts = r.json()["counts"]
    assert counts == {"all": 2, "ready": 1, "needs_info": 1, "invoiced": 0, "error": 0}

    r = client.patch(
        "/api/invoices/ikas/orders/1002",
        json={"address": "Kızılay Mah. 5", "district": "Çankaya"},
        headers=auth_headers(token),
    )
    assert r.status_code == 200 and r.json()["status"] == "ready"

    # Tekrar yükleme: güncellenir ama elle düzeltme korunur
    r = _upload(client, token)
    assert r.json()["updated"] == 2 and r.json()["created"] == 0
    r = client.get("/api/invoices/ikas/orders/1002", headers=auth_headers(token))
    assert r.json()["status"] == "ready"
    assert r.json()["draft"]["billing"]["district"] == "Çankaya"

    r = client.get("/api/invoices/ikas/orders", params={"status": "ready"}, headers=auth_headers(token))
    assert len(r.json()["items"]) == 2


def test_invoiced_order_is_locked(client, temp_db):
    from database.models import IkasOrder

    store_id, token = make_store(temp_db, "ikas-lock@test.local")
    _upload(client, token)
    db = temp_db["SessionLocal"]()
    rec = db.query(IkasOrder).filter_by(store_id=store_id, order_number="1001").first()
    rec.status = "invoiced"
    rec.invoice_number = "PEN2026000000001"
    db.commit()
    db.close()

    assert client.patch("/api/invoices/ikas/orders/1001", json={"city": "x"},
                        headers=auth_headers(token)).status_code == 409
    assert client.delete("/api/invoices/ikas/orders/1001", headers=auth_headers(token)).status_code == 409
    assert _upload(client, token).json()["skipped_invoiced"] == 1


def test_orders_are_isolated_between_stores(client, temp_db):
    _, token_a = make_store(temp_db, "ikas-iso-a@test.local")
    _, token_b = make_store(temp_db, "ikas-iso-b@test.local")
    _upload(client, token_a)

    assert client.get("/api/invoices/ikas/orders", headers=auth_headers(token_b)).json()["counts"]["all"] == 0
    assert client.get("/api/invoices/ikas/orders/1001", headers=auth_headers(token_b)).status_code == 404
    assert client.patch("/api/invoices/ikas/orders/1001", json={"city": "x"},
                        headers=auth_headers(token_b)).status_code == 404
    assert client.delete("/api/invoices/ikas/orders/1001", headers=auth_headers(token_b)).status_code == 404
    assert client.get("/api/invoices/ikas/orders", headers=auth_headers(token_a)).json()["counts"]["all"] == 2


def test_rejects_file_without_order_number(client, temp_db):
    _, token = make_store(temp_db, "ikas-bad@test.local")
    r = _upload(client, token, rows=[{"Ürün": "x", "Fiyat": "1"}])
    assert r.status_code == 400
    r = client.post("/api/invoices/ikas/import", files={"file": ("a.xls", b"abc")}, headers=auth_headers(token))
    assert r.status_code == 400


def test_vat_settings_change_draft(client, temp_db):
    _, token = make_store(temp_db, "ikas-vat@test.local")
    _upload(client, token)
    r = client.put("/api/invoices/settings", json={"product_vat_rate": 20, "shipping_vat_rate": 20},
                   headers=auth_headers(token))
    assert r.status_code == 200
    r = client.get("/api/invoices/ikas/orders/1001", headers=auth_headers(token))
    assert r.json()["draft"]["totals"]["vat"] == 275.0  # 1650 - 1650/1.2
    assert client.put("/api/invoices/settings", json={"product_vat_rate": 150, "shipping_vat_rate": 20},
                      headers=auth_headers(token)).status_code == 422
