"""
w3-customerqa-scope: qa_records artık store_id ile izole. Saf yerel DB
işlemleridir, Trendyol'a çağrı yapılmaz (create_question/submit_answer/
ai-suggest hiçbiri canlı Trendyol'a gitmez — sadece GET / Trendyol tarafını
dener, biz onu bağlı-olmayan-mağaza 409'una düşürerek test dışı bırakıyoruz).
"""
from tests.conftest import make_store, auth_headers


def test_qa_isolated_between_stores_read_and_write(client, temp_db):
    """A'nın sorusu B'de görünmemeli; B onu id ile de göremez/cevaplayamaz."""
    _, token_a = make_store(temp_db, "qa-a@test.local")
    _, token_b = make_store(temp_db, "qa-b@test.local")

    r = client.post(
        "/api/customer-qa/",
        json={"question": "Kargo ücreti ne kadar?", "customer_id": "c1"},
        headers=auth_headers(token_a),
    )
    assert r.status_code == 200, r.text
    qa_id = r.json()["qa_id"]

    # store A kendi sorusunu görüyor
    r = client.get(f"/api/customer-qa/{qa_id}", headers=auth_headers(token_a))
    assert r.status_code == 200, r.text

    # store B AYNI qa_id ile bakınca BULAMAMALI (404, veri sızmamalı)
    r = client.get(f"/api/customer-qa/{qa_id}", headers=auth_headers(token_b))
    assert r.status_code == 404, r.text

    # store B cevap da veremez
    r = client.post(
        f"/api/customer-qa/{qa_id}/answer",
        json={"answer": "el koymaya çalışıyorum"},
        headers=auth_headers(token_b),
    )
    assert r.status_code == 404, r.text

    # store A hâlâ cevaplayabiliyor (gerçek sahip etkilenmedi)
    r = client.post(
        f"/api/customer-qa/{qa_id}/answer",
        json={"answer": "50 TL"},
        headers=auth_headers(token_a),
    )
    assert r.status_code == 200, r.text


def test_qa_learning_stats_isolated(client, temp_db):
    """B'nin öğrenme istatistikleri A'nın cevapladığı sorudan ETKİLENMEMELİ."""
    _, token_a = make_store(temp_db, "qa-stats-a@test.local")
    _, token_b = make_store(temp_db, "qa-stats-b@test.local")

    r = client.post(
        "/api/customer-qa/", json={"question": "Beden tablosu var mı?"}, headers=auth_headers(token_a)
    )
    qa_id = r.json()["qa_id"]
    client.post(f"/api/customer-qa/{qa_id}/answer", json={"answer": "Evet"}, headers=auth_headers(token_a))

    stats_a = client.get("/api/customer-qa/stats/learning", headers=auth_headers(token_a)).json()
    stats_b = client.get("/api/customer-qa/stats/learning", headers=auth_headers(token_b)).json()

    assert stats_a["total_count"] == 1
    assert stats_a["answered_count"] == 1
    assert stats_b["total_count"] == 0
    assert stats_b["answered_count"] == 0
