"""
Database Connection and Session Management
"""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
import os
from pathlib import Path

# aiosqlite'ı önceden import et - SQLAlchemy'nin driver'ı bulabilmesi için
try:
    import aiosqlite
except ImportError:
    aiosqlite = None

# Database path
DB_DIR = Path(__file__).parent.parent
DB_PATH = DB_DIR / "trendyol_data.db"
DB_URL = f"sqlite:///{DB_PATH}"
ASYNC_DB_URL = f"sqlite+aiosqlite:///{DB_PATH}"

def _set_sqlite_pragmas(dbapi_connection, connection_record):
    """Her yeni SQLite bağlantısında WAL modu + busy_timeout ayarlar.
    WAL modu okuyucuların bir yazma-transaction'ı ile çakışıp "database is locked"
    hatası almasını büyük ölçüde önler (background sync task + eşzamanlı API istekleri
    aynı dosyaya yazarken bu olmadan sık görülüyordu). busy_timeout ise kısa süreli
    çakışmalarda anında hata vermek yerine birkaç saniye bekleyip tekrar dener."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=20000")
    cursor.close()


# Sync engine (normal operations) - Ghost mode: hataları sessizce yakala
engine = None
SessionLocal = None

try:
    engine = create_engine(
        DB_URL,
        connect_args={"check_same_thread": False, "timeout": 20},  # SQLite için gerekli
        echo=False  # SQL sorgularını logla (debug için True yapılabilir)
    )
    event.listen(engine, "connect", _set_sqlite_pragmas)
    # Session makers
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
except Exception as e:
    # Ghost mode: hata olsa bile devam et
    pass

# Async engine ve session maker - lazy loading (sadece gerektiğinde oluştur)
_async_engine = None
_AsyncSessionLocal = None

def get_async_engine():
    """Async engine'i lazy olarak oluştur"""
    global _async_engine
    if _async_engine is None:
        if aiosqlite is None:
            print("[Database] Warning: aiosqlite module not found. Please install it with: pip install aiosqlite")
            print("[Database] Async operations will use sync engine instead")
            return None
        try:
            _async_engine = create_async_engine(
                ASYNC_DB_URL,
                echo=False,
                connect_args={"timeout": 20},
            )
            event.listen(_async_engine.sync_engine, "connect", _set_sqlite_pragmas)
        except Exception as e:
            print(f"[Database] Warning: Could not create async engine: {e}")
            print("[Database] Async operations will use sync engine instead")
            return None
    return _async_engine

def get_async_session_maker():
    """Async session maker'ı lazy olarak oluştur"""
    global _AsyncSessionLocal
    if _AsyncSessionLocal is None:
        async_eng = get_async_engine()
        if async_eng is None:
            return None
        _AsyncSessionLocal = async_sessionmaker(async_eng, class_=AsyncSession, expire_on_commit=False)
    return _AsyncSessionLocal


def get_db() -> Session:
    """Dependency injection için database session"""
    if SessionLocal is None:
        raise RuntimeError("Database not available (ghost mode)")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_async_db() -> AsyncSession:
    """Async database session"""
    session_maker = get_async_session_maker()
    if session_maker is None:
        raise RuntimeError("Async database not available. Please install aiosqlite.")
    async with session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


def init_db():
    """Database'i başlat ve tabloları oluştur"""
    global engine, SessionLocal
    
    try:
        if engine is None:
            # Engine yoksa oluştur
            engine = create_engine(
                DB_URL,
                connect_args={"check_same_thread": False, "timeout": 20},
                echo=False
            )
            event.listen(engine, "connect", _set_sqlite_pragmas)
            SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        
        from database.models import Base

        # Database dosyasını oluştur
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)

        # Tabloları oluştur
        Base.metadata.create_all(bind=engine)
        print(f"[Database] Initialized database at {DB_PATH}")

        # Hafif kolon migration'ları (default_cost, unit_cost vb.)
        from database.migrations import run_migrations, prune_old_change_history
        run_migrations(engine)

        # w3-write-audit-trail: değişim geçmişi sonsuza kadar büyümesin (365 gün)
        prune_old_change_history(engine)

        # Çok-kiracılı migration (users/stores/store_id) — idempotent
        from database.migrate_multitenant import run_multitenant_migration
        run_multitenant_migration(engine)
    except Exception as e:
        # Ghost mode: hata olsa bile sessizce devam et
        print(f"[Database] Warning: Database initialization skipped (ghost mode): {e}")
        pass


def reset_db():
    """Database'i sıfırla (DİKKAT: Tüm veriler silinir!)"""
    from database.models import Base
    
    if DB_PATH.exists():
        DB_PATH.unlink()
        print(f"[Database] Deleted existing database")
    
    init_db()
    print(f"[Database] Database reset complete")

