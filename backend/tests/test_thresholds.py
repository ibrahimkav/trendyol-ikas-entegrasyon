"""
w3-configurable-thresholds testleri. Saf yerel DB işlemleridir, Trendyol'a
hiçbir çağrı yapılmaz.
"""
from tests.conftest import make_store, auth_headers


def test_get_thresholds_returns_defaults_when_unset(client, temp_db):
    """Hiç ayar girilmemiş mağazada eski kod-gömülü sabitler dönmeli
    (geriye dönük uyumluluk) ve is_customized hepsi false olmalı."""
    _, token = make_store(temp_db, "thresholds-default@test.local")
    resp = client.get("/api/settings/thresholds", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["margin_warning_threshold"] == 15.0
    assert data["low_stock_floor"] == 5
    assert data["low_stock_sales_ratio"] == 0.15
    assert data["is_customized"] == {
        "margin_warning_threshold": False,
        "low_stock_floor": False,
        "low_stock_sales_ratio": False,
    }


def test_put_thresholds_partial_update_persists(client, temp_db):
    """PUT sadece gönderilen alanı değiştirir, diğerleri varsayılanda kalır."""
    _, token = make_store(temp_db, "thresholds-put@test.local")

    resp = client.put(
        "/api/settings/thresholds",
        json={"margin_warning_threshold": 25.0},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["margin_warning_threshold"] == 25.0
    assert data["low_stock_floor"] == 5  # dokunulmadı, varsayılanda
    assert data["is_customized"]["margin_warning_threshold"] is True
    assert data["is_customized"]["low_stock_floor"] is False

    # Ayrı bir GET ile de aynı sonucu doğrula (gerçekten yazıldı, sadece PUT'un
    # kendi yanıtı değil).
    resp2 = client.get("/api/settings/thresholds", headers=auth_headers(token))
    assert resp2.json()["margin_warning_threshold"] == 25.0

    # İkinci bir PUT ile başka bir alanı güncelle — ilki KORUNMALI.
    resp3 = client.put(
        "/api/settings/thresholds",
        json={"low_stock_floor": 12},
        headers=auth_headers(token),
    )
    data3 = resp3.json()
    assert data3["margin_warning_threshold"] == 25.0  # önceki ayar hâlâ duruyor
    assert data3["low_stock_floor"] == 12


def test_put_thresholds_out_of_range_returns_400(client, temp_db):
    _, token = make_store(temp_db, "thresholds-invalid@test.local")
    resp = client.put(
        "/api/settings/thresholds",
        json={"margin_warning_threshold": 150.0},
        headers=auth_headers(token),
    )
    assert resp.status_code == 422 or resp.status_code == 400, resp.text


def test_thresholds_isolated_between_stores(client, temp_db):
    """A'nın eşiği B'de görünmemeli — çapraz-mağaza sızıntısı yok."""
    _, token_a = make_store(temp_db, "thresholds-a@test.local")
    _, token_b = make_store(temp_db, "thresholds-b@test.local")

    client.put(
        "/api/settings/thresholds",
        json={"margin_warning_threshold": 40.0, "low_stock_floor": 20},
        headers=auth_headers(token_a),
    )

    resp_a = client.get("/api/settings/thresholds", headers=auth_headers(token_a))
    assert resp_a.json()["margin_warning_threshold"] == 40.0

    resp_b = client.get("/api/settings/thresholds", headers=auth_headers(token_b))
    data_b = resp_b.json()
    assert data_b["margin_warning_threshold"] == 15.0  # B hâlâ varsayılanda
    assert data_b["is_customized"]["margin_warning_threshold"] is False


def test_reset_threshold_field_returns_to_default(client, temp_db):
    """Oscar'ın bulgusu: PUT'taki null='dokunma' yüzünden gerçek bir 'özelleştirmeyi
    kaldır' yolu yoktu — DELETE /thresholds/{field} bunu sağlıyor."""
    _, token = make_store(temp_db, "thresholds-reset@test.local")

    client.put(
        "/api/settings/thresholds",
        json={"margin_warning_threshold": 30.0, "low_stock_floor": 9},
        headers=auth_headers(token),
    )

    resp = client.delete("/api/settings/thresholds/margin_warning_threshold", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["margin_warning_threshold"] == 15.0
    assert data["is_customized"]["margin_warning_threshold"] is False
    # diğer alan ETKİLENMEMELİ
    assert data["low_stock_floor"] == 9
    assert data["is_customized"]["low_stock_floor"] is True


def test_reset_unknown_field_returns_400(client, temp_db):
    _, token = make_store(temp_db, "thresholds-reset-bad@test.local")
    resp = client.delete("/api/settings/thresholds/not_a_real_field", headers=auth_headers(token))
    assert resp.status_code == 400


def test_nan_input_returns_clean_422_not_500(client, temp_db):
    """Regresyon: bir sayısal alana NaN gönderilince Pydantic 422 üretirdi ama
    hata mesajı ham değeri yansıttığı için Starlette'in JSON encoder'ı (allow_nan=False)
    onu serialize ederken 500'e düşüyordu (Oscar'ın bulgusu). Artık app-geneli
    handler bunu temiz 422'ye çeviriyor."""
    _, token = make_store(temp_db, "thresholds-nan@test.local")
    resp = client.put(
        "/api/settings/thresholds",
        content=b'{"margin_warning_threshold": NaN}',
        headers={**auth_headers(token), "Content-Type": "application/json"},
    )
    assert resp.status_code == 422, resp.text
    # yanıt gerçekten JSON olarak parse edilebilmeli (500 HTML/plain text değil)
    body = resp.json()
    assert "detail" in body


def test_persists_across_restart(app, temp_db):
    """Kalıcılık kanıtı: aynı temp DB dosyasına bağlı YENİ bir TestClient/lifespan
    döngüsü ('restart' simülasyonu) ayarın hâlâ durduğunu görmeli — process-içi
    bir değişkende değil, GERÇEKTEN DB satırında tutulduğunun kanıtı."""
    from fastapi.testclient import TestClient

    store_id, token = make_store(temp_db, "thresholds-restart@test.local")

    with TestClient(app) as c1:
        r = c1.put(
            "/api/settings/thresholds",
            json={"margin_warning_threshold": 33.0},
            headers=auth_headers(token),
        )
        assert r.status_code == 200, r.text

    # "Restart": lifespan'ı kapatıp AYNI temp DB'ye bağlı yeni bir TestClient
    # döngüsü açıyoruz (app.dependency_overrides zaten aynı temp_db'ye bağlı).
    with TestClient(app) as c2:
        r2 = c2.get("/api/settings/thresholds", headers=auth_headers(token))
        assert r2.status_code == 200, r2.text
        assert r2.json()["margin_warning_threshold"] == 33.0
