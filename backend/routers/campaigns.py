"""
Kampanya ve İndirim Yönetimi Router
Trendyol kampanya ve indirim işlemlerini yönetir
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
import os
import requests
import base64
import json

# Database modülünü optional olarak yükle (ghost mode)
try:
    from database.db import get_db
    from database.models import Campaign, CampaignPerformance, Order, Store, Product
    from security import get_current_store
    _db_available = True
except Exception:
    _db_available = False
    # Dummy functions for ghost mode
    def get_db():
        raise HTTPException(status_code=503, detail="Database not available (ghost mode)")

    def get_current_store():
        raise HTTPException(status_code=503, detail="Database not available (ghost mode)")

router = APIRouter()


class CampaignRequest(BaseModel):
    """Kampanya oluşturma/güncelleme modeli"""
    name: str
    description: Optional[str] = None
    campaign_type: str  # 'coupon', 'flash_sale', 'bulk_discount', 'category_discount'
    discount_type: str  # 'percentage', 'fixed_amount'
    discount_value: float
    min_purchase_amount: Optional[float] = 0.0
    max_discount_amount: Optional[float] = None
    coupon_code: Optional[str] = None
    start_date: str  # ISO format
    end_date: str  # ISO format
    target_products: Optional[List[str]] = None
    target_categories: Optional[List[str]] = None
    usage_limit: Optional[int] = None
    max_usage_per_customer: Optional[int] = 1


class CampaignResponse(BaseModel):
    """Kampanya yanıt modeli"""
    id: int
    campaign_id: str
    name: str
    description: Optional[str]
    campaign_type: str
    discount_type: str
    discount_value: float
    min_purchase_amount: float
    max_discount_amount: Optional[float]
    coupon_code: Optional[str]
    start_date: str
    end_date: str
    status: str
    usage_limit: Optional[int]
    usage_count: int
    max_usage_per_customer: int
    is_active: bool
    created_at: str
    updated_at: str


class CampaignStats(BaseModel):
    """Kampanya istatistikleri"""
    total_campaigns: int
    active_campaigns: int
    total_discount_amount: float
    total_orders: int
    total_revenue: float
    average_discount_rate: float
    top_campaigns: List[Dict[str, Any]]


def generate_campaign_id() -> str:
    """Benzersiz kampanya ID oluştur"""
    return f"CMP-{int(datetime.now().timestamp())}"


def _check_db():
    """Database kontrolü - ghost mode"""
    if not _db_available:
        raise HTTPException(status_code=503, detail="Database not available (ghost mode)")


def generate_coupon_code() -> str:
    """Benzersiz kupon kodu oluştur"""
    import random
    import string
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))


@router.get("/", response_model=List[CampaignResponse])
async def get_campaigns(
    status: Optional[str] = None,
    campaign_type: Optional[str] = None,
    is_active: Optional[bool] = None,
    store: Store = Depends(get_current_store),
    db: Session = Depends(get_db)
):
    """
    Kampanya listesini getirir

    Args:
        status: Filtreleme için durum
        campaign_type: Filtreleme için kampanya tipi
        is_active: Aktif kampanyaları filtrele
    """
    query = db.query(Campaign).filter(Campaign.store_id == store.id)

    if status:
        query = query.filter(Campaign.status == status)
    
    if campaign_type:
        query = query.filter(Campaign.campaign_type == campaign_type)
    
    if is_active is not None:
        query = query.filter(Campaign.is_active == is_active)
    
    campaigns = query.order_by(Campaign.created_at.desc()).all()
    
    return [
        CampaignResponse(
            id=c.id,
            campaign_id=c.campaign_id,
            name=c.name,
            description=c.description,
            campaign_type=c.campaign_type,
            discount_type=c.discount_type,
            discount_value=c.discount_value,
            min_purchase_amount=c.min_purchase_amount,
            max_discount_amount=c.max_discount_amount,
            coupon_code=c.coupon_code,
            start_date=c.start_date.isoformat() if c.start_date else "",
            end_date=c.end_date.isoformat() if c.end_date else "",
            status=c.status,
            usage_limit=c.usage_limit,
            usage_count=c.usage_count,
            max_usage_per_customer=c.max_usage_per_customer,
            is_active=c.is_active,
            created_at=c.created_at.isoformat() if c.created_at else "",
            updated_at=c.updated_at.isoformat() if c.updated_at else ""
        )
        for c in campaigns
    ]


@router.get("/stats", response_model=CampaignStats)
async def get_campaign_stats(
    days: int = 30,
    store: Store = Depends(get_current_store),
    db: Session = Depends(get_db)
):
    """Kampanya istatistiklerini getirir"""
    date_filter = datetime.now() - timedelta(days=days)

    # Toplam kampanya sayısı
    total_campaigns = db.query(Campaign).filter(
        Campaign.store_id == store.id,
        Campaign.created_at >= date_filter
    ).count()

    # Aktif kampanya sayısı
    active_campaigns = db.query(Campaign).filter(
        and_(
            Campaign.store_id == store.id,
            Campaign.is_active == True,
            Campaign.status == 'active',
            Campaign.start_date <= datetime.now(),
            Campaign.end_date >= datetime.now()
        )
    ).count()

    # Performans verilerini topla
    performance_data = db.query(
        func.sum(CampaignPerformance.orders_count).label('total_orders'),
        func.sum(CampaignPerformance.revenue).label('total_revenue'),
        func.sum(CampaignPerformance.discount_amount).label('total_discount')
    ).filter(
        CampaignPerformance.store_id == store.id,
        CampaignPerformance.date >= date_filter
    ).first()

    total_orders = performance_data.total_orders or 0
    total_revenue = float(performance_data.total_revenue or 0)
    total_discount_amount = float(performance_data.total_discount or 0)

    # Ortalama indirim oranı
    campaigns_with_discount = db.query(Campaign).filter(
        and_(
            Campaign.store_id == store.id,
            Campaign.created_at >= date_filter,
            Campaign.discount_type == 'percentage'
        )
    ).all()
    
    avg_discount_rate = 0.0
    if campaigns_with_discount:
        total_discount = sum(c.discount_value for c in campaigns_with_discount)
        avg_discount_rate = total_discount / len(campaigns_with_discount)
    
    # En iyi performans gösteren kampanyalar
    top_campaigns_query = db.query(
        CampaignPerformance.campaign_id,
        func.sum(CampaignPerformance.orders_count).label('orders'),
        func.sum(CampaignPerformance.revenue).label('revenue')
    ).filter(
        CampaignPerformance.store_id == store.id,
        CampaignPerformance.date >= date_filter
    ).group_by(CampaignPerformance.campaign_id).order_by(
        func.sum(CampaignPerformance.orders_count).desc()
    ).limit(5).all()

    top_campaigns = []
    for campaign_id, orders, revenue in top_campaigns_query:
        campaign = db.query(Campaign).filter(Campaign.store_id == store.id, Campaign.campaign_id == campaign_id).first()
        if campaign:
            top_campaigns.append({
                "campaign_id": campaign_id,
                "name": campaign.name,
                "orders": orders or 0,
                "revenue": float(revenue or 0)
            })
    
    return CampaignStats(
        total_campaigns=total_campaigns,
        active_campaigns=active_campaigns,
        total_discount_amount=total_discount_amount,
        total_orders=total_orders,
        total_revenue=total_revenue,
        average_discount_rate=round(avg_discount_rate, 2),
        top_campaigns=top_campaigns
    )


@router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_campaign_detail(
    campaign_id: str,
    store: Store = Depends(get_current_store),
    db: Session = Depends(get_db)
):
    """Belirli bir kampanya detayını getirir"""
    campaign = db.query(Campaign).filter(Campaign.store_id == store.id, Campaign.campaign_id == campaign_id).first()
    
    if not campaign:
        raise HTTPException(status_code=404, detail="Kampanya bulunamadı")
    
    return CampaignResponse(
        id=campaign.id,
        campaign_id=campaign.campaign_id,
        name=campaign.name,
        description=campaign.description,
        campaign_type=campaign.campaign_type,
        discount_type=campaign.discount_type,
        discount_value=campaign.discount_value,
        min_purchase_amount=campaign.min_purchase_amount,
        max_discount_amount=campaign.max_discount_amount,
        coupon_code=campaign.coupon_code,
        start_date=campaign.start_date.isoformat() if campaign.start_date else "",
        end_date=campaign.end_date.isoformat() if campaign.end_date else "",
        status=campaign.status,
        usage_limit=campaign.usage_limit,
        usage_count=campaign.usage_count,
        max_usage_per_customer=campaign.max_usage_per_customer,
        is_active=campaign.is_active,
        created_at=campaign.created_at.isoformat() if campaign.created_at else "",
        updated_at=campaign.updated_at.isoformat() if campaign.updated_at else ""
    )


@router.post("/", response_model=CampaignResponse)
async def create_campaign(
    request: CampaignRequest,
    store: Store = Depends(get_current_store),
    db: Session = Depends(get_db)
):
    """Yeni bir kampanya oluşturur"""
    # Tarih kontrolü
    start_date = datetime.fromisoformat(request.start_date.replace('Z', '+00:00'))
    end_date = datetime.fromisoformat(request.end_date.replace('Z', '+00:00'))

    if end_date <= start_date:
        raise HTTPException(status_code=400, detail="Bitiş tarihi başlangıç tarihinden sonra olmalıdır")

    # Kupon kodu kontrolü
    coupon_code = request.coupon_code
    if not coupon_code and request.campaign_type == 'coupon':
        coupon_code = generate_coupon_code()

    if coupon_code:
        existing = db.query(Campaign).filter(Campaign.store_id == store.id, Campaign.coupon_code == coupon_code).first()
        if existing:
            raise HTTPException(status_code=400, detail="Bu kupon kodu zaten kullanılıyor")
    
    # Kampanya ID oluştur
    campaign_id = generate_campaign_id()
    
    # Durum belirleme
    now = datetime.now()
    if start_date > now:
        status = 'draft'
    elif start_date <= now <= end_date:
        status = 'active'
    else:
        status = 'expired'
    
    # Yeni kampanya oluştur
    new_campaign = Campaign(
        store_id=store.id,
        campaign_id=campaign_id,
        name=request.name,
        description=request.description,
        campaign_type=request.campaign_type,
        discount_type=request.discount_type,
        discount_value=request.discount_value,
        min_purchase_amount=request.min_purchase_amount or 0.0,
        max_discount_amount=request.max_discount_amount,
        coupon_code=coupon_code,
        start_date=start_date,
        end_date=end_date,
        status=status,
        target_products=json.dumps(request.target_products) if request.target_products else None,
        target_categories=json.dumps(request.target_categories) if request.target_categories else None,
        usage_limit=request.usage_limit,
        max_usage_per_customer=request.max_usage_per_customer or 1,
        is_active=True
    )
    
    db.add(new_campaign)
    db.commit()
    db.refresh(new_campaign)
    
    return CampaignResponse(
        id=new_campaign.id,
        campaign_id=new_campaign.campaign_id,
        name=new_campaign.name,
        description=new_campaign.description,
        campaign_type=new_campaign.campaign_type,
        discount_type=new_campaign.discount_type,
        discount_value=new_campaign.discount_value,
        min_purchase_amount=new_campaign.min_purchase_amount,
        max_discount_amount=new_campaign.max_discount_amount,
        coupon_code=new_campaign.coupon_code,
        start_date=new_campaign.start_date.isoformat() if new_campaign.start_date else "",
        end_date=new_campaign.end_date.isoformat() if new_campaign.end_date else "",
        status=new_campaign.status,
        usage_limit=new_campaign.usage_limit,
        usage_count=new_campaign.usage_count,
        max_usage_per_customer=new_campaign.max_usage_per_customer,
        is_active=new_campaign.is_active,
        created_at=new_campaign.created_at.isoformat() if new_campaign.created_at else "",
        updated_at=new_campaign.updated_at.isoformat() if new_campaign.updated_at else ""
    )


@router.patch("/{campaign_id}", response_model=CampaignResponse)
async def update_campaign(
    campaign_id: str,
    request: Dict[str, Any],
    store: Store = Depends(get_current_store),
    db: Session = Depends(get_db)
):
    """Kampanya bilgilerini günceller"""
    campaign = db.query(Campaign).filter(Campaign.store_id == store.id, Campaign.campaign_id == campaign_id).first()
    
    if not campaign:
        raise HTTPException(status_code=404, detail="Kampanya bulunamadı")
    
    # Güncellenebilir alanlar
    updatable_fields = [
        'name', 'description', 'discount_value', 'min_purchase_amount',
        'max_discount_amount', 'usage_limit', 'max_usage_per_customer', 'status', 'is_active'
    ]
    
    for field, value in request.items():
        if field in updatable_fields and hasattr(campaign, field):
            setattr(campaign, field, value)
    
    # Tarih güncellemeleri
    if 'start_date' in request:
        campaign.start_date = datetime.fromisoformat(request['start_date'].replace('Z', '+00:00'))
    if 'end_date' in request:
        campaign.end_date = datetime.fromisoformat(request['end_date'].replace('Z', '+00:00'))
    
    # Durum güncelleme
    now = datetime.now()
    if campaign.start_date and campaign.end_date:
        if campaign.start_date > now:
            campaign.status = 'draft'
        elif campaign.start_date <= now <= campaign.end_date:
            campaign.status = 'active'
        else:
            campaign.status = 'expired'
    
    db.commit()
    db.refresh(campaign)
    
    return CampaignResponse(
        id=campaign.id,
        campaign_id=campaign.campaign_id,
        name=campaign.name,
        description=campaign.description,
        campaign_type=campaign.campaign_type,
        discount_type=campaign.discount_type,
        discount_value=campaign.discount_value,
        min_purchase_amount=campaign.min_purchase_amount,
        max_discount_amount=campaign.max_discount_amount,
        coupon_code=campaign.coupon_code,
        start_date=campaign.start_date.isoformat() if campaign.start_date else "",
        end_date=campaign.end_date.isoformat() if campaign.end_date else "",
        status=campaign.status,
        usage_limit=campaign.usage_limit,
        usage_count=campaign.usage_count,
        max_usage_per_customer=campaign.max_usage_per_customer,
        is_active=campaign.is_active,
        created_at=campaign.created_at.isoformat() if campaign.created_at else "",
        updated_at=campaign.updated_at.isoformat() if campaign.updated_at else ""
    )


@router.patch("/{campaign_id}/toggle", response_model=CampaignResponse)
async def toggle_campaign(
    campaign_id: str,
    store: Store = Depends(get_current_store),
    db: Session = Depends(get_db)
):
    """Kampanyayı aktif/pasif yapar"""
    campaign = db.query(Campaign).filter(Campaign.store_id == store.id, Campaign.campaign_id == campaign_id).first()
    
    if not campaign:
        raise HTTPException(status_code=404, detail="Kampanya bulunamadı")
    
    campaign.is_active = not campaign.is_active
    
    if not campaign.is_active:
        campaign.status = 'paused'
    elif campaign.start_date <= datetime.now() <= campaign.end_date:
        campaign.status = 'active'
    
    db.commit()
    db.refresh(campaign)
    
    return CampaignResponse(
        id=campaign.id,
        campaign_id=campaign.campaign_id,
        name=campaign.name,
        description=campaign.description,
        campaign_type=campaign.campaign_type,
        discount_type=campaign.discount_type,
        discount_value=campaign.discount_value,
        min_purchase_amount=campaign.min_purchase_amount,
        max_discount_amount=campaign.max_discount_amount,
        coupon_code=campaign.coupon_code,
        start_date=campaign.start_date.isoformat() if campaign.start_date else "",
        end_date=campaign.end_date.isoformat() if campaign.end_date else "",
        status=campaign.status,
        usage_limit=campaign.usage_limit,
        usage_count=campaign.usage_count,
        max_usage_per_customer=campaign.max_usage_per_customer,
        is_active=campaign.is_active,
        created_at=campaign.created_at.isoformat() if campaign.created_at else "",
        updated_at=campaign.updated_at.isoformat() if campaign.updated_at else ""
    )


@router.delete("/{campaign_id}")
async def delete_campaign(
    campaign_id: str,
    store: Store = Depends(get_current_store),
    db: Session = Depends(get_db)
):
    """Kampanyayı siler (sadece draft durumundakiler)"""
    campaign = db.query(Campaign).filter(Campaign.store_id == store.id, Campaign.campaign_id == campaign_id).first()
    
    if not campaign:
        raise HTTPException(status_code=404, detail="Kampanya bulunamadı")
    
    if campaign.status != 'draft':
        raise HTTPException(status_code=400, detail="Sadece taslak durumundaki kampanyalar silinebilir")
    
    db.delete(campaign)
    db.commit()
    
    return {"message": "Kampanya silindi", "campaign_id": campaign_id}


@router.get("/coupon/{coupon_code}", response_model=CampaignResponse)
async def get_campaign_by_coupon(
    coupon_code: str,
    store: Store = Depends(get_current_store),
    db: Session = Depends(get_db)
):
    """Kupon koduna göre kampanya getirir"""
    campaign = db.query(Campaign).filter(Campaign.store_id == store.id, Campaign.coupon_code == coupon_code).first()
    
    if not campaign:
        raise HTTPException(status_code=404, detail="Kupon kodu bulunamadı")
    
    # Kupon geçerliliği kontrolü
    now = datetime.now()
    if not campaign.is_active:
        raise HTTPException(status_code=400, detail="Bu kupon aktif değil")
    
    if campaign.start_date > now:
        raise HTTPException(status_code=400, detail="Bu kupon henüz başlamadı")
    
    if campaign.end_date < now:
        raise HTTPException(status_code=400, detail="Bu kuponun süresi dolmuş")
    
    if campaign.usage_limit and campaign.usage_count >= campaign.usage_limit:
        raise HTTPException(status_code=400, detail="Bu kuponun kullanım limiti dolmuş")
    
    return CampaignResponse(
        id=campaign.id,
        campaign_id=campaign.campaign_id,
        name=campaign.name,
        description=campaign.description,
        campaign_type=campaign.campaign_type,
        discount_type=campaign.discount_type,
        discount_value=campaign.discount_value,
        min_purchase_amount=campaign.min_purchase_amount,
        max_discount_amount=campaign.max_discount_amount,
        coupon_code=campaign.coupon_code,
        start_date=campaign.start_date.isoformat() if campaign.start_date else "",
        end_date=campaign.end_date.isoformat() if campaign.end_date else "",
        status=campaign.status,
        usage_limit=campaign.usage_limit,
        usage_count=campaign.usage_count,
        max_usage_per_customer=campaign.max_usage_per_customer,
        is_active=campaign.is_active,
        created_at=campaign.created_at.isoformat() if campaign.created_at else "",
        updated_at=campaign.updated_at.isoformat() if campaign.updated_at else ""
    )



# ---------------------------------------------------------------------------
# Wave2c — Kampanya Kâr-Etkisi ("katılırsan tahmini kârın")
# Jim w2b-reconciliation-campaign-logic.md BÖLÜM2 mantığı.
# w2a Net Kâr formülünü İNDİRİMLİ fiyata uygular; komisyonu İNDİRİMLİ fiyattan
# hesaplar (kritik nüans — atlanırsa kâr olduğundan düşük görünür). Kâr tanımı
# utils/profitability.py ile tutarlı: net = fiyat - ürün_maliyeti - komisyon - kargo
# (net-aşama KDV/hizmet placeholder'ları şu an 0). store-scoped + JWT + lokal DB.
# ---------------------------------------------------------------------------
class CampaignProfitEffectRequest(BaseModel):
    """Kampanya senaryosu: indirim + tip. product_ids boşsa maliyeti girili tüm ürünler."""
    product_ids: Optional[List[str]] = None
    discount_type: str = "percentage"   # 'percentage' | 'fixed_amount'
    discount_value: float = 0.0
    campaign_type: str = "build_your_own"  # 'build_your_own' | 'advantageous_offers' | 'basket'
    # Avantajlı Teklifler: Trendyol komisyonun bir kısmını karşılar (yüzde, 0-100).
    # Bu, indirimli fiyattan hesaplanan komisyonu efektif olarak düşürür → kârı geri artırır.
    commission_support_pct: Optional[float] = None


def _apply_discount(price: float, discount_type: str, discount_value: float) -> float:
    if discount_type == "percentage":
        return max(0.0, price * (1 - discount_value / 100.0))
    return max(0.0, price - discount_value)


@router.post("/profit-effect")
async def campaign_profit_effect(
    request: CampaignProfitEffectRequest,
    store: Store = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    """Bir kampanya senaryosunun ürün başına ve toplam kâr etkisini hesaplar
    (mevcut kâr vs kampanya kârı + delta). Trendyol'a kampanya OLUŞTURMAZ — sadece
    'katılırsan kârın ne olur' senaryo hesabı."""
    from routers import financial as fin

    q = db.query(Product).filter(Product.store_id == store.id)
    if request.product_ids:
        q = q.filter(Product.product_id.in_(request.product_ids))
    products = q.all()

    cargo = fin.CARGO_COST_PER_PRODUCT
    support = (request.commission_support_pct or 0.0) if request.campaign_type == "advantageous_offers" else 0.0

    items = []
    total_current = 0.0
    total_new = 0.0
    skipped_no_cost = []
    for p in products:
        cost = p.default_cost or 0.0
        if cost <= 0:
            skipped_no_cost.append(p.product_id)
            continue
        current_price = p.current_price or 0.0
        current_commission = fin.calculate_commission(current_price, p.category)
        current_net = current_price - cost - current_commission - cargo

        new_price = _apply_discount(current_price, request.discount_type, request.discount_value)
        new_commission = fin.calculate_commission(new_price, p.category)  # KRİTİK: indirimli fiyattan
        if support > 0:
            new_commission = new_commission * (1 - support / 100.0)  # Trendyol karşılaması kârı geri artırır
        new_net = new_price - cost - new_commission - cargo

        total_current += current_net
        total_new += new_net
        items.append({
            "product_id": p.product_id,
            "product_name": p.product_name,
            "category": p.category,
            "current_price": round(current_price, 2),
            "new_price": round(new_price, 2),
            "current_commission": round(current_commission, 2),
            "new_commission": round(new_commission, 2),
            "cost": round(cost, 2),
            "cargo_cost": round(cargo, 2),
            "current_net_profit": round(current_net, 2),
            "new_net_profit": round(new_net, 2),
            "delta": round(new_net - current_net, 2),
            "current_margin_percent": round(current_net / current_price * 100, 2) if current_price > 0 else None,
            "new_margin_percent": round(new_net / new_price * 100, 2) if new_price > 0 else None,
        })

    return {
        "campaign_type": request.campaign_type,
        "discount_type": request.discount_type,
        "discount_value": request.discount_value,
        "commission_support_pct": support if support > 0 else None,
        "items": items,
        "count": len(items),
        "skipped_no_cost_data": skipped_no_cost,
        "totals": {
            "current_net_profit": round(total_current, 2),
            "new_net_profit": round(total_new, 2),
            "delta": round(total_new - total_current, 2),
        },
        "_note": (
            "Kar tanimi Dashboard/Kar Marji ile tutarli: net = fiyat - urun_maliyeti - komisyon - kargo "
            "(net-asama KDV/hizmet placeholder'lari su an 0). Komisyon INDIRIMLI fiyattan hesaplanir (Jim). "
            "Sepet kampanyalari (basket) urun-basi degil sepet-basi indirim ister; bu endpoint urun-basi "
            "hesap yapar, sepet kompozisyonu varsayimi frontend/ileride eklenebilir (Jim: dusuk-orta guven). "
            "Trendyol'a kampanya olusturmaz, sadece senaryo."
        ),
    }
