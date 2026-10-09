"""
Hafif SQLite şema migrasyonları — mevcut veriyi koruyarak yeni kolonlar ekler.
"""
from datetime import datetime, timedelta

from sqlalchemy import inspect, text


def run_migrations(engine) -> None:
    """Eksik kolonları ALTER TABLE ile ekler."""
    if engine is None:
        return

    inspector = inspect(engine)
    tables = inspector.get_table_names()

    migrations = [
        ("products", "default_cost", "FLOAT DEFAULT 0.0"),
        ("order_lines", "unit_cost", "FLOAT DEFAULT 0.0"),
        ("products", "desi", "FLOAT DEFAULT 0.0"),  # Wave2b: kargo tahmini + Hakediş&Desi Kontrolü
        ("products", "content_id", "VARCHAR"),  # w3-product-image-backend: ürün görseli CDN URL'i için
        ("products", "image_url", "VARCHAR"),  # w3-image-url-store: Trendyol API'nin gerçek images[0].url'i (kalıptan üretilemez)
    ]

    with engine.connect() as conn:
        for table, column, col_type in migrations:
            if table not in tables:
                continue
            existing = {c["name"] for c in inspector.get_columns(table)}
            if column in existing:
                continue
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))
            conn.commit()
            print(f"[Migration] Added {table}.{column}")


def prune_old_change_history(engine, retention_days: int = 365) -> None:
    """w3-write-audit-trail hacim kararı: product_change_history sonsuza kadar
    büyümesin diye RETENTION_DAYS'ten eski kayıtlar her app-start'ta silinir.
    365 gün seçildi — 300 TL vakası gibi bir soruşturma genelde günler/haftalar
    içinde yapılır, ama "geçen çeyrek ne değişmişti" gibi daha geniş bir pencereyi
    de bir yıl boyunca destekler; sonsuz saklamak yerine sınırlı ama cömert bir
    pencere. Tablo yoksa (henüz create_all() ile oluşmadıysa) sessizce çıkar."""
    if engine is None:
        return
    inspector = inspect(engine)
    if "product_change_history" not in inspector.get_table_names():
        return
    cutoff = (datetime.now() - timedelta(days=retention_days)).isoformat(sep=" ")
    with engine.connect() as conn:
        result = conn.execute(
            text("DELETE FROM product_change_history WHERE changed_at < :cutoff"),
            {"cutoff": cutoff},
        )
        conn.commit()
        if result.rowcount:
            print(f"[Migration] Pruned {result.rowcount} product_change_history rows older than {retention_days} days")
