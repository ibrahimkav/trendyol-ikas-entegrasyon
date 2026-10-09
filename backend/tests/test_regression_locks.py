"""
Regresyon kilitleri — bu dalgada GERÇEKTEN bozuk bulunup düzeltilen davranışlar
(w3-hardening / w3-backend-cleanup / w3-epoch-date-sweep). Amaç geniş kapsam
değil: bunların bir daha SESSİZCE bozulmamasını yakalamak.

Trendyol'a hiçbir canlı çağrı yapılmaz: orders/stats testinde per-store
credential çözümleyicisi ve sipariş çekme fonksiyonu monkeypatch'lenir.
"""
import time

import routers.orders as orders_module
from tests.conftest import make_store, auth_headers


class _FakeCreds:
    supplier_id = "999999"
    api_key = "fake"
    api_secret = "fake"
    store_id = None


def test_orders_stats_no_crash_and_epoch_ms_parsed(client, temp_db, monkeypatch):
    """Regresyon 1: orders.py'de bir NameError (dead variable: total_elements,
    w3-backend-cleanup) bu uca girildiğinde 500 fırlatıyordu.
    Regresyon 2: Trendyol epoch-ms (13 haneli) int tarih gönderir; eski kod
    string varsayıp bunu ya çöktürüyor ya da sessizce filtreden düşürüyordu
    (w3-epoch-date-sweep). Bu test her ikisini TEK istekte kilitler."""
    store_id, token = make_store(temp_db, "orders-stats@test.local")

    now_ms = int(time.time() * 1000)
    ten_days_ago_ms = now_ms - 10 * 24 * 3600 * 1000
    two_years_ago_ms = now_ms - 2 * 365 * 24 * 3600 * 1000

    fake_orders = [
        {"orderNumber": "1", "status": "Delivered", "orderDate": ten_days_ago_ms, "totalPrice": 100.0},
        {"orderNumber": "2", "status": "Created", "orderDate": two_years_ago_ms, "totalPrice": 50.0},
    ]

    monkeypatch.setattr(orders_module, "resolve_trendyol_creds", lambda db, store: _FakeCreds())
    monkeypatch.setattr(orders_module, "fetch_orders", lambda creds: fake_orders)

    resp = client.get("/api/orders/stats?period=30days", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    data = resp.json()
    # epoch-ms doğru ayrıştırılmasaydı ya 500 dönerdi ya da her iki sipariş de
    # (yanlış birim yüzünden) filtreye takılırdı/geçerdi — sadece 10-gün-önceki
    # siparişin "30days" penceresine girmesi doğru davranışın kanıtı.
    assert data["total_orders"] == 1, f"epoch-ms tarih filtresi yanlış çalışıyor: {data}"

    resp_all = client.get("/api/orders/stats?period=all", headers=auth_headers(token))
    assert resp_all.status_code == 200, resp_all.text
    assert resp_all.json()["total_orders"] == 2


def test_sync_now_unconnected_store_returns_409_not_500(client, temp_db):
    """Regresyon: bağlı olmayan mağazada senkronizasyon uçları 500 DEĞİL,
    açıklayıcı 409 dönmeli (resolve_trendyol_creds ilk adımda devreye girer,
    hiçbir Trendyol çağrısı denenmeden)."""
    _, token = make_store(temp_db, "sync-unconnected@test.local")
    resp = client.post("/api/sync/now", headers=auth_headers(token))
    assert resp.status_code == 409, resp.text
    assert "Trendyol" in resp.json()["detail"]


def test_alerts_advanced_no_crash(client, temp_db):
    """Regresyon: bir dosyada StockAlert adında hem gerçek SQLAlchemy modeli hem
    de (artık kaldırılmış) bir Pydantic BaseModel varsa, ikincisi birinciyi
    gölgeler ve db.query(StockAlert) 'Column expression... got <class ...>'
    hatasıyla 500 patlar. Bu uç canlı 200 dönmeli."""
    _, token = make_store(temp_db, "alerts@test.local")
    resp = client.get("/api/inventory/alerts/advanced", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    assert resp.json() == []  # yeni mağaza, hiç alert yok


def test_alerts_acknowledge_no_crash(client, temp_db):
    """Aynı gölgelenme regresyonu, bu sefer yazma (acknowledge) tarafında."""
    from database.models import StockAlert
    from datetime import datetime

    store_id, token = make_store(temp_db, "alerts-ack@test.local")
    db = temp_db["SessionLocal"]()
    try:
        alert = StockAlert(
            store_id=store_id,
            product_id="P1",
            product_name="Test Ürün",
            current_stock=0,
            min_stock_level=5,
            alert_type="out_of_stock",
            alert_level=3,
            is_acknowledged=False,
            created_at=datetime.now(),
        )
        db.add(alert)
        db.commit()
        db.refresh(alert)
        alert_id = alert.id
    finally:
        db.close()

    resp = client.post(f"/api/inventory/alerts/acknowledge/{alert_id}", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    assert resp.json()["alert_id"] == alert_id
