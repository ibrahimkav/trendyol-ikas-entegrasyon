"""
w3-smoke-tests ortak fixture'ları.

Her test kendi GEÇİCİ SQLite dosyasını kullanır (gerçek trendyol_data.db'ye HİÇ
dokunulmaz) ve Trendyol'a HİÇBİR canlı çağrı yapmaz — background sync task
no-op'a çevrilir, credential çözümleyicileri gereken testlerde monkeypatch'lenir.
"""
import os
import sys
import tempfile
import importlib

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("JWT_SECRET", "test-suite-jwt-secret-not-for-prod-use-only")
# Geçerli bir Fernet anahtarı olmalı (32 bayt url-safe base64) — eski değer geçersizdi ve
# kimlik bilgisi kaydeden ilk testte ValueError veriyordu.
os.environ.setdefault("CREDENTIAL_ENCRYPTION_KEY", "dGVzdC1zdWl0ZS1jcmVkLWtleS1ub3QtZm9yLXByb2Q=")


@pytest.fixture()
def temp_db(monkeypatch, tmp_path):
    """Her test için TAZE, izole bir SQLite dosyası. Gerçek trendyol_data.db'ye
    dokunulmaz. database.db.get_db bu geçici DB'ye yönlendirilir (app.dependency_overrides)."""
    db_path = tmp_path / "test_smoke.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    from database.models import Base
    # w3-dup-index-fix + w3-dup-index-fix-rest: models.py'deki TÜM çakışan index
    # adları (idx_product_id + 5 diğeri) düzeltildi — artık düz create_all() yeterli,
    # önceki tolerant-skip workaround'una gerek kalmadı.
    Base.metadata.create_all(bind=engine)
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def _override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    yield {"engine": engine, "SessionLocal": TestSessionLocal, "override": _override_get_db}
    engine.dispose()


@pytest.fixture()
def app(temp_db, monkeypatch):
    """FastAPI app'i geçici DB'ye bağlı, background sync no-op'lanmış olarak döner."""
    import main as main_module
    from database.db import get_db as real_get_db

    # Background sync task GERÇEK Trendyol çağrısı yapar (env/per-store cred ile) —
    # testlerde asla tetiklenmesin diye no-op'a çevriliyor (main.py'nin KENDİ modül
    # global'i patch'leniyor, çünkü lifespan() ismi main modülünün globals'ından okur).
    async def _noop_background_sync(interval_minutes=5):
        return None
    monkeypatch.setattr(main_module, "background_sync_task", _noop_background_sync)

    main_module.app.dependency_overrides[real_get_db] = temp_db["override"]

    yield main_module.app

    main_module.app.dependency_overrides.clear()


@pytest.fixture()
def client(app):
    with TestClient(app) as c:
        yield c


def make_store(temp_db, email: str):
    """Yeni bir User+Store oluşturur, (store, token) döner. StoreCredential
    EKLENMEZ (varsayılan: bağlı değil) — bağlı bir mağaza gereken testler
    kendi credential/monkeypatch'ini kurar."""
    from database.models import User, Store
    from security import create_access_token

    db = temp_db["SessionLocal"]()
    try:
        user = User(email=email, is_active=True)
        db.add(user)
        db.commit()
        db.refresh(user)

        store = Store(user_id=user.id, store_name=f"Test Mağaza {email}", is_active=True)
        db.add(store)
        db.commit()
        db.refresh(store)

        token = create_access_token(user_id=user.id, store_id=store.id)
        return store.id, token
    finally:
        db.close()


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
