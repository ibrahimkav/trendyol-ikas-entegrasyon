"""
Çok-kiracılı (multi-tenant) migration — Wave 1 backend temeli.

Yapılanlar:
  1. `users`, `stores`, `store_credentials`, `otp_codes` tablolarını oluşturur (yoksa).
  2. Bootstrap: id=1 ile bir varsayılan User + Store oluşturur (mevcut tek-mağaza
     verisinin sahibi olacak) — yoksa.
  3. Mevcut 19 iş tablosuna `store_id INTEGER NOT NULL DEFAULT 1` kolonu ekler
     (ALTER TABLE ... ADD COLUMN) — bu hem geriye dönük satırları 1'e backfill eder
     hem de gelecekteki INSERT'lerde varsayılan değer sağlar.
  4. Eskiden tek-kolon UNIQUE olan 8 tabloyu (products, orders, cache_metadata,
     return_refunds, campaigns, barcode_templates, qa_records, size_charts)
     composite (store_id, X) UNIQUE constraint'e geçirmek için yeniden oluşturur
     (SQLite tek-kolon UNIQUE constraint'i ALTER TABLE ile kaldıramaz; bu yüzden
     create-tmp -> copy -> drop-old -> rename yolu izlenir).

İdempotent: her tablo için "store_id kolonu zaten var mı?" kontrolü yapılır;
varsa o tablo atlanır. Birden fazla çalıştırmak güvenlidir.

Geri dönüş: çalıştırmadan önce `trendyol_data.db` otomatik olarak
`trendyol_data.db.bak-<timestamp>` adıyla yedeklenir. Migration'ı geri almak için
bu yedeği `trendyol_data.db` üzerine kopyalamak yeterlidir (uygulama kapalıyken).

Kullanım:
    python -m database.migrate_multitenant
"""
import shutil
from datetime import datetime
from pathlib import Path

from sqlalchemy import inspect, text

# Tek-kolon UNIQUE'den composite (store_id, X)'e geçecek tablolar.
# campaigns için iki unique kolon var (campaign_id, coupon_code) — rebuild mantığı
# tablo bazlı olduğu için ayrıca listelemeye gerek yok, model şeması zaten ikisini de içeriyor.
REBUILD_TABLES = [
    "products",
    "orders",
    "cache_metadata",
    "return_refunds",
    "campaigns",
    "barcode_templates",
    "qa_records",
    "size_charts",
]

# Sadece store_id eklenmesi yeterli olan tablolar (unique constraint değişikliği yok)
SIMPLE_TABLES = [
    "order_lines",
    "competitor_prices",
    "sync_logs",
    "campaign_performance",
    "stock_alerts",
    "stock_recommendations",
    "stock_history",
    "price_history",
    "barcode_history",
    "price_trends",
    "product_image_mappings",
]

ALL_STORE_ID_TABLES = REBUILD_TABLES + SIMPLE_TABLES


def _backup(db_path: Path) -> Path:
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = db_path.with_name(f"{db_path.name}.bak-{ts}")
    shutil.copy2(db_path, backup_path)
    print(f"[Migration] Yedek alındı: {backup_path}")
    return backup_path


def _table_has_column(inspector, table: str, column: str) -> bool:
    if table not in inspector.get_table_names():
        return False
    return any(c["name"] == column for c in inspector.get_columns(table))


