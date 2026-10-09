"""
Fiyat Geçmişi ve Trend Analizi Router
Ürün fiyat değişikliklerini takip eder ve trend analizi yapar
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, desc
import os

# Database modülünü optional olarak yükle (ghost mode)
try:
    from database.db import get_db
    from database.models import PriceHistory, PriceTrend, Product, Store
    from security import get_current_store
    _db_available = True
except Exception:
    _db_available = False
    def get_db():
        raise HTTPException(status_code=503, detail="Database not available (ghost mode)")

    def get_current_store():
        raise HTTPException(status_code=503, detail="Database not available (ghost mode)")

router = APIRouter()


def _check_db():
    """Database kontrolü - ghost mode"""
    if not _db_available:
        raise HTTPException(status_code=503, detail="Database not available (ghost mode)")


class PriceHistoryResponse(BaseModel):
    """Fiyat geçmişi yanıt modeli"""
    id: int
    product_id: str
    product_name: Optional[str]
    previous_price: float
    new_price: float
    price_change: float
    price_change_percent: float
    change_reason: Optional[str]
    competitor_price: Optional[float]
    created_at: str


class PriceTrendResponse(BaseModel):
    """Fiyat trend yanıt modeli"""
    date: str
    average_price: float
    min_price: Optional[float]
    max_price: Optional[float]
    price_volatility: float
    sales_count: int
    revenue: float
    competitor_avg_price: Optional[float]
    market_position: Optional[str]


class PriceAnalysisResponse(BaseModel):
    """Fiyat analizi yanıt modeli"""
    product_id: str
    product_name: str
    current_price: float
    price_trend: str  # 'increasing', 'decreasing', 'stable'
    average_price_30days: float
    average_price_90days: float
    price_change_30days: float
    price_change_90days: float
    best_price_period: Dict[str, Any]
    worst_price_period: Dict[str, Any]
    recommendations: List[str]


@router.get("/{product_id}", response_model=List[PriceHistoryResponse])
async def get_price_history(
    product_id: str,
    days: int = 90,
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Session = Depends(get_db) if _db_available else None
):
    """
    Belirli bir ürünün fiyat geçmişini getirir

    Args:
        product_id: Ürün ID'si
        days: Son kaç günün verileri (varsayılan: 90)
    """
    if not _db_available:
        return []

    _check_db()

    date_filter = datetime.now() - timedelta(days=days)

    history = db.query(PriceHistory).filter(
        and_(
            PriceHistory.store_id == store.id,
            PriceHistory.product_id == product_id,
            PriceHistory.created_at >= date_filter
        )
    ).order_by(PriceHistory.created_at.desc()).limit(200).all()
    
    return [
        PriceHistoryResponse(
            id=h.id,
            product_id=h.product_id,
            product_name=h.product_name,
            previous_price=h.previous_price,
            new_price=h.new_price,
            price_change=h.price_change,
            price_change_percent=h.price_change_percent,
            change_reason=h.change_reason,
            competitor_price=h.competitor_price,
            created_at=h.created_at.isoformat() if h.created_at else ""
        )
        for h in history
    ]


@router.get("/{product_id}/trend", response_model=List[PriceTrendResponse])
async def get_price_trend(
    product_id: str,
    period: str = 'daily',  # 'daily', 'weekly', 'monthly'
    days: int = 30,
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Session = Depends(get_db) if _db_available else None
):
    """
    Belirli bir ürünün fiyat trend verilerini getirir
    
    Args:
        product_id: Ürün ID'si
        period: Zaman dilimi ('daily', 'weekly', 'monthly')
        days: Son kaç günün verileri
    """
    if not _db_available:
        return []
    
    _check_db()
    
    date_filter = datetime.now() - timedelta(days=days)
    
    trends = db.query(PriceTrend).filter(
        and_(
            PriceTrend.store_id == store.id,
            PriceTrend.product_id == product_id,
            PriceTrend.period_type == period,
            PriceTrend.date >= date_filter
        )
    ).order_by(PriceTrend.date.asc()).all()
    
    return [
        PriceTrendResponse(
            date=t.date.isoformat() if t.date else "",
            average_price=t.average_price,
            min_price=t.min_price,
            max_price=t.max_price,
            price_volatility=t.price_volatility,
            sales_count=t.sales_count,
            revenue=t.revenue,
            competitor_avg_price=t.competitor_avg_price,
            market_position=t.market_position
        )
        for t in trends
    ]


@router.get("/{product_id}/analysis", response_model=PriceAnalysisResponse)
async def get_price_analysis(
    product_id: str,
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Session = Depends(get_db) if _db_available else None
):
    """
    Belirli bir ürünün detaylı fiyat analizini getirir
    Trend, değişim oranları ve öneriler içerir
    """
    if not _db_available:
        # Ghost mode - basit analiz
        return PriceAnalysisResponse(
            product_id=product_id,
            product_name="Unknown",
            current_price=0.0,
            price_trend="stable",
            average_price_30days=0.0,
            average_price_90days=0.0,
            price_change_30days=0.0,
            price_change_90days=0.0,
            best_price_period={},
            worst_price_period={},
            recommendations=["Database not available"]
        )
    
    _check_db()
    
    # Son 30 ve 90 günlük veriler
    date_30 = datetime.now() - timedelta(days=30)
    date_90 = datetime.now() - timedelta(days=90)
    
    # Fiyat geçmişi
    history_30 = db.query(PriceHistory).filter(
        and_(
            PriceHistory.store_id == store.id,
            PriceHistory.product_id == product_id,
            PriceHistory.created_at >= date_30
        )
    ).order_by(PriceHistory.created_at.asc()).all()

    history_90 = db.query(PriceHistory).filter(
        and_(
            PriceHistory.store_id == store.id,
            PriceHistory.product_id == product_id,
            PriceHistory.created_at >= date_90
        )
    ).order_by(PriceHistory.created_at.asc()).all()

    # Güncel fiyat
    current_price_record = db.query(PriceHistory).filter(
        PriceHistory.store_id == store.id,
        PriceHistory.product_id == product_id
    ).order_by(PriceHistory.created_at.desc()).first()
    
    current_price = current_price_record.new_price if current_price_record else 0.0
    product_name = current_price_record.product_name if current_price_record else "Unknown"
    
    # Ortalama fiyatlar
    if history_30:
        avg_30 = sum(h.new_price for h in history_30) / len(history_30)
        first_price_30 = history_30[0].previous_price if history_30[0].previous_price > 0 else history_30[0].new_price
        change_30 = ((current_price - first_price_30) / first_price_30 * 100) if first_price_30 > 0 else 0.0
    else:
        avg_30 = current_price
        change_30 = 0.0
    
    if history_90:
        avg_90 = sum(h.new_price for h in history_90) / len(history_90)
        first_price_90 = history_90[0].previous_price if history_90[0].previous_price > 0 else history_90[0].new_price
        change_90 = ((current_price - first_price_90) / first_price_90 * 100) if first_price_90 > 0 else 0.0
    else:
        avg_90 = current_price
        change_90 = 0.0
    
    # Trend belirleme
    if len(history_30) >= 2:
        recent_changes = [h.price_change_percent for h in history_30[-5:]]
        avg_change = sum(recent_changes) / len(recent_changes) if recent_changes else 0.0
        
        if avg_change > 2:
            trend = "increasing"
        elif avg_change < -2:
            trend = "decreasing"
        else:
            trend = "stable"
    else:
        trend = "stable"
    
    # En iyi ve en kötü dönemler
    best_period = {}
    worst_period = {}
    
    if history_90:
        # Satış bazlı en iyi/kötü dönemler
        periods_with_sales = [
            {
                "date": h.created_at.isoformat() if h.created_at else "",
                "price": h.new_price,
                "sales_after": h.sales_after
            }
            for h in history_90 if h.sales_after > 0
        ]
        
        if periods_with_sales:
            best_period = max(periods_with_sales, key=lambda x: x["sales_after"])
            worst_period = min(periods_with_sales, key=lambda x: x["sales_after"])
    
    # Öneriler
    recommendations = []
    
    if trend == "decreasing" and change_30 < -5:
        recommendations.append("Fiyat son 30 günde %5'ten fazla düştü. Rekabet analizi yapın.")
    
    if current_price > avg_30 * 1.1:
        recommendations.append("Mevcut fiyat ortalamanın üzerinde. Satışları etkileyebilir.")
    
    if current_price < avg_30 * 0.9:
        recommendations.append("Mevcut fiyat ortalamanın altında. Kâr marjını kontrol edin.")
    
    if not recommendations:
        recommendations.append("Fiyat trendi normal görünüyor.")
    
    return PriceAnalysisResponse(
        product_id=product_id,
        product_name=product_name,
        current_price=current_price,
        price_trend=trend,
        average_price_30days=round(avg_30, 2),
        average_price_90days=round(avg_90, 2),
        price_change_30days=round(change_30, 2),
        price_change_90days=round(change_90, 2),
        best_price_period=best_period,
        worst_price_period=worst_period,
        recommendations=recommendations
    )


@router.post("/{product_id}/record")
async def record_price_change(
    product_id: str,
    new_price: float,
    change_reason: Optional[str] = "manual",
    competitor_price: Optional[float] = None,
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Session = Depends(get_db) if _db_available else None
):
    """
    Yeni bir fiyat değişikliğini kaydeder
    
    Args:
        product_id: Ürün ID'si
        new_price: Yeni fiyat
        change_reason: Değişiklik nedeni ('manual', 'automation', 'competitor', 'campaign')
        competitor_price: Rakip fiyatı (varsa)
    """
    if not _db_available:
        raise HTTPException(status_code=503, detail="Database not available (ghost mode)")
    
    _check_db()
    
    # Önceki fiyatı bul
    last_record = db.query(PriceHistory).filter(
        PriceHistory.store_id == store.id,
        PriceHistory.product_id == product_id
    ).order_by(PriceHistory.created_at.desc()).first()

    previous_price = last_record.new_price if last_record else new_price

    # Ürün adını bul
    product = db.query(Product).filter(Product.store_id == store.id, Product.product_id == product_id).first()
    product_name = product.product_name if product else "Unknown"
    
    # Değişim hesapla
    price_change = new_price - previous_price
    price_change_percent = ((new_price - previous_price) / previous_price * 100) if previous_price > 0 else 0.0
    
    # Yeni kayıt oluştur
    new_record = PriceHistory(
        store_id=store.id,
        product_id=product_id,
        product_name=product_name,
        previous_price=previous_price,
        new_price=new_price,
        price_change=price_change,
        price_change_percent=price_change_percent,
        change_reason=change_reason,
        competitor_price=competitor_price
    )
    
    db.add(new_record)
    db.commit()
    db.refresh(new_record)
    
    return {
        "message": "Fiyat değişikliği kaydedildi",
        "price_history_id": new_record.id,
        "price_change": price_change,
        "price_change_percent": round(price_change_percent, 2)
    }


def get_trendyol_orders_data() -> List[Dict]:
    """Trendyol API'den sipariş verilerini çeker"""
    import requests
    import base64
    
    api_key = os.getenv("TRENDYOL_API_KEY")
    api_secret = os.getenv("TRENDYOL_API_SECRET")
    supplier_id = os.getenv("TRENDYOL_SUPPLIER_ID")
    
    if not all([api_key, api_secret, supplier_id]):
        return []
    
    try:
        url = f"https://api.trendyol.com/sapigw/suppliers/{supplier_id}/orders"
        auth_string = f"{api_key}:{api_secret}"
        auth_bytes = auth_string.encode('ascii')
        auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
        
        headers = {
            "Authorization": f"Basic {auth_b64}",
            "Content-Type": "application/json",
            "User-Agent": "Trendyol-AI-Assistant/1.0"
        }
        
        all_orders = []
        page = 0
        size = 200
        
        while True:
            response = requests.get(
                url,
                headers=headers,
                params={"page": page, "size": size},
                timeout=30
            )
            
            if response.status_code != 200:
                break
            
            try:
                data = response.json()
                orders = data.get("content", [])
                
                if not orders:
                    break
                
                all_orders.extend(orders)
                
                if len(orders) < size:
                    break
                
                page += 1
                
                if page > 100:
                    break
            except Exception:
                break
        
        return all_orders
    except Exception:
        return []


