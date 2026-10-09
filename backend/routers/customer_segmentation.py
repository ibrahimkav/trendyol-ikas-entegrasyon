"""
Müşteri Segmentasyonu ve CRM Router
Müşteri segmentasyonu, analiz ve CRM özellikleri
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

router = APIRouter(tags=["Customer Segmentation"])

# Database modülünü optional olarak yükle
_db_available = False
try:
    from database.db import get_db
    from database.models import Order, OrderLine, Product, Store
    from security import get_current_store
    from utils.store_trendyol import try_resolve_trendyol_creds
    _db_available = True
except Exception:
    def get_current_store():
        raise HTTPException(status_code=503, detail="Database not available (ghost mode)")


def _check_db():
    """Database kontrolü"""
    if not _db_available:
        raise HTTPException(status_code=503, detail="Database not available (ghost mode)")


class CustomerSegment(BaseModel):
    """Müşteri segmenti"""
    segment_id: str
    segment_name: str
    description: str
    criteria: Dict[str, Any]
    customer_count: int
    total_revenue: float
    avg_order_value: float
    created_at: str


class CustomerProfile(BaseModel):
    """Müşteri profili"""
    customer_id: str
    customer_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    total_orders: int
    total_revenue: float
    avg_order_value: float
    first_order_date: Optional[str] = None
    last_order_date: Optional[str] = None
    days_since_last_order: Optional[int] = None
    favorite_category: Optional[str] = None
    segment: str
    customer_lifetime_value: float
    churn_risk: str  # "low", "medium", "high"
    created_at: str


class SegmentAnalysis(BaseModel):
    """Segment analizi"""
    segment_id: str
    segment_name: str
    total_customers: int
    total_revenue: float
    avg_revenue_per_customer: float
    avg_orders_per_customer: float
    top_products: List[Dict[str, Any]]
    top_categories: List[Dict[str, Any]]
    growth_trend: str  # "increasing", "stable", "decreasing"
    recommendations: List[str]


class CustomerSegmentationRequest(BaseModel):
    """Müşteri segmentasyonu isteği"""
    min_orders: Optional[int] = None
    min_revenue: Optional[float] = None
    days_since_last_order: Optional[int] = None
    category: Optional[str] = None


def calculate_customer_segments(orders_data: List[Dict]) -> Dict[str, List[Dict]]:
    """
    Sipariş verilerinden müşteri segmentlerini hesaplar
    """
    if not orders_data:
        return {
            "vip": [],
            "loyal": [],
            "regular": [],
            "new": [],
            "at_risk": []
        }
    
    customers = {}
    
    # Müşteri verilerini topla
    for order in orders_data:
        if not isinstance(order, dict):
            continue
            
        customer_id = (
            order.get("customerId") or
            order.get("customer_id") or
            order.get("buyerId") or
            order.get("buyer_id") or
            order.get("customerEmail") or
            order.get("customer_email") or
            order.get("orderNumber") or
            order.get("order_number") or
            None
        )
        
        if not customer_id or customer_id == "unknown":
            continue
        
        if customer_id not in customers:
            customers[customer_id] = {
                "customer_id": customer_id,
                "customer_name": (
                    order.get("customerFirstName") or
                    order.get("customer_first_name") or
                    order.get("customerName") or
                    order.get("customer_name") or
                    "Bilinmeyen Müşteri"
                ),
                "email": (
                    order.get("customerEmail") or
                    order.get("customer_email") or
                    None
                ),
                "phone": (
                    order.get("customerPhone") or
                    order.get("customer_phone") or
                    None
                ),
                "orders": [],
                "total_revenue": 0.0,
                "order_count": 0,
                "first_order_date": None,
                "last_order_date": None,
                "categories": {}
            }
        
        # Sipariş bilgilerini ekle
        # Trendyol orderDate epoch-ms int olarak gelir (string DEĞİL) — downstream kod
        # (CustomerProfile Pydantic modeli, .replace("Z",...) çağrıları) ISO string bekliyor.
        # Bu satırlar önceden hiç gerçek veriyle çalışmadığı için (orders hep boştu) bu
        # tip uyuşmazlığı ortaya çıkmamıştı — per-store creds fix'iyle şimdi gerçek veri
        # akınca fark edildi, burada normalize ediliyor.
        _raw_order_date = (
            order.get("orderDate") or
            order.get("order_date") or
            order.get("createdAt") or
            order.get("created_at")
        )
        if isinstance(_raw_order_date, (int, float)):
            order_date = datetime.fromtimestamp(_raw_order_date / 1000).isoformat()
        elif isinstance(_raw_order_date, str) and _raw_order_date:
            order_date = _raw_order_date
        else:
            order_date = datetime.now().isoformat()
        
        order_amount = (
            order.get("totalAmount") or
            order.get("total_amount") or
            order.get("amount") or
            order.get("totalPrice") or
            order.get("total_price") or
            0.0
        )
        
        if isinstance(order_amount, str):
            try:
                order_amount = float(order_amount.replace(",", "."))
            except:
                order_amount = 0.0
        
        customers[customer_id]["orders"].append({
            "order_id": order.get("orderNumber") or order.get("order_number") or "",
            "date": order_date,
            "amount": order_amount
        })
        
        customers[customer_id]["total_revenue"] += order_amount
        customers[customer_id]["order_count"] += 1
        
        # Tarih güncellemeleri
        if not customers[customer_id]["first_order_date"]:
            customers[customer_id]["first_order_date"] = order_date
        else:
            if order_date < customers[customer_id]["first_order_date"]:
                customers[customer_id]["first_order_date"] = order_date
        
        if not customers[customer_id]["last_order_date"]:
            customers[customer_id]["last_order_date"] = order_date
        else:
            if order_date > customers[customer_id]["last_order_date"]:
                customers[customer_id]["last_order_date"] = order_date
        
        # Kategori takibi
        lines = (
            order.get("lines") or
            order.get("orderLines") or
            order.get("items") or
            []
        )
        
        if isinstance(lines, dict):
            lines = [lines]
        
        for line in lines:
            category = (
                line.get("categoryName") or
                line.get("category_name") or
                line.get("category") or
                "Diğer"
            )
            customers[customer_id]["categories"][category] = (
                customers[customer_id]["categories"].get(category, 0) + 1
            )
    
    # Segmentlere ayır
    segments = {
        "vip": [],
        "loyal": [],
        "regular": [],
        "new": [],
        "at_risk": []
    }
    
    now = datetime.now()
    
    for customer_id, customer_data in customers.items():
        total_revenue = customer_data["total_revenue"]
        order_count = customer_data["order_count"]
        avg_order_value = total_revenue / order_count if order_count > 0 else 0
        
        # Son sipariş tarihini hesapla
        days_since_last_order = None
        if customer_data["last_order_date"]:
            try:
                last_order = datetime.fromisoformat(customer_data["last_order_date"].replace("Z", "+00:00"))
                days_since_last_order = (now - last_order.replace(tzinfo=None)).days
            except:
                pass
        
        # En sevilen kategori
        favorite_category = None
        if customer_data["categories"]:
            favorite_category = max(
                customer_data["categories"].items(),
                key=lambda x: x[1]
            )[0]
        
        customer_profile = {
            **customer_data,
            "avg_order_value": avg_order_value,
            "days_since_last_order": days_since_last_order,
            "favorite_category": favorite_category,
            "customer_lifetime_value": total_revenue * 1.2  # Basit CLV hesaplama
        }
        
        # Segment belirleme
        if total_revenue >= 5000 and order_count >= 10:
            customer_profile["segment"] = "vip"
            customer_profile["churn_risk"] = "low"
            segments["vip"].append(customer_profile)
        elif total_revenue >= 2000 and order_count >= 5:
            customer_profile["segment"] = "loyal"
            customer_profile["churn_risk"] = "low" if days_since_last_order and days_since_last_order < 60 else "medium"
            segments["loyal"].append(customer_profile)
        elif order_count >= 3:
            customer_profile["segment"] = "regular"
            customer_profile["churn_risk"] = "medium" if days_since_last_order and days_since_last_order < 90 else "high"
            segments["regular"].append(customer_profile)
        elif days_since_last_order and days_since_last_order > 180:
            customer_profile["segment"] = "at_risk"
            customer_profile["churn_risk"] = "high"
            segments["at_risk"].append(customer_profile)
        else:
            customer_profile["segment"] = "new"
            customer_profile["churn_risk"] = "low"
            segments["new"].append(customer_profile)
    
    return segments


@router.get("/segments", response_model=List[CustomerSegment])
async def get_customer_segments(
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Optional[Session] = Depends(get_db) if _db_available else None
):
    """
    Müşteri segmentlerini getirir
    """
    try:
        from routers.products import get_trendyol_orders_data
        creds = try_resolve_trendyol_creds(db, store) if (_db_available and store) else None
        orders = get_trendyol_orders_data(creds)
        
        segments_data = calculate_customer_segments(orders)
        
        result = []
        segment_names = {
            "vip": "VIP Müşteriler",
            "loyal": "Sadık Müşteriler",
            "regular": "Düzenli Müşteriler",
            "new": "Yeni Müşteriler",
            "at_risk": "Risk Altındaki Müşteriler"
        }
        
        segment_descriptions = {
            "vip": "Yüksek harcama yapan, sık sipariş veren müşteriler",
            "loyal": "Düzenli sipariş veren, sadık müşteriler",
            "regular": "Orta seviye sipariş veren müşteriler",
            "new": "Yeni başlayan müşteriler",
            "at_risk": "Uzun süredir sipariş vermeyen müşteriler"
        }
        
        for segment_id, customers in segments_data.items():
            if customers:
                total_revenue = sum(c["total_revenue"] for c in customers)
                avg_order_value = sum(c["avg_order_value"] for c in customers) / len(customers)
                
                result.append(CustomerSegment(
                    segment_id=segment_id,
                    segment_name=segment_names.get(segment_id, segment_id),
                    description=segment_descriptions.get(segment_id, ""),
                    criteria={
                        "min_revenue": 5000 if segment_id == "vip" else 2000 if segment_id == "loyal" else 0,
                        "min_orders": 10 if segment_id == "vip" else 5 if segment_id == "loyal" else 3 if segment_id == "regular" else 0
                    },
                    customer_count=len(customers),
                    total_revenue=total_revenue,
                    avg_order_value=avg_order_value,
                    created_at=datetime.now().isoformat()
                ))
        
        return result
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Segment analizi hatası: {str(e)}"
        )


@router.get("/customers", response_model=List[CustomerProfile])
async def get_customer_profiles(
    segment: Optional[str] = None,
    limit: int = 100,
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Optional[Session] = Depends(get_db) if _db_available else None
):
    """
    Müşteri profillerini getirir
    """
    try:
        from routers.products import get_trendyol_orders_data
        creds = try_resolve_trendyol_creds(db, store) if (_db_available and store) else None
        orders = get_trendyol_orders_data(creds)
        
        if not orders:
            return []
        
        segments_data = calculate_customer_segments(orders)
        
        all_customers = []
        for customers in segments_data.values():
            all_customers.extend(customers)
        
        # Segment filtresi
        if segment:
            all_customers = [c for c in all_customers if c.get("segment") == segment]
        
        # Sıralama (toplam gelire göre)
        all_customers.sort(key=lambda x: x.get("total_revenue", 0), reverse=True)
        
        # Limit
        all_customers = all_customers[:limit]
        
        # CustomerProfile formatına çevir
        profiles = []
        for customer in all_customers:
            try:
                profiles.append(CustomerProfile(
                    customer_id=str(customer.get("customer_id", "unknown")),
                    customer_name=customer.get("customer_name"),
                    email=customer.get("email"),
                    phone=customer.get("phone"),
                    total_orders=int(customer.get("order_count", 0)),
                    total_revenue=float(customer.get("total_revenue", 0)),
                    avg_order_value=float(customer.get("avg_order_value", 0)),
                    first_order_date=customer.get("first_order_date"),
                    last_order_date=customer.get("last_order_date"),
                    days_since_last_order=customer.get("days_since_last_order"),
                    favorite_category=customer.get("favorite_category"),
                    segment=str(customer.get("segment", "regular")),
                    customer_lifetime_value=float(customer.get("customer_lifetime_value", 0)),
                    churn_risk=str(customer.get("churn_risk", "medium")),
                    created_at=datetime.now().isoformat()
                ))
            except Exception as e:
                print(f"[CustomerSegmentation] Müşteri profili oluşturma hatası: {e}, customer: {customer.get('customer_id', 'unknown')}")
                continue
        
        return profiles
    
    except Exception as e:
        import traceback
        print(f"[CustomerSegmentation] Müşteri profilleri hatası: {e}")
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Müşteri profilleri hatası: {str(e)}"
        )


@router.get("/segments/{segment_id}/analysis", response_model=SegmentAnalysis)
async def get_segment_analysis(
    segment_id: str,
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Optional[Session] = Depends(get_db) if _db_available else None
):
    """
    Segment detaylı analizi
    """
    try:
        from routers.products import get_trendyol_orders_data
        creds = try_resolve_trendyol_creds(db, store) if (_db_available and store) else None
        orders = get_trendyol_orders_data(creds)
        
        segments_data = calculate_customer_segments(orders)
        
        if segment_id not in segments_data or not segments_data[segment_id]:
            raise HTTPException(status_code=404, detail="Segment bulunamadı")
        
        customers = segments_data[segment_id]
        
        # Toplam gelir
        total_revenue = sum(c["total_revenue"] for c in customers)
        avg_revenue_per_customer = total_revenue / len(customers) if customers else 0
        avg_orders_per_customer = sum(c["order_count"] for c in customers) / len(customers) if customers else 0
        
        # En çok satılan ürünler ve kategoriler
        all_products = {}
        all_categories = {}
        
        for customer in customers:
            if customer.get("favorite_category"):
                all_categories[customer["favorite_category"]] = (
                    all_categories.get(customer["favorite_category"], 0) + 1
                )
        
        top_products = sorted(
            all_products.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]
        
        top_categories = sorted(
            all_categories.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]
        
        # Büyüme trendi (basit)
        growth_trend = "stable"
        if len(customers) > 10:
            growth_trend = "increasing"
        elif len(customers) < 3:
            growth_trend = "decreasing"
        
        # Öneriler
        recommendations = []
        if segment_id == "vip":
            recommendations = [
                "VIP müşterilere özel kampanyalar düzenleyin",
                "Erken erişim fırsatları sunun",
                "Özel müşteri hizmeti sağlayın"
            ]
        elif segment_id == "at_risk":
            recommendations = [
                "Müşteri geri kazanma kampanyaları başlatın",
                "Özel indirim teklifleri gönderin",
                "Müşteri geri bildirimleri toplayın"
            ]
        elif segment_id == "new":
            recommendations = [
                "Hoş geldin kampanyaları düzenleyin",
                "İlk sipariş indirimleri sunun",
                "Müşteri sadakat programına dahil edin"
            ]
        
        segment_names = {
            "vip": "VIP Müşteriler",
            "loyal": "Sadık Müşteriler",
            "regular": "Düzenli Müşteriler",
            "new": "Yeni Müşteriler",
            "at_risk": "Risk Altındaki Müşteriler"
        }
        
        return SegmentAnalysis(
            segment_id=segment_id,
            segment_name=segment_names.get(segment_id, segment_id),
            total_customers=len(customers),
            total_revenue=total_revenue,
            avg_revenue_per_customer=avg_revenue_per_customer,
            avg_orders_per_customer=avg_orders_per_customer,
            top_products=[{"name": p[0], "count": p[1]} for p in top_products],
            top_categories=[{"name": c[0], "count": c[1]} for c in top_categories],
            growth_trend=growth_trend,
            recommendations=recommendations
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Segment analizi hatası: {str(e)}"
        )


@router.get("/churn-risk")
async def get_churn_risk_customers(
    risk_level: Optional[str] = None,
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Optional[Session] = Depends(get_db) if _db_available else None
):
    """
    Churn riski olan müşterileri getirir
    """
    try:
        from routers.products import get_trendyol_orders_data
        creds = try_resolve_trendyol_creds(db, store) if (_db_available and store) else None
        orders = get_trendyol_orders_data(creds)
        
        segments_data = calculate_customer_segments(orders)
        
        at_risk_customers = segments_data.get("at_risk", [])
        
        # Risk seviyesine göre filtrele
        if risk_level:
            at_risk_customers = [
                c for c in at_risk_customers
                if c.get("churn_risk") == risk_level
            ]
        
        # Sıralama (en uzun süre sipariş vermeyenler)
        at_risk_customers.sort(
            key=lambda x: x.get("days_since_last_order", 0),
            reverse=True
        )
        
        return {
            "total_customers": len(at_risk_customers),
            "customers": at_risk_customers[:50]  # İlk 50
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Churn risk analizi hatası: {str(e)}"
        )

