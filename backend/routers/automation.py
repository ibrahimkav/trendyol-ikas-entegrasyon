"""
Otomasyon Kuralları Router
Otomatik fiyat güncelleme ve stok bazlı kurallar
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
from collections import defaultdict
import json
from sqlalchemy.orm import Session

router = APIRouter()

# Database modülünü optional olarak yükle (ghost mode)
try:
    from database.db import get_db
    from database.models import Store, AutomationRuleRecord
    from security import get_current_store
    from utils.store_trendyol import resolve_trendyol_creds, fetch_orders as _fetch_store_orders
    _db_available = True
except Exception:
    _db_available = False
    def get_db():
        raise HTTPException(status_code=503, detail="Database not available (ghost mode)")

    def get_current_store():
        raise HTTPException(status_code=503, detail="Database not available (ghost mode)")


class AutomationRule(BaseModel):
    """Otomasyon kuralı modeli"""
    id: Optional[str] = None
    name: str
    rule_type: str  # "price_update", "stock_based_price", "auto_restock"
    enabled: bool = True
    conditions: Dict[str, Any]  # Kural koşulları
    actions: Dict[str, Any]  # Kural eylemleri
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# w3-automation-persist: kurallar artık AutomationRuleRecord tablosunda KALICI
# (önceden bu module-level dict tek depolamaydı, her restart'ta kayboluyordu —
# hive/docs sürüm geçmişinde "production'da database kullanılmalı" notuyla
# bilinçli bırakılmıştı, şimdi giderildi). Bu dict SADECE ghost mode'da
# (_db_available=False, DB modülü hiç yüklenemiyorsa) kullanılır.
_ghost_rules: Dict[int, Dict[str, AutomationRule]] = {}


def _sid(store) -> int:
    """Ghost mode'da (DB yok) store None olur — tüm ghost istekleri tek (0) alanı paylaşır."""
    return store.id if store else 0


def _record_to_rule(rec: "AutomationRuleRecord") -> AutomationRule:
    """DB satırını, router'ın geri kalanının (execute_automation_rule dahil)
    beklediği AutomationRule pydantic nesnesine çevirir — çağıran kodun geri
    kalanı DEĞİŞMEDEN yeniden kullanılabiliyor."""
    return AutomationRule(
        id=rec.id,
        name=rec.name,
        rule_type=rec.rule_type,
        enabled=rec.enabled,
        conditions=json.loads(rec.conditions_json),
        actions=json.loads(rec.actions_json),
        created_at=rec.created_at.isoformat() if rec.created_at else None,
        updated_at=rec.updated_at.isoformat() if rec.updated_at else None,
    )


def get_trendyol_orders_data(creds=None) -> List[Dict]:
    """Bu mağazanın Trendyol siparişlerini çeker (Wave3 kalıbı: per-store, env DEĞİL).
    NOT: creds=None → [] (henüz dönüştürülmemiş çağıranlar için güvenli köprü)."""
    if creds is None:
        return []
    try:
        return _fetch_store_orders(creds, max_pages=100, size=200)
    except Exception:
        return []


@router.get("/rules")
async def get_all_rules(
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Session = Depends(get_db) if _db_available else None,
):
    """Bu mağazanın otomasyon kurallarını listeler. w3-automation-leak: store-scoped.
    w3-automation-persist: DB'den okunuyor (ghost mode'da bellek fallback)."""
    if db is not None:
        records = db.query(AutomationRuleRecord).filter(AutomationRuleRecord.store_id == _sid(store)).all()
        rules = [_record_to_rule(r) for r in records]
    else:
        rules = list(_ghost_rules.setdefault(_sid(store), {}).values())
    return {
        "rules": [rule.dict() for rule in rules],
        "total": len(rules)
    }


@router.get("/rules/{rule_id}")
async def get_rule(
    rule_id: str,
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Session = Depends(get_db) if _db_available else None,
):
    """Belirli bir kuralı getirir. w3-automation-leak: store-scoped."""
    if db is not None:
        rec = db.query(AutomationRuleRecord).filter(
            AutomationRuleRecord.store_id == _sid(store), AutomationRuleRecord.id == rule_id
        ).first()
        if not rec:
            raise HTTPException(status_code=404, detail="Kural bulunamadı")
        return _record_to_rule(rec).dict()

    rules = _ghost_rules.setdefault(_sid(store), {})
    if rule_id not in rules:
        raise HTTPException(status_code=404, detail="Kural bulunamadı")
    return rules[rule_id].dict()


