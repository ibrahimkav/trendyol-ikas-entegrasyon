# Backend smoke/regresyon testleri

Çalıştırmak için (backend/ dizininden): `venv/Scripts/python.exe -m pytest tests/ -v`

Her test kendi geçici SQLite dosyasını kullanır (`tmp_path` fixture) — gerçek `trendyol_data.db`'ye YAZILMAZ, sadece `init_db()`'nin idempotent şema kontrolü her `TestClient` başlangıcında ona dokunur (gerçek sunucu her açılışta zaten aynısını yapıyor, veri kaybı riski yok). Background sync + Trendyol'a giden hiçbir canlı çağrı testlerde tetiklenmez (no-op'lanmış/monkeypatch'lenmiş).

Kapsam: `test_regression_locks.py` (daha önce gerçekten bozuk olan şeyler), `test_cross_store_isolation.py` (çapraz-mağaza sızıntıları), `test_new_surface.py` (grouped settings + bulk CSV). pytest bu oturumda `pip install pytest` ile eklendi (venv'de yoktu) — `requirements.txt`'e yazıldı.
