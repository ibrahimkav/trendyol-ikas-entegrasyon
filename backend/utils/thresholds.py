"""
Store bazında ayarlanabilir uyarı eşikleri — w3-configurable-thresholds.
Spec: hive/docs/thresholds-spec.md. Varsayılan değerler, koddaki ESKİ
gömülü sabitlerle AYNIDIR (geriye dönük uyumluluk: hiç ayar girilmemiş
mağazada davranış değişmez).
"""
from typing import Optional

from sqlalchemy.orm import Session

from database.models import StoreThreshold

DEFAULT_MARGIN_WARNING_THRESHOLD = 15.0  # % — eski financial.py sabitiyle aynı
DEFAULT_LOW_STOCK_FLOOR = 5  # eski inventory.py sabitiyle aynı
DEFAULT_LOW_STOCK_SALES_RATIO = 0.15  # eski inventory.py sabitiyle aynı

MARGIN_WARNING_THRESHOLD_MIN, MARGIN_WARNING_THRESHOLD_MAX = 0.0, 100.0
LOW_STOCK_FLOOR_MIN, LOW_STOCK_FLOOR_MAX = 0, 1000
LOW_STOCK_SALES_RATIO_MIN, LOW_STOCK_SALES_RATIO_MAX = 0.01, 1.0


def get_effective_thresholds(db: Session, store_id: int) -> dict:
    """Bu mağaza için EFEKTİF eşik değerlerini döner — DB'de satır yoksa veya
    alan NULL ise kod-gömülü varsayılan kullanılır. Her zaman TAM şema döner
    (satır hiç yoksa bile), çağıran taraf None kontrolü yapmak zorunda kalmaz."""
    row: Optional[StoreThreshold] = (
        db.query(StoreThreshold).filter(StoreThreshold.store_id == store_id).first()
    )
    return {
        "margin_warning_threshold": (
            row.margin_warning_threshold
            if row and row.margin_warning_threshold is not None
            else DEFAULT_MARGIN_WARNING_THRESHOLD
        ),
        "low_stock_floor": (
            row.low_stock_floor
            if row and row.low_stock_floor is not None
            else DEFAULT_LOW_STOCK_FLOOR
        ),
        "low_stock_sales_ratio": (
            row.low_stock_sales_ratio
            if row and row.low_stock_sales_ratio is not None
            else DEFAULT_LOW_STOCK_SALES_RATIO
        ),
        "is_customized": {
            "margin_warning_threshold": bool(row and row.margin_warning_threshold is not None),
            "low_stock_floor": bool(row and row.low_stock_floor is not None),
            "low_stock_sales_ratio": bool(row and row.low_stock_sales_ratio is not None),
        },
    }