@router.post("/rules")
async def create_rule(
    rule: AutomationRule,
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Session = Depends(get_db) if _db_available else None,
):
    """Yeni otomasyon kuralı oluşturur. w3-automation-leak: store-scoped."""
    import uuid

    rule_id = str(uuid.uuid4())
    rule.id = rule_id
    rule.created_at = datetime.now().isoformat()
    rule.updated_at = datetime.now().isoformat()

    if db is not None:
        rec = AutomationRuleRecord(
            id=rule_id,
            store_id=_sid(store),
            name=rule.name,
            rule_type=rule.rule_type,
            enabled=rule.enabled,
            conditions_json=json.dumps(rule.conditions, ensure_ascii=False),
            actions_json=json.dumps(rule.actions, ensure_ascii=False),
        )
        db.add(rec)
        db.commit()
        db.refresh(rec)
        rule = _record_to_rule(rec)
    else:
        _ghost_rules.setdefault(_sid(store), {})[rule_id] = rule

    return {
        "message": "Kural oluşturuldu",
        "rule": rule.dict()
    }


@router.put("/rules/{rule_id}")
async def update_rule(
    rule_id: str,
    rule: AutomationRule,
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Session = Depends(get_db) if _db_available else None,
):
    """Mevcut kuralı günceller. w3-automation-leak: store-scoped."""
    if db is not None:
        rec = db.query(AutomationRuleRecord).filter(
            AutomationRuleRecord.store_id == _sid(store), AutomationRuleRecord.id == rule_id
        ).first()
        if not rec:
            raise HTTPException(status_code=404, detail="Kural bulunamadı")

        rec.name = rule.name
        rec.rule_type = rule.rule_type
        rec.enabled = rule.enabled
        rec.conditions_json = json.dumps(rule.conditions, ensure_ascii=False)
        rec.actions_json = json.dumps(rule.actions, ensure_ascii=False)
        db.commit()
        db.refresh(rec)
        rule = _record_to_rule(rec)
    else:
        rules = _ghost_rules.setdefault(_sid(store), {})
        if rule_id not in rules:
            raise HTTPException(status_code=404, detail="Kural bulunamadı")

        rule.id = rule_id
        rule.updated_at = datetime.now().isoformat()
        rule.created_at = rules[rule_id].created_at
        rules[rule_id] = rule

    return {
        "message": "Kural güncellendi",
        "rule": rule.dict()
    }


@router.delete("/rules/{rule_id}")
async def delete_rule(
    rule_id: str,
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Session = Depends(get_db) if _db_available else None,
):
    """Kuralı siler. w3-automation-leak: store-scoped."""
    if db is not None:
        rec = db.query(AutomationRuleRecord).filter(
            AutomationRuleRecord.store_id == _sid(store), AutomationRuleRecord.id == rule_id
        ).first()
        if not rec:
            raise HTTPException(status_code=404, detail="Kural bulunamadı")
        db.delete(rec)
        db.commit()
    else:
        rules = _ghost_rules.setdefault(_sid(store), {})
        if rule_id not in rules:
            raise HTTPException(status_code=404, detail="Kural bulunamadı")
        del rules[rule_id]

    return {"message": "Kural silindi"}


@router.post("/rules/{rule_id}/toggle")
async def toggle_rule(
    rule_id: str,
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Session = Depends(get_db) if _db_available else None,
):
    """Kuralı aktif/pasif yapar. w3-automation-leak: store-scoped."""
    if db is not None:
        rec = db.query(AutomationRuleRecord).filter(
            AutomationRuleRecord.store_id == _sid(store), AutomationRuleRecord.id == rule_id
        ).first()
        if not rec:
            raise HTTPException(status_code=404, detail="Kural bulunamadı")
        rec.enabled = not rec.enabled
        db.commit()
        db.refresh(rec)
        rule = _record_to_rule(rec)
    else:
        rules = _ghost_rules.setdefault(_sid(store), {})
        if rule_id not in rules:
            raise HTTPException(status_code=404, detail="Kural bulunamadı")
        rule = rules[rule_id]
        rule.enabled = not rule.enabled
        rule.updated_at = datetime.now().isoformat()

    return {
        "message": f"Kural {'aktif' if rule.enabled else 'pasif'} edildi",
        "rule": rule.dict()
    }