@router.get("/products/all")
async def get_all_products_price_history(
    days: int = 30,
    limit: int = 200,
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Session = Depends(get_db) if _db_available else None
):
    """
    Tüm ürünlerin son fiyat değişikliklerini getirir
    Önce siparişlerden ürünleri çıkarır, sonra fiyat geçmişi ile birleştirir
    """
    from collections import defaultdict
    
    # Siparişlerden ürünleri çıkar
    orders = get_trendyol_orders_data()
    products_from_orders = {}
    
    for order in orders:
        lines = order.get("lines", []) or order.get("orderLines", []) or order.get("items", []) or []
        
        if isinstance(lines, dict):
            lines = [lines]
        
        for line in lines:
            try:
                product_id = (
                    line.get("productId") or 
                    line.get("product_id") or 
                    line.get("barcode") or 
                    line.get("sku") or
                    line.get("merchantSku") or
                    str(line.get("id", "")) if line.get("id") else ""
                )
                
                if not product_id:
                    continue
                
                product_id_str = str(product_id)
                
                if product_id_str not in products_from_orders:
                    products_from_orders[product_id_str] = {
                        "product_id": product_id_str,
                        "product_name": (
                            line.get("productName") or 
                            line.get("product_name") or 
                            line.get("name") or 
                            line.get("productTitle") or
                            "Bilinmeyen Ürün"
                        ),
                        "category": line.get("categoryName") or line.get("category_name") or "",
                        "barcode": line.get("barcode") or line.get("sku") or "",
                        "current_price": 0.0
                    }
                
                # Fiyat bilgisini güncelle (en son fiyatı al)
                price = (
                    line.get("price", 0) or 
                    line.get("salePrice", 0) or 
                    line.get("unitPrice", 0) or
                    line.get("amount", 0) or
                    0
                )
                
                if isinstance(price, str):
                    try:
                        price = float(price.replace(',', '.'))
                    except:
                        price = 0.0
                
                if price > 0:
                    products_from_orders[product_id_str]["current_price"] = float(price)
            except Exception:
                continue
    
    # Database'den fiyat geçmişi varsa birleştir
    result_products = []
    
    if _db_available:
        try:
            _check_db()
            date_filter = datetime.now() - timedelta(days=days)
            
            # Fiyat geçmişi olan ürünler için son değişikliği al
            subquery = db.query(
                PriceHistory.product_id,
                func.max(PriceHistory.created_at).label('max_date')
            ).filter(
                PriceHistory.store_id == store.id,
                PriceHistory.created_at >= date_filter
            ).group_by(PriceHistory.product_id).subquery()

            recent_changes = db.query(PriceHistory).join(
                subquery,
                and_(
                    PriceHistory.product_id == subquery.c.product_id,
                    PriceHistory.created_at == subquery.c.max_date
                )
            ).filter(PriceHistory.store_id == store.id).all()
            
            # Fiyat geçmişi olan ürünleri işaretle
            history_dict = {h.product_id: h for h in recent_changes}
            
            # Tüm ürünleri birleştir
            for product_id, product_data in products_from_orders.items():
                if product_id in history_dict:
                    # Fiyat geçmişi var
                    h = history_dict[product_id]
                    result_products.append({
                        "product_id": product_id,
                        "product_name": h.product_name or product_data["product_name"],
                        "current_price": h.new_price,
                        "previous_price": h.previous_price,
                        "price_change_percent": h.price_change_percent,
                        "last_change_date": h.created_at.isoformat() if h.created_at else "",
                        "has_history": True
                    })
                else:
                    # Fiyat geçmişi yok, siparişlerden gelen fiyatı kullan
                    result_products.append({
                        "product_id": product_id,
                        "product_name": product_data["product_name"],
                        "current_price": product_data["current_price"],
                        "previous_price": product_data["current_price"],
                        "price_change_percent": 0.0,
                        "last_change_date": "",
                        "has_history": False
                    })
        except Exception as e:
            # Database hatası varsa sadece siparişlerden gelen ürünleri kullan
            print(f"[PriceHistory] Database error: {e}")
            for product_id, product_data in products_from_orders.items():
                result_products.append({
                    "product_id": product_id,
                    "product_name": product_data["product_name"],
                    "current_price": product_data["current_price"],
                    "previous_price": product_data["current_price"],
                    "price_change_percent": 0.0,
                    "last_change_date": "",
                    "has_history": False
                })
    else:
        # Database yoksa sadece siparişlerden gelen ürünleri kullan
        for product_id, product_data in products_from_orders.items():
            result_products.append({
                "product_id": product_id,
                "product_name": product_data["product_name"],
                "current_price": product_data["current_price"],
                "previous_price": product_data["current_price"],
                "price_change_percent": 0.0,
                "last_change_date": "",
                "has_history": False
            })
    
    # Ürün adına göre sırala
    result_products.sort(key=lambda x: (x["product_name"] or x["product_id"]).lower())
    
    return {
        "products": result_products[:limit],
        "total": len(result_products),
        "with_history": len([p for p in result_products if p.get("has_history", False)]),
        "without_history": len([p for p in result_products if not p.get("has_history", False)])
    }


