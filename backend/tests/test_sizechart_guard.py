"""
w3-sizechart-guard: size_chart.py'nin 4 CRUD endpoint'i öncesinde HİÇBİR
Depends() yoktu (auth'suz) ve store_id filtrelemiyordu (çapraz-mağaza
yazma+silme mümkündü). Bu dosya hem "auth zorunlu" hem "store izole"
(özellikle YAZMA/SİLME yönü) davranışını kilitler. Saf yerel DB işlemleridir,
Trendyol'a çağrı yapılmaz.
"""
from tests.conftest import make_store, auth_headers


def test_unauthenticated_requests_are_rejected(client, temp_db):
    """Regresyon: bu 4 uç ÖNCEDEN kimlik doğrulaması olmadan (401 değil, 200)
    erişilebiliyordu. Authorization header'ı hiç göndermeden hepsi reddedilmeli."""
    assert client.get("/api/size-chart/").status_code in (401, 403)
    assert client.get("/api/size-chart/SOME-CODE").status_code in (401, 403)
    assert client.post("/api/size-chart/SOME-CODE", json={"sizes": []}).status_code in (401, 403)
    assert client.delete("/api/size-chart/SOME-CODE").status_code in (401, 403)


def _sizes():
    return [{"size": "M", "bel_min": 76, "bel_max": 81}]


def test_sizechart_isolated_read(client, temp_db):
    """A'nın oluşturduğu tablo B'nin listesinde/aramasında görünmemeli."""
    _, token_a = make_store(temp_db, "sc-a@test.local")
    _, token_b = make_store(temp_db, "sc-b@test.local")

    r = client.post(
        "/api/size-chart/LEAK-CODE",
        json={"product_name": "Test Ürün", "sizes": _sizes()},
        headers=auth_headers(token_a),
    )
    assert r.status_code == 200, r.text

    r = client.get("/api/size-chart/", headers=auth_headers(token_b))
    assert r.status_code == 200
    assert r.json()["total_count"] == 0

    r = client.get("/api/size-chart/LEAK-CODE", headers=auth_headers(token_b))
    assert r.status_code == 404


def test_sizechart_write_and_delete_isolated(client, temp_db):
    """EN YÜKSEK RİSKLİ kısım: B, A'nın kaydının ÜZERİNE YAZAMAMALI ve
    SİLEMEMELİ. B'nin isteği kendi (boş) kaydını etkilemeli, A'nınkini değil."""
    from database.models import SizeChart

    store_a, token_a = make_store(temp_db, "sc-write-a@test.local")
    store_b, token_b = make_store(temp_db, "sc-write-b@test.local")

    client.post(
        "/api/size-chart/SHARED-CODE",
        json={"product_name": "A'nın ürünü", "sizes": _sizes()},
        headers=auth_headers(token_a),
    )

    # B AYNI product_code ile upsert dener — kendi YENİ satırını oluşturmalı,
    # A'nınkinin üzerine YAZMAMALI.
    r = client.post(
        "/api/size-chart/SHARED-CODE",
        json={"product_name": "B'nin ürünü", "sizes": [{"size": "L"}]},
        headers=auth_headers(token_b),
    )
    assert r.status_code == 200, r.text

    db = temp_db["SessionLocal"]()
    try:
        rows = db.query(SizeChart).filter(SizeChart.product_code == "SHARED-CODE").all()
        by_store = {row.store_id: row.product_name for row in rows}
        assert by_store[store_a] == "A'nın ürünü", "B'nin yazması A'nın kaydını BOZMUŞ"
        assert by_store[store_b] == "B'nin ürünü"
    finally:
        db.close()

    # B kendi kaydını siler — A'nınki ETKİLENMEMELİ.
    r = client.delete("/api/size-chart/SHARED-CODE", headers=auth_headers(token_b))
    assert r.status_code == 200, r.text

    # A'nın kaydı hâlâ duruyor.
    r = client.get("/api/size-chart/SHARED-CODE", headers=auth_headers(token_a))
    assert r.status_code == 200
    assert r.json()["product_name"] == "A'nın ürünü"

    # B artık kendi kaydını göremiyor (sildi).
    r = client.get("/api/size-chart/SHARED-CODE", headers=auth_headers(token_b))
    assert r.status_code == 404


def test_sizechart_delete_does_not_affect_other_store_directly(client, temp_db):
    """B, A'nın kaydı VARKEN kendi kaydı YOKKEN SHARED-CODE'u silmeye çalışırsa
    404 almalı (kendi kaydı yok) — A'nın kaydı asla dokunulmamalı."""
    store_a, token_a = make_store(temp_db, "sc-del-a@test.local")
    _, token_b = make_store(temp_db, "sc-del-b@test.local")

    client.post(
        "/api/size-chart/ONLY-A-CODE",
        json={"product_name": "Sadece A'da", "sizes": _sizes()},
        headers=auth_headers(token_a),
    )

    r = client.delete("/api/size-chart/ONLY-A-CODE", headers=auth_headers(token_b))
    assert r.status_code == 404, r.text

    r = client.get("/api/size-chart/ONLY-A-CODE", headers=auth_headers(token_a))
    assert r.status_code == 200, "B'nin başarısız silme denemesi A'nın kaydını etkilememeli"


def test_parse_text_requires_auth_but_not_store(client, temp_db):
    """parse-text hiçbir DB okuma/yazma yapmaz (saf metin ayrıştırma) — store
    kavramı uygulanmaz, ama en azından giriş yapmış olmak gerekir."""
    assert client.post("/api/size-chart/parse-text", json={"text": "M: Bel 76-81"}).status_code in (401, 403)

    _, token = make_store(temp_db, "sc-parse@test.local")
    # w3-sizeadvisor-case'de düzeltildi: endpoint'in KENDİ dokümante ettiği
    # örnek (büyük harfli etiketler) artık gerçekten parse oluyor.
    text = "S: Bel 71-76, Göğüs 83-88, Boy 165-170, Kilo 50-60"
    r = client.post("/api/size-chart/parse-text", json={"text": text}, headers=auth_headers(token))
    assert r.status_code == 200, r.text
    assert r.json()["success"] is True