@router.get("/rules/{rule_id}/execute")
async def execute_rule(
    rule_id: str,
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Session = Depends(get_db) if _db_available else None
):
    """Kuralı manuel olarak çalıştırır. w3-hardening: per-store credential + w3-automation-leak: store-scoped rule lookup."""
    if db is not None:
        rec = db.query(AutomationRuleRecord).filter(
            AutomationRuleRecord.store_id == _sid(store), AutomationRuleRecord.id == rule_id
        ).first()
        if not rec:
            raise HTTPException(status_code=404, detail="Kural bulunamadı")
        rule = _record_to_rule(rec)
    else:
        rules = _ghost_rules.setdefault(_sid(store), {})
        if rule_id not in rules:
            raise HTTPException(status_code=404, detail="Kural bulunamadı")
        rule = rules[rule_id]

    if not rule.enabled:
        raise HTTPException(status_code=400, detail="Kural pasif durumda")

    # Kuralı çalıştır
    creds = resolve_trendyol_creds(db, store)
    result = await execute_automation_rule(rule, creds)

    return {
        "message": "Kural çalıştırıldı",
        "result": result
    }


async def execute_automation_rule(rule: AutomationRule, creds=None) -> Dict[str, Any]:
    """Otomasyon kuralını çalıştırır"""
    orders = get_trendyol_orders_data(creds)

    if rule.rule_type == "price_update":
        return await execute_price_update_rule(rule, orders)
    elif rule.rule_type == "stock_based_price":
        return await execute_stock_based_price_rule(rule, orders)
    else:
        return {
            "success": False,
            "message": "Bilinmeyen kural tipi"
        }


async def execute_price_update_rule(rule: AutomationRule, orders: List[Dict]) -> Dict[str, Any]:
    """Fiyat güncelleme kuralını çalıştırır"""
    conditions = rule.conditions
    actions = rule.actions

    # Ürün performansını hesapla
    product_performance = defaultdict(lambda: {
        "sales_count": 0,
        "total_revenue": 0.0,
        "last_price": 0.0,
        "orders": []
    })

    for order in orders:
        lines = order.get("lines", []) or order.get("orderLines", []) or order.get("items", []) or []
        if isinstance(lines, dict):
            lines = [lines]

        for line in lines:
            product_id = (
                line.get("productId") or
                line.get("product_id") or
                line.get("barcode") or
                ""
            )

            if not product_id:
                continue

            price = line.get("price", 0) or line.get("salePrice", 0) or 0.0
            quantity = line.get("quantity", 1) or 1

            product_performance[str(product_id)]["sales_count"] += quantity
            product_performance[str(product_id)]["total_revenue"] += float(price) * quantity
            product_performance[str(product_id)]["last_price"] = float(price)
            product_performance[str(product_id)]["orders"].append({
                "price": float(price),
                "quantity": quantity
            })

    # Koşulları kontrol et ve eylemleri uygula
    updated_products = []

    for product_id, perf in product_performance.items():
        should_update = False
        new_price = perf["last_price"]

        # Koşul kontrolü
        if conditions.get("min_sales") and perf["sales_count"] >= conditions["min_sales"]:
            should_update = True

        if conditions.get("min_revenue") and perf["total_revenue"] >= conditions["min_revenue"]:
            should_update = True

        if should_update:
            # Eylem uygula
            if actions.get("price_change_type") == "percentage":
                change = actions.get("price_change_value", 0)
                new_price = perf["last_price"] * (1 + change / 100)
            elif actions.get("price_change_type") == "fixed":
                change = actions.get("price_change_value", 0)
                new_price = perf["last_price"] + change

            updated_products.append({
                "product_id": product_id,
                "old_price": perf["last_price"],
                "new_price": round(new_price, 2),
                "sales_count": perf["sales_count"]
            })

    return {
        "success": True,
        "updated_products": updated_products,
        "total_updated": len(updated_products)
    }