@router.get("/trends/summary")
async def get_price_trends_summary(
    days: int = 30,
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Session = Depends(get_db) if _db_available else None
):
    """
    Genel fiyat trend özeti
    """
    if not _db_available:
        return {
            "total_price_changes": 0,
            "average_change_percent": 0.0,
            "increasing_prices": 0,
            "decreasing_prices": 0,
            "stable_prices": 0
        }

    _check_db()

    date_filter = datetime.now() - timedelta(days=days)

    changes = db.query(PriceHistory).filter(
        PriceHistory.store_id == store.id,
        PriceHistory.created_at >= date_filter
    ).all()
    
    if not changes:
        return {
            "total_price_changes": 0,
            "average_change_percent": 0.0,
            "increasing_prices": 0,
            "decreasing_prices": 0,
            "stable_prices": 0
        }
    
    increasing = len([c for c in changes if c.price_change_percent > 2])
    decreasing = len([c for c in changes if c.price_change_percent < -2])
    stable = len([c for c in changes if -2 <= c.price_change_percent <= 2])
    
    avg_change = sum(c.price_change_percent for c in changes) / len(changes) if changes else 0.0
    
    return {
        "total_price_changes": len(changes),
        "average_change_percent": round(avg_change, 2),
        "increasing_prices": increasing,
        "decreasing_prices": decreasing,
        "stable_prices": stable
    }