def _bootstrap_default_owner(conn):
    """id=1 User + id=1 Store yoksa oluşturur (mevcut tek-mağaza verisinin sahibi)."""
    existing_user = conn.execute(text("SELECT id FROM users WHERE id = 1")).fetchone()
    if not existing_user:
        conn.execute(text(
            "INSERT INTO users (id, email, is_active, created_at) "
            "VALUES (1, 'owner@local', 1, CURRENT_TIMESTAMP)"
        ))
        print("[Migration] Varsayılan sahip kullanıcı oluşturuldu: users.id=1 (owner@local)")

    existing_store = conn.execute(text("SELECT id FROM stores WHERE id = 1")).fetchone()
    if not existing_store:
        conn.execute(text(
            "INSERT INTO stores (id, user_id, store_name, is_active, created_at, updated_at) "
            "VALUES (1, 1, 'Mağazam', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        ))
        print("[Migration] Varsayılan mağaza oluşturuldu: stores.id=1 (mevcut veri buraya bağlandı)")


def _add_store_id_simple(conn, table: str):
    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN store_id INTEGER NOT NULL DEFAULT 1"))
    conn.execute(text(f"CREATE INDEX IF NOT EXISTS idx_{table}_store_id ON {table} (store_id)"))
    print(f"[Migration] {table}: store_id eklendi (basit ALTER)")


def _rebuild_with_composite_unique(conn, inspector, table: str, model_cls):
    """
    Tabloyu yeni şemayla (store_id + composite unique) yeniden oluşturur:
    create tmp -> INSERT ... SELECT (store_id=1) -> DROP old -> RENAME tmp -> old.
    Tüm adımlar AYNI connection (conn) üzerinden yapılır — SQLite tek-yazar
    kısıtı nedeniyle ayrı bir engine bağlantısı açmak "database is locked" riski taşır.
    """
    tmp_name = f"{table}__mt_new"

    # Eski tablonun kolon sırasını al (yeni şemada bunlar birebir aynı isimlerle var,
    # sadece store_id + constraint farkı var).
    old_columns = [c["name"] for c in inspector.get_columns(table)]

    # Eski tablodaki adlandırılmış index'leri düşür — yeni (tmp) tablo aynı Index isimlerini
    # (ör. 'idx_product_id') kullanacağı için isim çakışması olmasın diye önce eskiler silinir.
    # (SQLite'ın UNIQUE constraint için ürettiği otomatik "sqlite_autoindex_*" index'lere
    # dokunmuyoruz; onlar tablo düşürülünce kendiliğinden gider ve isimleri tmp tabloyla çakışmaz.)
    for idx in inspector.get_indexes(table):
        idx_name = idx.get("name")
        if idx_name and not idx_name.startswith("sqlite_autoindex"):
            conn.execute(text(f'DROP INDEX IF EXISTS "{idx_name}"'))

    # Yeni (hedef) şemayı models.py'deki güncel Table tanımından, geçici isimle klonla.
    new_table = model_cls.__table__.tometadata(model_cls.metadata, name=tmp_name)
    new_table.create(bind=conn, checkfirst=True)

    col_list = ", ".join(old_columns)
    conn.execute(text(
        f"INSERT INTO {tmp_name} ({col_list}, store_id) "
        f"SELECT {col_list}, 1 FROM {table}"
    ))

    conn.execute(text(f"DROP TABLE {table}"))
    conn.execute(text(f"ALTER TABLE {tmp_name} RENAME TO {table}"))
    # Geçici Table nesnesini paylaşılan metadata'dan temizle (hijyen — DB'de zaten yeniden adlandırıldı)
    model_cls.metadata.remove(new_table)

    # SQLAlchemy'nin index=True kolonlar için otomatik ürettiği index isimleri tmp tablo
    # adını (__mt_new) içeriyor (ör. ix_products__mt_new_product_id) — RENAME bu isimleri
    # değiştirmez (yalnızca UNIQUE/PK autoindex'leri SQLite otomatik yeniden adlandırır).
    # Kozmetik ama kafa karıştırıcı; temiz isimle DROP+CREATE yaparak düzeltiyoruz.
    for row in conn.execute(text(f'PRAGMA index_list("{table}")')).fetchall():
        idx_name = row[1]
        if "__mt_new" not in idx_name:
            continue
        clean_name = idx_name.replace("__mt_new", "")
        cols = [r[2] for r in conn.execute(text(f'PRAGMA index_info("{idx_name}")')).fetchall()]
        conn.execute(text(f'DROP INDEX "{idx_name}"'))
        col_list_sql = ", ".join(f'"{c}"' for c in cols)
        conn.execute(text(f'CREATE INDEX IF NOT EXISTS "{clean_name}" ON {table} ({col_list_sql})'))

    print(f"[Migration] {table}: composite unique constraint'e geçirildi (tablo yeniden oluşturuldu)")


def _already_migrated(inspector) -> bool:
    """users tablosu var VE tüm store_id hedef tabloları store_id kolonuna sahipse
    migration tamamen uygulanmış demektir — tekrar tekrar yedek almayı/iş yapmayı önler."""
    tables = inspector.get_table_names()
    if "users" not in tables or "stores" not in tables:
        return False
    for table in ALL_STORE_ID_TABLES:
        if table in tables and not _table_has_column(inspector, table, "store_id"):
            return False
    return True


def run_multitenant_migration(engine) -> None:
    if engine is None:
        print("[Migration] Engine yok, çok-kiracılı migration atlandı (ghost mode).")
        return

    # database/models.py içindeki güncel (store_id'li) modeller
    from database import models as m

    inspector = inspect(engine)
    if _already_migrated(inspector):
        print("[Migration] Çok-kiracılı şema zaten uygulanmış, atlanıyor.")
        return

    db_path = Path(str(engine.url.database))
    if db_path.exists():
        _backup(db_path)

    inspector = inspect(engine)

    # 1) Yeni tabloları oluştur (users/stores/store_credentials/otp_codes) — sadece eksikse.
    m.Base.metadata.create_all(
        bind=engine,
        tables=[m.User.__table__, m.Store.__table__, m.StoreCredential.__table__, m.OTPCode.__table__],
        checkfirst=True,
    )

    model_by_table = {
        "products": m.Product,
        "orders": m.Order,
        "cache_metadata": m.CacheMetadata,
        "return_refunds": m.ReturnRefund,
        "campaigns": m.Campaign,
        "barcode_templates": m.BarcodeTemplate,
        "qa_records": m.QARecord,
        "size_charts": m.SizeChart,
    }

    # ÖNEMLİ: tüm inspector sorguları AYNI connection (conn) üzerinden yapılmalı.
    # inspect(engine) çağrısı her seferinde yeni bir bağlantı açar; bu bağlantı,
    # aynı anda açık olan yazma-transaction'ı (conn) ile çakışıp SQLite'ta
    # "database is locked" hatası verir (SQLite tek-yazarlı kilit modeli).
    with engine.begin() as conn:
        _bootstrap_default_owner(conn)

        insp = inspect(conn)

        for table in SIMPLE_TABLES:
            if table not in insp.get_table_names():
                continue
            if _table_has_column(insp, table, "store_id"):
                continue
            _add_store_id_simple(conn, table)

        for table in REBUILD_TABLES:
            if table not in insp.get_table_names():
                continue
            if _table_has_column(insp, table, "store_id"):
                continue
            _rebuild_with_composite_unique(conn, insp, table, model_by_table[table])

    print("[Migration] Çok-kiracılı migration tamamlandı (idempotent — tekrar çalıştırmak güvenli).")


if __name__ == "__main__":
    # Not: init_db() zaten run_migrations() + run_multitenant_migration()'ı içeriden çağırıyor
    # (bkz. database/db.py) — burada AYRICA çağırmıyoruz, aksi halde aynı transaction mantığı
    # iki kez tetiklenir ve gereksiz ikinci bir yedek/kilit riski oluşur.
    import sys
    from pathlib import Path as _Path
    sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))
    from database.db import init_db

    init_db()