async def execute_stock_based_price_rule(rule: AutomationRule, orders: List[Dict]) -> Dict[str, Any]:
    """Stok bazlı fiyat kuralını çalıştırır"""
    from datetime import datetime, timedelta

    conditions = rule.conditions
    actions = rule.actions

    # Ürün stok tahmini
    product_stock = defaultdict(lambda: {
        "sales_count": 0,
        "last_sale_date": None,
        "estimated_stock": 0,
        "current_price": 0.0
    })

    today = datetime.now()

    for order in orders:
        order_date_str = order.get("orderDate") or order.get("order_date")
        if order_date_str:
            try:
                if isinstance(order_date_str, str) and 'T' in order_date_str:
                    order_date = datetime.fromisoformat(order_date_str.replace('Z', '+00:00'))
                    if order_date.tzinfo:
                        order_date = order_date.replace(tzinfo=None)
                elif isinstance(order_date_str, (int, float)):
                    timestamp = float(order_date_str)
                    if timestamp > 1e12:
                        timestamp = timestamp / 1000
                    order_date = datetime.fromtimestamp(timestamp)
                else:
                    continue
            except:
                continue
        else:
            continue

        lines = order.get("lines", []) or order.get("orderLines", []) or order.get("items", []) or []
        if isinstance(lines, dict):
            lines = [lines]

        for line in lines:
            product_id = (
                line.get("productId") or
                line.get("product_id") or
                line.get("barcode") or
                ""
            )

            if not product_id:
                continue

            price = line.get("price", 0) or line.get("salePrice", 0) or 0.0
            quantity = line.get("quantity", 1) or 1

            product_stock[str(product_id)]["sales_count"] += quantity
            product_stock[str(product_id)]["current_price"] = float(price)

            if not product_stock[str(product_id)]["last_sale_date"] or order_date > product_stock[str(product_id)]["last_sale_date"]:
                product_stock[str(product_id)]["last_sale_date"] = order_date

    # Stok tahmini ve fiyat güncelleme
    updated_products = []

    for product_id, stock_info in product_stock.items():
        # Basit stok tahmini (son 30 günlük satış bazlı)
        days_since_last_sale = (today - stock_info["last_sale_date"]).days if stock_info["last_sale_date"] else 999

        # Son 30 gün içinde satış varsa
        if days_since_last_sale <= 30:
            estimated_stock = max(0, stock_info["sales_count"] - (days_since_last_sale * stock_info["sales_count"] / 30))
        else:
            estimated_stock = 0

        stock_info["estimated_stock"] = int(estimated_stock)

        # Koşul kontrolü
        should_update = False
        new_price = stock_info["current_price"]

        min_stock = conditions.get("min_stock", 10)
        max_stock = conditions.get("max_stock", 100)

        if conditions.get("low_stock_action") and estimated_stock <= min_stock:
            # Düşük stok - fiyat artır
            if actions.get("low_stock_price_change_type") == "percentage":
                change = actions.get("low_stock_price_change_value", 0)
                new_price = stock_info["current_price"] * (1 + change / 100)
            elif actions.get("low_stock_price_change_type") == "fixed":
                change = actions.get("low_stock_price_change_value", 0)
                new_price = stock_info["current_price"] + change
            should_update = True

        if conditions.get("high_stock_action") and estimated_stock >= max_stock:
            # Yüksek stok - fiyat düşür
            if actions.get("high_stock_price_change_type") == "percentage":
                change = actions.get("high_stock_price_change_value", 0)
                new_price = stock_info["current_price"] * (1 - abs(change) / 100)
            elif actions.get("high_stock_price_change_type") == "fixed":
                change = actions.get("high_stock_price_change_value", 0)
                new_price = stock_info["current_price"] - abs(change)
            should_update = True

        if should_update:
            updated_products.append({
                "product_id": product_id,
                "old_price": stock_info["current_price"],
                "new_price": round(new_price, 2),
                "estimated_stock": int(estimated_stock),
                "reason": "low_stock" if estimated_stock <= min_stock else "high_stock"
            })

    return {
        "success": True,
        "updated_products": updated_products,
        "total_updated": len(updated_products)
    }


@router.get("/templates")
async def get_rule_templates():
    """Hazır kural şablonlarını döner"""
    return {
        "templates": [
            {
                "name": "Düşük Stokta Fiyat Artır",
                "rule_type": "stock_based_price",
                "description": "Stok 10'un altına düştüğünde fiyatı %10 artır",
                "conditions": {
                    "min_stock": 10,
                    "low_stock_action": True
                },
                "actions": {
                    "low_stock_price_change_type": "percentage",
                    "low_stock_price_change_value": 10
                }
            },
            {
                "name": "Yüksek Stokta Fiyat Düşür",
                "rule_type": "stock_based_price",
                "description": "Stok 100'ün üstüne çıktığında fiyatı %5 düşür",
                "conditions": {
                    "max_stock": 100,
                    "high_stock_action": True
                },
                "actions": {
                    "high_stock_price_change_type": "percentage",
                    "high_stock_price_change_value": 5
                }
            },
            {
                "name": "Yüksek Satışta Fiyat Artır",
                "rule_type": "price_update",
                "description": "Aylık satış 50'yi geçtiğinde fiyatı %5 artır",
                "conditions": {
                    "min_sales": 50
                },
                "actions": {
                    "price_change_type": "percentage",
                    "price_change_value": 5
                }
            }
        ]
    }

