"""
Sipariş durumunun satış/ciro hesaplarına dahil edilip edilmeyeceği.

Trendyol paket durumları: Created, Picking, Invoiced, Shipped, Delivered, UnDelivered,
Cancelled, UnSupplied, Returned, AtCollectionPoint, UnPacked ...
İptal edilen, tedarik edilemeyen ve iade edilen siparişler gerçekleşmiş satış değildir;
ciro/kâr/müşteri harcaması hesaplarına katılmamalıdır (iade zararı ayrı raporlanır).
Tek doğruluk kaynağı bu modüldür — dashboard, raporlar, kâr listesi, müşteriler ve
ürün istatistikleri buradan okur.
"""
from typing import Any, Optional

NON_SALE_STATUSES = frozenset({"cancelled", "unsupplied", "returned"})


def _norm(status: Optional[Any]) -> str:
    return str(status or "").strip().replace(" ", "").replace("_", "").casefold()


def is_countable_sale(status: Optional[Any]) -> bool:
    """Durum gerçekleşmiş (ya da gerçekleşmekte olan) bir satış mı? Bilinmeyen/boş
    durum satış sayılır (eski davranışla uyumlu; veri eksikliği satışı yok saymaz)."""
    return _norm(status) not in NON_SALE_STATUSES


def order_status_of(order: Any) -> Optional[str]:
    """Trendyol sipariş sözlüğü veya Order modeli için durum alanı."""
    if isinstance(order, dict):
        return order.get("status") or order.get("shipmentPackageStatus") or order.get("orderStatus")
    return getattr(order, "status", None)
