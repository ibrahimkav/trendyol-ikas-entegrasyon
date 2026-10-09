"""
Finansal Yönetim Router
Gelir/gider takibi ve komisyon hesaplama
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, field_validator
from typing import List, Optional, Dict, Any
from pydantic import BaseModel as PydanticBaseModel
from datetime import datetime, timedelta
from collections import defaultdict
import os
import requests
import base64

from sqlalchemy.orm import Session

from database.db import get_db
from database.models import Product, Store, OrderLine, Order
from security import get_current_store
from utils.profitability import (
    compute_product_profitability,
    compute_order_profitability,
    compute_category_profitability,
    compute_return_loss,
    resolve_date_range,
)
from utils.store_trendyol import resolve_trendyol_creds, fetch_orders
from utils.thresholds import get_effective_thresholds
from utils.change_history import record_change
from utils.numeric_validation import numeric_field_error, PRICE_MAX

router = APIRouter()

# Kargo maliyeti ayarı (ürün başına TL)
CARGO_COST_PER_PRODUCT = float(os.getenv("CARGO_COST_PER_PRODUCT", "75.0"))

# KDV oranı (%10)
VAT_RATE = float(os.getenv("VAT_RATE", "10.0")) / 100  # %10 -> 0.10


class Expense(BaseModel):
    """Gider modeli"""
    id: Optional[str] = None
    name: str
    amount: float
    category: str  # "kargo", "reklam", "stok", "diğer"
    date: str
    description: Optional[str] = None
    created_at: Optional[str] = None


# Basit in-memory storage (production'da database kullanılmalı)
expenses: Dict[str, Expense] = {}


def get_trendyol_orders_data(creds=None) -> List[Dict]:
    """Bu mağazanın Trendyol siparişlerini çeker (Wave3: per-store, env DEĞİL).
    creds=None → [] (güvenli köprü); çağıranlar resolve_trendyol_creds(db, store) geçer."""
    if creds is None:
        return []
    return fetch_orders(creds)


def parse_order_date(order_date_str):
    """Sipariş tarihini parse eder"""
    if not order_date_str:
        return None
    
    try:
        if isinstance(order_date_str, str):
            if 'T' in order_date_str:
                date_str_clean = order_date_str.replace('Z', '+00:00')
                order_date = datetime.fromisoformat(date_str_clean)
                if order_date.tzinfo:
                    order_date = order_date.replace(tzinfo=None)
            else:
                order_date = datetime.strptime(order_date_str, "%Y-%m-%d")
        elif isinstance(order_date_str, (int, float)):
            timestamp = float(order_date_str)
            if timestamp > 1e12:
                timestamp = timestamp / 1000
            order_date = datetime.fromtimestamp(timestamp)
            if order_date.tzinfo:
                order_date = order_date.replace(tzinfo=None)
        else:
            return None
        return order_date
    except:
        return None


def calculate_commission(total_price: float, category: str = None) -> float:
    """
    Trendyol komisyon hesaplama
    Kategoriye göre komisyon oranları (varsayılan %10)
    """
    # Kategori bazlı komisyon oranları
    commission_rates = {
        "elektronik": 0.12,  # %12
        "giyim": 0.15,  # %15
        "ev_yasam": 0.10,  # %10
        "kozmetik": 0.12,  # %12
        "spor": 0.10,  # %10
        "kitap": 0.08,  # %8
        "oyuncak": 0.10,  # %10
    }
    
    # Kategori bulunamazsa varsayılan %10
    rate = commission_rates.get(category, 0.10) if category else 0.10
    
    return total_price * rate


@router.get("/summary")
async def get_financial_summary(period: str = "monthly", store: Store = Depends(get_current_store), db: Session = Depends(get_db)):
    """
    Finansal özet döner
    period: "daily", "weekly", "monthly", "yearly"
    """
    creds = resolve_trendyol_creds(db, store)
    orders = get_trendyol_orders_data(creds)
    
    # Period'a göre tarih filtresi
    today = datetime.now()
    if period == "daily":
        start_date = today.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = today
    elif period == "weekly":
        days_since_monday = today.weekday()
        start_date = (today - timedelta(days=days_since_monday)).replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = today
    elif period == "monthly":
        start_date = datetime(today.year, today.month, 1)
        end_date = today
    elif period == "yearly":
        start_date = datetime(today.year, 1, 1)
        end_date = today
    else:
        start_date = datetime(2020, 1, 1)
        end_date = today
    
    # Gelir hesaplama
    total_revenue = 0.0
    total_commission = 0.0
    total_cargo_cost = 0.0
    total_vat = 0.0  # KDV
    order_count = 0
    
    for order in orders:
        order_date = parse_order_date(order.get("orderDate") or order.get("order_date"))
        if order_date and start_date <= order_date <= end_date:
            total_price = order.get("totalPrice") or order.get("totalPriceValue") or order.get("totalAmount") or 0.0
            if isinstance(total_price, str):
                try:
                    total_price = float(total_price.replace(",", "."))
                except:
                    total_price = 0.0
            
            total_price = float(total_price) if total_price else 0.0
            total_revenue += total_price
            
            # KDV hesapla (gelir üzerinden %10)
            # KDV dahil fiyat üzerinden KDV'yi çıkar: KDV = Fiyat / (1 + KDV Oranı) * KDV Oranı
            # Veya basitçe: KDV = Fiyat * (KDV Oranı / (1 + KDV Oranı))
            # %10 KDV için: KDV = Fiyat * 0.10 / 1.10 = Fiyat * 0.0909...
            vat_amount = total_price * (VAT_RATE / (1 + VAT_RATE))
            total_vat += vat_amount
            
            # Komisyon hesapla
            category = order.get("categoryName") or order.get("category_name") or ""
            commission = calculate_commission(total_price, category)
            total_commission += commission
            
            # Kargo maliyeti - API'den gerçek değeri çekmeye çalış
            cargo_cost = 0.0
            
            # Önce API'den kargo maliyeti bilgisini kontrol et
            cargo_cost_fields = [
                "cargoCost",
                "cargo_cost",
                "shippingCost",
                "shipping_cost",
                "cargoPrice",
                "cargo_price",
                "shipmentCost",
                "shipment_cost",
                "deliveryCost",
                "delivery_cost"
            ]
            
            for field in cargo_cost_fields:
                value = order.get(field)
                if value:
                    try:
                        if isinstance(value, str):
                            cargo_cost = float(value.replace(",", "."))
                        else:
                            cargo_cost = float(value)
                        if cargo_cost > 0:
                            break
                    except:
                        continue
            
            # Eğer API'den kargo maliyeti bulunamadıysa
            # Ürün başına kargo maliyeti hesapla
            if cargo_cost == 0.0:
                # Siparişteki ürün sayısını hesapla
                lines = order.get("lines", []) or order.get("orderLines", []) or order.get("items", []) or []
                if isinstance(lines, dict):
                    lines = [lines]
                
                product_count = 0
                for line in lines:
                    quantity = line.get("quantity", 1) or line.get("qty", 1) or 1
                    product_count += quantity
                
                # Ürün sayısı 0 ise, en az 1 ürün kabul et
                if product_count == 0:
                    product_count = 1
                
                # Ürün başına kargo maliyeti hesapla
                cargo_cost = product_count * CARGO_COST_PER_PRODUCT
            
            total_cargo_cost += cargo_cost
            order_count += 1
    
    # Giderler
    total_expenses = sum(exp.amount for exp in expenses.values())
    period_expenses = sum(
        exp.amount for exp in expenses.values()
        if exp.date and start_date.date() <= datetime.fromisoformat(exp.date).date() <= end_date.date()
    )
    
    # Net kâr (KDV dahil gelir - KDV - Komisyon - Kargo - Diğer Giderler)
    net_profit = total_revenue - total_vat - total_commission - total_cargo_cost - period_expenses
    
    return {
        "period": period,
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
        "total_revenue": round(total_revenue, 2),
        "total_vat": round(total_vat, 2),
        "vat_rate": VAT_RATE * 100,  # Yüzde olarak
        "total_commission": round(total_commission, 2),
        "total_cargo_cost": round(total_cargo_cost, 2),
        "total_expenses": round(period_expenses, 2),
        "net_profit": round(net_profit, 2),
        "order_count": order_count,
        "average_order_value": round(total_revenue / order_count, 2) if order_count > 0 else 0.0,
        "profit_margin": round((net_profit / total_revenue * 100), 2) if total_revenue > 0 else 0.0,
        "cargo_cost_per_product": CARGO_COST_PER_PRODUCT,
        "note": f"Kargo maliyeti ürün başına {CARGO_COST_PER_PRODUCT} TL, KDV %{VAT_RATE * 100} olarak hesaplanmaktadır."
    }


@router.get("/revenue-breakdown")
async def get_revenue_breakdown(period: str = "monthly", store: Store = Depends(get_current_store), db: Session = Depends(get_db)):
    """Gelir dağılımını döner (kategori, günlük, vb.)"""
    creds = resolve_trendyol_creds(db, store)
    orders = get_trendyol_orders_data(creds)
    
    today = datetime.now()
    if period == "monthly":
        start_date = datetime(today.year, today.month, 1)
        end_date = today
    elif period == "yearly":
        start_date = datetime(today.year, 1, 1)
        end_date = today
    else:
        start_date = datetime(2020, 1, 1)
        end_date = today
    
    category_revenue = defaultdict(float)
    daily_revenue = defaultdict(float)
    
    for order in orders:
        order_date = parse_order_date(order.get("orderDate") or order.get("order_date"))
        if order_date and start_date <= order_date <= end_date:
            total_price = order.get("totalPrice") or order.get("totalPriceValue") or order.get("totalAmount") or 0.0
            if isinstance(total_price, str):
                try:
                    total_price = float(total_price.replace(",", "."))
                except:
                    total_price = 0.0
            
            total_price = float(total_price) if total_price else 0.0
            
            # Kategori bazlı
            category = order.get("categoryName") or order.get("category_name") or "Diğer"
            category_revenue[category] += total_price
            
            # Günlük bazlı
            day_key = order_date.strftime("%Y-%m-%d")
            daily_revenue[day_key] += total_price
    
    return {
        "category_breakdown": [
            {"category": cat, "revenue": round(rev, 2)}
            for cat, rev in sorted(category_revenue.items(), key=lambda x: x[1], reverse=True)
        ],
        "daily_breakdown": [
            {"date": date, "revenue": round(rev, 2)}
            for date, rev in sorted(daily_revenue.items())
        ]
    }


@router.get("/expenses")
async def get_all_expenses():
    """Tüm giderleri listeler"""
    return {
        "expenses": [exp.dict() for exp in expenses.values()],
        "total": sum(exp.amount for exp in expenses.values())
    }


@router.post("/expenses")
async def create_expense(expense: Expense):
    """Yeni gider oluşturur"""
    import uuid
    
    expense.id = str(uuid.uuid4())
    expense.created_at = datetime.now().isoformat()
    expenses[expense.id] = expense
    
    return {
        "message": "Gider oluşturuldu",
        "expense": expense.dict()
    }


@router.put("/expenses/{expense_id}")
async def update_expense(expense_id: str, expense: Expense):
    """Gideri günceller"""
    if expense_id not in expenses:
        raise HTTPException(status_code=404, detail="Gider bulunamadı")
    
    expense.id = expense_id
    expenses[expense_id] = expense
    
    return {
        "message": "Gider güncellendi",
        "expense": expense.dict()
    }


@router.delete("/expenses/{expense_id}")
async def delete_expense(expense_id: str):
    """Gideri siler"""
    if expense_id not in expenses:
        raise HTTPException(status_code=404, detail="Gider bulunamadı")
    
    del expenses[expense_id]
    
    return {"message": "Gider silindi"}


@router.get("/commission-calculator")
async def calculate_commission_for_order(order_id: Optional[str] = None, amount: Optional[float] = None, category: Optional[str] = None, store: Store = Depends(get_current_store), db: Session = Depends(get_db)):
    """Komisyon hesaplayıcı"""
    if order_id:
        creds = resolve_trendyol_creds(db, store)
        orders = get_trendyol_orders_data(creds)
        order = next((o for o in orders if o.get("orderNumber") == order_id or o.get("id") == order_id), None)
        
        if not order:
            raise HTTPException(status_code=404, detail="Sipariş bulunamadı")
        
        total_price = order.get("totalPrice") or order.get("totalPriceValue") or order.get("totalAmount") or 0.0
        if isinstance(total_price, str):
            try:
                total_price = float(total_price.replace(",", "."))
            except:
                total_price = 0.0
        
        category = order.get("categoryName") or order.get("category_name") or category
        commission = calculate_commission(float(total_price), category)
        
        return {
            "order_id": order_id,
            "order_amount": round(float(total_price), 2),
            "category": category,
            "commission_rate": 0.10 if not category else (0.12 if category == "elektronik" else 0.10),
            "commission_amount": round(commission, 2),
            "net_amount": round(float(total_price) - commission, 2)
        }
    elif amount:
        commission = calculate_commission(amount, category)
        return {
            "amount": round(amount, 2),
            "category": category or "Genel",
            "commission_rate": 0.10 if not category else (0.12 if category == "elektronik" else 0.10),
            "commission_amount": round(commission, 2),
            "net_amount": round(amount - commission, 2)
        }
    else:
        raise HTTPException(status_code=400, detail="order_id veya amount parametresi gerekli")


class CargoCostSetting(BaseModel):
    cargo_cost_per_product: float


@router.get("/cargo-cost-setting")
async def get_cargo_cost_setting():
    """Kargo maliyeti ayarını döner"""
    return {"cargo_cost_per_product": CARGO_COST_PER_PRODUCT}


@router.put("/cargo-cost-setting")
async def update_cargo_cost_setting(setting: CargoCostSetting):
    """Kargo maliyeti ayarını günceller"""
    global CARGO_COST_PER_PRODUCT
    CARGO_COST_PER_PRODUCT = float(setting.cargo_cost_per_product)
    os.environ["CARGO_COST_PER_PRODUCT"] = str(CARGO_COST_PER_PRODUCT)
    return {
        "message": "Kargo maliyeti güncellendi",
        "cargo_cost_per_product": CARGO_COST_PER_PRODUCT
    }


@router.get("/order-profitability")
async def get_order_profitability(limit: Optional[int] = 50, store: Store = Depends(get_current_store), db: Session = Depends(get_db)):
    """Sipariş bazlı kâr/zarar analizi döner"""
    creds = resolve_trendyol_creds(db, store)
    orders = get_trendyol_orders_data(creds)
    results = []
    
    for order in orders[:limit]:
        order_number = order.get("orderNumber") or order.get("id") or "N/A"
        order_date_str = order.get("orderDate") or order.get("order_date")
        order_date = parse_order_date(order_date_str)
        
        total_price = order.get("totalPrice") or order.get("totalPriceValue") or order.get("totalAmount") or 0.0
        if isinstance(total_price, str):
            try:
                total_price = float(total_price.replace(",", "."))
            except:
                total_price = 0.0
        total_price = float(total_price) if total_price else 0.0
        
        vat = total_price * (VAT_RATE / (1 + VAT_RATE))
        category = order.get("categoryName") or order.get("category_name") or ""
        commission = calculate_commission(total_price, category)
        
        cargo_cost = 0.0
        for field in ["cargoCost", "cargo_cost", "shippingCost", "shipping_cost"]:
            val = order.get(field)
            if val:
                try:
                    cargo_cost = float(str(val).replace(",", "."))
                    if cargo_cost > 0:
                        break
                except:
                    pass
        if cargo_cost == 0.0:
            lines = order.get("lines", []) or order.get("orderLines", []) or []
            prod_count = sum(line.get("quantity", 1) for line in lines) if isinstance(lines, list) else 1
            if prod_count == 0:
                prod_count = 1
            cargo_cost = prod_count * CARGO_COST_PER_PRODUCT
            
        total_product_cost = 0.0
        lines = order.get("lines", []) or order.get("orderLines", []) or []
        for line in lines:
            unit_price = line.get("price") or line.get("salePrice") or line.get("unitPrice") or 0.0
            if isinstance(unit_price, str):
                try:
                    unit_price = float(unit_price.replace(",", "."))
                except:
                    unit_price = 0.0
            qty = line.get("quantity", 1)
            unit_cost = float(unit_price) * 0.40
            total_product_cost += unit_cost * qty
            
        if total_product_cost == 0.0 and total_price > 0:
            total_product_cost = total_price * 0.40
            
        net_profit = total_price - vat - commission - cargo_cost - total_product_cost
        profit_margin = (net_profit / total_price * 100) if total_price > 0 else 0.0
        
        results.append({
            "order_number": order_number,
            "order_date": order_date.strftime("%Y-%m-%d %H:%M") if order_date else "N/A",
            "customer_name": str(order.get("customerFirstName", "")) + " " + str(order.get("customerLastName", "")),
            "total_revenue": round(total_price, 2),
            "vat": round(vat, 2),
            "commission": round(commission, 2),
            "cargo_cost": round(cargo_cost, 2),
            "product_cost": round(total_product_cost, 2),
            "net_profit": round(net_profit, 2),
            "profit_margin": round(profit_margin, 2),
            "status": order.get("status", "N/A")
        })
        
    return {
        "orders": results,
        "count": len(results)
    }


@router.get("/product-profitability")
async def get_product_profitability(store: Store = Depends(get_current_store), db: Session = Depends(get_db)):
    """Ürün bazlı kâr marjı listesi"""
    creds = resolve_trendyol_creds(db, store)
    orders = get_trendyol_orders_data(creds)
    margin_warning_threshold = get_effective_thresholds(db, store.id)["margin_warning_threshold"]
    product_data = defaultdict(lambda: {"name": "", "revenue": 0.0, "quantity": 0, "cost": 0.0, "commission": 0.0, "cargo": 0.0})
    
    for order in orders:
        category = order.get("categoryName") or order.get("category_name") or ""
        total_price = order.get("totalPrice") or order.get("totalPriceValue") or 0.0
        if isinstance(total_price, str):
            try:
                total_price = float(total_price.replace(",", "."))
            except:
                total_price = 0.0
        total_price = float(total_price) if total_price else 0.0
        
        lines = order.get("lines", []) or order.get("orderLines", []) or []
        for line in lines:
            prod_id = str(line.get("productId") or line.get("product_id") or line.get("barcode") or "unknown")
            prod_name = line.get("productName") or line.get("product_name") or line.get("name") or "Ürün " + prod_id
            qty = int(line.get("quantity", 1) or 1)
            price = line.get("price") or line.get("salePrice") or line.get("unitPrice") or 0.0
            if isinstance(price, str):
                try:
                    price = float(price.replace(",", "."))
                except:
                    price = 0.0
            price = float(price) if price else 0.0
            
            revenue = price * qty
            cost = revenue * 0.40
            comm = calculate_commission(revenue, category)
            cargo = qty * CARGO_COST_PER_PRODUCT
            
            product_data[prod_id]["name"] = prod_name
            product_data[prod_id]["revenue"] += revenue
            product_data[prod_id]["quantity"] += qty
            product_data[prod_id]["cost"] += cost
            product_data[prod_id]["commission"] += comm
            product_data[prod_id]["cargo"] += cargo
            
    results = []
    for prod_id, data in product_data.items():
        rev = data["revenue"]
        cost = data["cost"]
        comm = data["commission"]
        cargo = data["cargo"]
        vat = rev * (VAT_RATE / (1 + VAT_RATE))
        net_profit = rev - vat - comm - cargo - cost
        margin = (net_profit / rev * 100) if rev > 0 else 0.0
        
        results.append({
            "product_id": prod_id,
            "product_name": data["name"],
            "total_quantity": data["quantity"],
            "total_revenue": round(rev, 2),
            "total_cost": round(cost, 2),
            "total_commission": round(comm, 2),
            "total_cargo": round(cargo, 2),
            "net_profit": round(net_profit, 2),
            "profit_margin": round(margin, 2),
            "low_margin": margin < margin_warning_threshold
        })
        
    results.sort(key=lambda x: x["net_profit"], reverse=True)
    return {
        "products": results,
        "count": len(results)
    }


# ---------------------------------------------------------------------------
# Wave2a — Kâr Marjı Listesi (store_id-scoped, lokal DB tabanlı)
# NOT: yukarıdaki eski endpoint'ler (summary/order-profitability/product-profitability)
# hâlâ canlı Trendyol API + %40 hardcoded maliyet varsayımı kullanıyor (retrofit
# edilmedi — Wave2b). Bu YENİ endpoint'ler gerçek Product.default_cost/OrderLine.unit_cost
# + store_id filtresi kullanır, bkz. utils/profitability.py.
# ---------------------------------------------------------------------------

@router.get("/profit-margin-list")
async def get_profit_margin_list(
    profit_filter: str = "all",  # "all" | "profit" | "loss"
    min_margin: Optional[float] = None,
    max_margin: Optional[float] = None,
    product_name: Optional[str] = None,
    sku: Optional[str] = None,  # barcode üzerinden arar
    category: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    sort_by: str = "net_profit",  # "net_profit" | "profit_margin_percent" | "revenue"
    store: Store = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    """Ürün-bazlı kâr marjı listesi. Varsayılan aralık: son 30 gün.
    NOT: 'HB Sku No' / 'Marka' filtreleri şu an Product şemasında YOK (bu alanlar
    eklenmedi) — sku filtresi barcode üzerinden çalışıyor, marka filtresi desteklenmiyor
    (Wave2b'de şema genişletmesi gerekebilir, flag edildi)."""
    start, end = resolve_date_range(start_date, end_date, default_days=30)
    products = compute_product_profitability(db, store.id, start, end)

    if profit_filter == "profit":
        products = [p for p in products if p["has_cost_data"] and p["net_profit"] >= 0]
    elif profit_filter == "loss":
        products = [p for p in products if p["has_cost_data"] and p["net_profit"] < 0]

    if min_margin is not None:
        products = [p for p in products if p["profit_margin_percent"] is not None and p["profit_margin_percent"] >= min_margin]
    if max_margin is not None:
        products = [p for p in products if p["profit_margin_percent"] is not None and p["profit_margin_percent"] <= max_margin]
    if product_name:
        needle = product_name.lower()
        products = [p for p in products if needle in (p["product_name"] or "").lower()]
    if sku:
        products = [p for p in products if sku.lower() in (p["barcode"] or "").lower()]
    if category:
        products = [p for p in products if (p["category"] or "").lower() == category.lower()]

    reverse = sort_by != "product_name"
    products.sort(key=lambda p: (p.get(sort_by) if p.get(sort_by) is not None else -1e18), reverse=reverse)

    return {
        "period": {"start_date": start.strftime("%Y-%m-%d"), "end_date": end.strftime("%Y-%m-%d")},
        "products": products,
        "count": len(products),
    }


class BulkPriceUpdateItem(BaseModel):
    product_id: str
    new_price: float

    @field_validator("new_price")
    @classmethod
    def _price_valid(cls, v):
        err = numeric_field_error(v, "fiyat", PRICE_MAX)
        if err:
            raise ValueError(err)
        return v


class ProfitMarginBulkUpdateRequest(BaseModel):
    """Ya doğrudan yeni fiyat listesi (items) ya da tüm seçili ürünlere uygulanacak
    tek bir hedef kâr oranı/tutarı (target_mode) gönderilir."""
    items: Optional[List[BulkPriceUpdateItem]] = None
    product_ids: Optional[List[str]] = None
    target_mode: Optional[str] = None  # "amount" (₺) | "percent" (%)
    target_value: Optional[float] = None


@router.post("/profit-margin-list/bulk-price-update")
async def bulk_update_profit_margin_prices(
    request: ProfitMarginBulkUpdateRequest,
    store: Store = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    """Kâr Marjı Listesi'nden toplu fiyat güncelleme.
    - `items` verilirse: her ürün için doğrudan `new_price` uygulanır.
    - `product_ids` + `target_mode`/`target_value` verilirse: her ürün için
      cost+komisyon+kargo baz alınarak istenen kâr tutarı/oranına ulaşacak fiyat
      hesaplanır (bkz. /api/pricing/calculate ile aynı formül)."""
    updated = []
    not_found = []

    if request.items:
        for item in request.items:
            product = db.query(Product).filter(Product.store_id == store.id, Product.product_id == item.product_id).first()
            if not product:
                not_found.append(item.product_id)
                continue
            record_change(db, store.id, product.product_id, "current_price", product.current_price, item.new_price, "bulk_price_update")
            product.current_price = item.new_price
            updated.append({"product_id": item.product_id, "new_price": item.new_price})
        db.commit()
        return {"updated": updated, "not_found": not_found, "count": len(updated)}

    if request.product_ids and request.target_mode and request.target_value is not None:
        from utils.pricing_calc import calculate_suggested_price

        for product_id in request.product_ids:
            product = db.query(Product).filter(Product.store_id == store.id, Product.product_id == product_id).first()
            if not product or not product.default_cost:
                not_found.append(product_id)
                continue
            category = product.category
            suggested = calculate_suggested_price(
                cost=product.default_cost,
                cargo_cost=CARGO_COST_PER_PRODUCT,
                category=category,
                target_mode=request.target_mode,
                target_value=request.target_value,
            )
            if suggested is None:
                not_found.append(product_id)
                continue
            # w3-manual-numeric-validation: hesaplanan fiyat da (target_value kullanıcıdan
            # gelse de, GERÇEKTEN yazılan alan bu hesaplanmış değer) aynı üst-sınır/negatif
            # kontrolünden geçer — formül kendi başına bunu garanti etmiyor.
            if numeric_field_error(suggested["suggested_price"], "fiyat", PRICE_MAX):
                not_found.append(product_id)
                continue
            record_change(db, store.id, product.product_id, "current_price", product.current_price, suggested["suggested_price"], "bulk_price_update")
            product.current_price = suggested["suggested_price"]
            updated.append({"product_id": product_id, "new_price": suggested["suggested_price"]})
        db.commit()
        return {"updated": updated, "not_found": not_found, "count": len(updated)}

    raise HTTPException(status_code=400, detail="items VEYA (product_ids + target_mode + target_value) gerekli")



# ---------------------------------------------------------------------------
# Wave2b — Raporlar×4 (Ryan'ın Raporlar sayfaları için, store_id-scoped, lokal DB)
# Hepsi Jim'in w2a-profit-formulas.md formülleriyle tutarlı (utils/profitability.py).
# Varsayılan aralık: son 30 gün.
# ---------------------------------------------------------------------------

@router.get("/reports/order-profitability")
async def report_order_profitability(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: Optional[int] = 200,
    store: Store = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    """Sipariş bazlı kârlılık raporu."""
    start, end = resolve_date_range(start_date, end_date, default_days=30)
    orders = compute_order_profitability(db, store.id, start, end, limit=limit)
    return {
        "period": {"start_date": start.strftime("%Y-%m-%d"), "end_date": end.strftime("%Y-%m-%d")},
        "orders": orders,
        "count": len(orders),
    }


@router.get("/reports/product-profitability")
async def report_product_profitability(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    sort_by: str = "net_profit",
    store: Store = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    """Ürün bazlı kârlılık raporu."""
    start, end = resolve_date_range(start_date, end_date, default_days=30)
    products = compute_product_profitability(db, store.id, start, end)
    reverse = sort_by != "product_name"
    products.sort(key=lambda p: (p.get(sort_by) if p.get(sort_by) is not None else -1e18), reverse=reverse)
    return {
        "period": {"start_date": start.strftime("%Y-%m-%d"), "end_date": end.strftime("%Y-%m-%d")},
        "products": products,
        "count": len(products),
    }


@router.get("/reports/category-profitability")
async def report_category_profitability(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    store: Store = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    """Kategori bazlı kârlılık raporu."""
    start, end = resolve_date_range(start_date, end_date, default_days=30)
    categories = compute_category_profitability(db, store.id, start, end)
    return {
        "period": {"start_date": start.strftime("%Y-%m-%d"), "end_date": end.strftime("%Y-%m-%d")},
        "categories": categories,
        "count": len(categories),
    }


@router.get("/reports/return-loss")
async def report_return_loss(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    store: Store = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    """İade zarar raporu (return_refunds tablosundan)."""
    start, end = resolve_date_range(start_date, end_date, default_days=30)
    result = compute_return_loss(db, store.id, start, end)
    return {
        "period": {"start_date": start.strftime("%Y-%m-%d"), "end_date": end.strftime("%Y-%m-%d")},
        **result,
    }


# ---------------------------------------------------------------------------
# Wave2b — Tekil ürün detayı (deep-link productId fallback — Ryan/Phyllis flag'i)
# ---------------------------------------------------------------------------
@router.get("/product/{product_id}")
async def get_single_product(
    product_id: str,
    store: Store = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    """Tek ürünün lokal DB kaydı (Ürün Fiyatlandırma deep-link'i ürün adı/maliyet/desi
    ön-doldurması için). NOT: products.py'deki GET /{product_id} CANLI Trendyol API'ye
    gider ve store-scoped değildir; bu ise lokal DB + store_id — deep-link fallback'i
    için bilinçli olarak burada, financial altında."""
    product = db.query(Product).filter(Product.store_id == store.id, Product.product_id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Ürün bulunamadı")
    return {
        "product_id": product.product_id,
        "product_name": product.product_name,
        "category": product.category,
        "barcode": product.barcode,
        "current_price": product.current_price,
        "default_cost": product.default_cost,
        "desi": product.desi,
    }


# ---------------------------------------------------------------------------
# Wave2b — Hakediş & Desi Kontrolü (mutabakat)
# Jim'in w2b-reconciliation-campaign-logic.md BÖLÜM 1 mantığı.
# TAHMİNİ taraf (desi-bazlı kargo + tarife komisyonu) LOKAL veriden hesaplanır.
# GERÇEK taraf (Trendyol Settlements/OtherFinancials/Cargo-Invoice) şu an YOK —
# per-store Trendyol API entegrasyonu ayrı/büyük bir iş (god'un onayladığı kapsam
# dışı madde). Bu yüzden endpoint tahmini tarafı gerçek döner, gerçek tarafı
# 'settlement_pending' bayrağıyla null bırakır; frontend "gerçekleşen bekleniyor"
# gösterebilir. Şema hazır olduğu için settlement baglaninca sadece o taraf dolar.
# ---------------------------------------------------------------------------
# Basit desi->kargo tarife tablosu (yapılandırılabilir; gerçek Trendyol tarifesiyle
# kalibre edilmeli — şimdilik makul kademeler). desi=0 ise CARGO_COST_PER_PRODUCT'a düşer.
_DESI_CARGO_TIERS = [
    (1, 40.0), (2, 55.0), (3, 70.0), (5, 95.0), (10, 140.0), (15, 190.0), (30, 320.0),
]


def _estimate_cargo_from_desi(desi: float) -> float:
    if not desi or desi <= 0:
        return CARGO_COST_PER_PRODUCT
    for max_desi, cost in _DESI_CARGO_TIERS:
        if desi <= max_desi:
            return cost
    return _DESI_CARGO_TIERS[-1][1] + (desi - 30) * 10.0


# Sapma toleransı — Jim: melontik değeri DOGRULANAMADI, yapılandırılabilir bırak (~1TL/%1).
RECON_TOLERANCE_ABS = float(os.getenv("RECON_TOLERANCE_ABS", "1.0"))
RECON_TOLERANCE_PCT = float(os.getenv("RECON_TOLERANCE_PCT", "1.0"))


@router.get("/reconciliation")
async def get_reconciliation(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    only_flagged: bool = False,
    store: Store = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    """Hakediş & Desi Kontrolü: sipariş-satırı bazında BEKLENEN (tahmini) komisyon+kargo
    ile GERÇEK (settlement) tutarları karşılaştırır (Wave3 FAZ3). Mağaza Trendyol'a
    bağlıysa gerçek komisyon Settlements'tan çekilip actual_commission doldurulur ve
    tolerans aşan farklar 'hatalı kesinti adayı' olarak işaretlenir; bağlı değilse
    tahmini taraf yine döner, actual_* null + status='settlement_pending'."""
    from utils.store_trendyol import try_resolve_trendyol_creds, fetch_settlements, fetch_otherfinancials, cargo_transaction_types

    start, end = resolve_date_range(start_date, end_date, default_days=30)

    products = {p.product_id: p for p in db.query(Product).filter(Product.store_id == store.id).all()}
    rows = (
        db.query(OrderLine, Order.order_number)
        .join(Order, OrderLine.order_id == Order.order_id)
        .filter(OrderLine.store_id == store.id, Order.store_id == store.id)
        .filter(Order.order_date >= start, Order.order_date <= end)
        .all()
    )

    # GERÇEK taraf: mağaza bağlıysa Settlements'tan komisyon çek, (orderNumber, barcode) ile eşle
    creds = try_resolve_trendyol_creds(db, store)
    settlement_available = False
    actual_commission_map: Dict[tuple, float] = defaultdict(float)
    # actual_cargo: OtherFinancials kargo/kesinti kalemlerinden — DÜŞÜK GÜVEN, MUHAFAZAKÂR.
    # SADECE hem orderNumber HEM barcode taşıyan kalemleri bir satıra atfediyoruz;
    # yalnız orderNumber taşıyan (satıra atfedilemeyen) kalemler KATILMIYOR (yanlış flag'den iyidir).
    actual_cargo_map: Dict[tuple, float] = defaultdict(float)
    cargo_available = False
    if creds is not None:
        try:
            txns = fetch_settlements(creds, start, end, transaction_type="Commission")
            for t in txns:
                on = str(t.get("orderNumber") or "")
                bc = str(t.get("barcode") or "")
                amt = t.get("commissionAmount")
                if amt is None:
                    continue
                try:
                    amt = abs(float(amt))  # komisyon kesintisi mutlak tutar
                except Exception:
                    continue
                # CommissionPositive (iade/iptal komisyon iadesi) tutarı düşer
                if str(t.get("transactionType") or "").lower().startswith("commissionpositive"):
                    amt = -amt
                actual_commission_map[(on, bc)] += amt
            settlement_available = True
        except Exception:
            settlement_available = False

        # Kargo (actual_cargo) — OtherFinancials kesinti faturaları, muhafazakâr eşleme
        try:
            cargo_txns = fetch_otherfinancials(creds, start, end)
            for t in cargo_txns:
                on = str(t.get("orderNumber") or "")
                bc = str(t.get("barcode") or "")
                # MUHAFAZAKÂR: satıra atfetmek için HEM orderNumber HEM barcode gerekli
                if not on or not bc:
                    continue
                # Kargo kesintisi tutarı: OtherFinancials'ta 'debt' (kesinti) alanında;
                # yoksa cargoAmount/amount alternatiflerini dene
                raw = t.get("debt")
                if raw is None:
                    raw = t.get("cargoAmount") or t.get("amount")
                if raw is None:
                    continue
                try:
                    cargo_amt = abs(float(raw))
                except Exception:
                    continue
                actual_cargo_map[(on, bc)] += cargo_amt
            cargo_available = True
        except Exception:
            cargo_available = False

    items = []
    for line, order_number in rows:
        product = products.get(line.product_id)
        revenue = float(line.total_price or 0.0)
        expected_commission = calculate_commission(revenue, line.category)
        desi = (product.desi if product else 0.0) or 0.0
        expected_cargo = _estimate_cargo_from_desi(desi) * (line.quantity or 1)

        actual_commission = None
        commission_diff = None
        actual_cargo = None
        cargo_diff = None
        flagged = False
        item_status = "settlement_pending"
        key = (str(order_number or ""), str(line.product_id or ""))
        if settlement_available:
            if key in actual_commission_map:
                actual_commission = round(actual_commission_map[key], 2)
                commission_diff = round(actual_commission - expected_commission, 2)
                pct = (abs(commission_diff) / expected_commission * 100) if expected_commission > 0 else 0.0
                if abs(commission_diff) >= RECON_TOLERANCE_ABS or pct >= RECON_TOLERANCE_PCT:
                    flagged = True
                item_status = "reconciled"
            else:
                # Settlement çekildi ama bu satır için kayıt yok (henüz hakediş oluşmamış)
                item_status = "awaiting_settlement"

            # actual_cargo — SADECE muhafazakâr (orderNumber+barcode) eşleşen kalemler
            if cargo_available and key in actual_cargo_map:
                actual_cargo = round(actual_cargo_map[key], 2)
                cargo_diff = round(actual_cargo - expected_cargo, 2)
                cargo_pct = (abs(cargo_diff) / expected_cargo * 100) if expected_cargo > 0 else 0.0
                if abs(cargo_diff) >= RECON_TOLERANCE_ABS or cargo_pct >= RECON_TOLERANCE_PCT:
                    flagged = True
                if item_status != "reconciled":
                    item_status = "reconciled"

        items.append({
            "order_number": order_number,
            "order_id": line.order_id,
            "barcode": line.product_id,
            "product_name": line.product_name,
            "desi": desi,
            "expected_commission": round(expected_commission, 2),
            "expected_cargo": round(expected_cargo, 2),
            "actual_commission": actual_commission,
            # actual_cargo: OtherFinancials kesinti kalemlerinden, SADECE orderNumber+barcode
            # ile muhafazakâr eşleşenler doldurulur; eşleşmeyen/belirsiz kalemler null bırakılır
            # (yanlış flag'den iyidir — Jim düşük-güven notu).
            "actual_cargo": actual_cargo,
            "commission_diff": commission_diff,
            "cargo_diff": cargo_diff,
            "flagged": flagged,
            "status": item_status,
        })

    if only_flagged:
        items = [i for i in items if i["flagged"]]

    return {
        "period": {"start_date": start.strftime("%Y-%m-%d"), "end_date": end.strftime("%Y-%m-%d")},
        "settlement_available": settlement_available,
        "cargo_available": cargo_available,
        "cargo_transaction_types": cargo_transaction_types(),
        "items": items,
        "count": len(items),
        "flagged_count": sum(1 for i in items if i["flagged"]),
        "tolerance": {"abs_try": RECON_TOLERANCE_ABS, "pct": RECON_TOLERANCE_PCT},
        "_note": (
            "GERCEK komisyon Trendyol Settlements'tan cekiliyor (per-store creds, 15-gunluk pencere paginate). "
            "actual_cargo Trendyol OtherFinancials kesinti kalemlerinden cekiliyor ama MUHAFAZAKAR eslenir: "
            "SADECE hem orderNumber HEM barcode tasiyan kalemler bir satira atfedilir; belirsiz kalemler null kalir "
            "(yanlis flag'den iyidir - Jim dusuk-guven). Taranan kargo transactionType adaylari 'cargo_transaction_types' "
            "alaninda; env TRENDYOL_CARGO_TXN_TYPES ile override edilebilir (gercek Trendyol hesabiyla kalibre edilmeli). "
            "settlement_available/cargo_available=false -> magaza Trendyol'a bagli degil VEYA erisilemedi -> actual_* null. "
            "Itiraz OTOMATIK gonderilemez (Trendyol API'de endpoint yok) - cikti rapor/export olarak kalir (Jim)."
        ),
    }
