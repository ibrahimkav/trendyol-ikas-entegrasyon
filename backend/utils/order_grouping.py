"""
Kargo hazırlığı için sipariş sıralama: aynı ürünü içeren siparişler art arda gelir.

Etiketler bu sırayla basılınca paketlemede aynı ürün bir kere raftan alınıp
peş peşe paketlenebilir. Sıralama:
  1. Tek çeşit ürün içeren siparişler önce — ürün adına göre (beden/renk adın
     içinde olduğundan aynı model bir arada, aynı beden yan yana), sonra ürün
     barkoduna, sonra adede göre.
  2. Birden çok çeşit ürün içeren (karma) siparişler sonra — içerdikleri ürün
     listesine göre; aynı kombinasyondaki siparişler yan yana.
  Eşitlikte sipariş tarihi (eskiden yeniye), sonra sipariş numarası.

Trendyol satır alanları sürüme göre değişebildiğinden ürün adı/kodu için birden
çok alan denenir. Sıralama hiçbir girdide hata fırlatmaz: anahtarı hesaplanamayan
sipariş sona konur, beklenmedik bir hatada liste olduğu gibi döner — tek bir bozuk
sipariş toplu etiket yazdırmayı durduramaz.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, Iterable, List, Tuple

logger = logging.getLogger(__name__)

_TR_FOLD = str.maketrans({"İ": "i", "I": "ı"})


def _fold(text: Any) -> str:
    """Türkçe uyumlu büyük/küçük harf duyarsız karşılaştırma metni."""
    return " ".join(str(text or "").translate(_TR_FOLD).casefold().split())


def _natural(text: str) -> Tuple:
    """'beden 28' < 'beden 30' < 'beden 100' (sayılar sayı olarak karşılaştırılır).
    isdecimal(): \\d ile birebir aynı küme — '²', '①' gibi isdigit() olup int()'e
    çevrilemeyen karakterler metin parçası sayılır."""
    return tuple((0, int(part), "") if part.isdecimal() else (1, 0, part) for part in re.split(r"(\d+)", text) if part)


def line_product_name(line: Dict[str, Any]) -> str:
    """Ürün adı; beden adda yoksa (ayrı productSize alanındaysa) sona eklenir ki
    aynı modelin bedenleri ayırt edilip sıralanabilsin."""
    name = str(line.get("productName") or line.get("productTitle") or line.get("name") or "").strip()
    size = str(line.get("productSize") or "").strip()
    if size and _fold(size) not in _fold(name):
        name = f"{name}, {size}" if name else size
    return name


def line_product_code(line: Dict[str, Any]) -> str:
    for key in ("barcode", "merchantSku", "sku", "stockCode", "productCode", "contentId", "productId"):
        value = line.get(key)
        if value not in (None, ""):
            return str(value).strip()
    return ""


def _line_quantity(line: Dict[str, Any]) -> int:
    try:
        return int(line.get("quantity") or line.get("qty") or 1)
    except (TypeError, ValueError):
        return 1


def _product_key(line: Dict[str, Any]) -> Tuple:
    return (_natural(_fold(line_product_name(line))), _natural(_fold(line_product_code(line))))


def _order_date(order: Dict[str, Any]) -> float:
    raw = order.get("orderDate")
    try:
        return float(raw)  # Trendyol: epoch milisaniye
    except (TypeError, ValueError):
        return float("inf")


def order_products(order: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Siparişteki ürünler (aynı ürün birden çok satırda ise adetleri toplanır), sıralı."""
    merged: Dict[Tuple, Dict[str, Any]] = {}
    lines = order.get("lines") if isinstance(order, dict) else None
    for line in lines if isinstance(lines, list) else []:
        if not isinstance(line, dict):
            continue
        key = _product_key(line)
        entry = merged.setdefault(key, {
            "name": line_product_name(line) or "Ürün",
            "code": line_product_code(line),
            "quantity": 0,
        })
        entry["quantity"] += _line_quantity(line)
    return [merged[k] for k in sorted(merged)]


def product_summary(order: Dict[str, Any]) -> str:
    """Etiket önizlemesinde gösterilecek kısa ürün özeti: 'Ürün A ×2 + Ürün B ×1'."""
    return " + ".join(f"{p['name']} ×{p['quantity']}" for p in order_products(order))


def _sort_key(order: Dict[str, Any]) -> Tuple:
    try:
        return _product_sort_key(order)
    except Exception:  # beklenmedik veri: siparişi sona koy, yazdırmayı durdurma
        logger.warning("Sipariş ürün sıralama anahtarı hesaplanamadı: %r", order.get("orderNumber") if isinstance(order, dict) else order)
        return (2,)


def _product_sort_key(order: Dict[str, Any]) -> Tuple:
    products = order_products(order)
    keys = tuple(_product_key({"productName": p["name"], "barcode": p["code"]}) for p in products)
    quantities = tuple(p["quantity"] for p in products)
    is_mixed = 1 if len(products) > 1 else 0
    number = str(order.get("orderNumber") or order.get("id") or "")
    # Ürünü olmayan sipariş en sona
    return (0 if products else 1, is_mixed, keys, quantities, _order_date(order), _natural(number))


def sort_orders_by_product(orders: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Trendyol sipariş sözlüklerini aynı ürünler art arda gelecek şekilde sıralar
    (girdiyi değiştirmez, yeni liste döner). Hata durumunda orijinal sıra döner."""
    orders = list(orders)
    try:
        return sorted(orders, key=_sort_key)
    except Exception:
        logger.exception("Siparişler ürüne göre sıralanamadı — Trendyol sırası kullanılıyor")
        return orders
