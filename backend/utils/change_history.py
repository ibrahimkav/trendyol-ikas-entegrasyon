"""
w3-write-audit-trail: gerçek satıcı verisine (maliyet/desi/fiyat) yapılan
yazmaların izlenebilir geçmişi. 300 TL vakasının dersi: KİM/NEREDEN yazdığını
kanıtlayamadık, eski değeri geri getiremedik — bu modül o iki boşluğu kapatır.

Kullanım: yeni değeri ATAMADAN ÖNCE, eski değeri okurken çağır — eski değer
üzerine yazıldıktan sonra kaybolur, çağrı sırası önemli.
"""
from typing import Optional

from sqlalchemy.orm import Session

from database.models import ProductChangeHistory


def record_change(
    db: Session,
    store_id: int,
    product_id: str,
    field: str,
    old_value: Optional[float],
    new_value: Optional[float],
    source: str,
) -> None:
    """Bir Product alanındaki değişikliği kaydeder. Eski değer == yeni değerse
    (gerçek bir değişiklik yok — ör. CSV'de aynı değer tekrar yüklendi) hiçbir
    şey YAZMAZ, gürültü/hacim şişmesin diye. db.commit() ÇAĞIRMAZ — çağıranın
    kendi transaction'ına eklenir, aynı commit ile birlikte yazılır."""
    if old_value == new_value:
        return
    db.add(ProductChangeHistory(
        store_id=store_id,
        product_id=product_id,
        field=field,
        old_value=old_value,
        new_value=new_value,
        source=source,
    ))
