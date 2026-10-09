"""
İade ve İptal Yönetimi Router
Trendyol iade ve iptal işlemlerini yönetir
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
    from database.models import ReturnRefund, Order, Store
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


def _check_db():
    """Database kontrolü - ghost mode"""
    if not _db_available:
        raise HTTPException(status_code=503, detail="Database not available (ghost mode)")


class ReturnRefundRequest(BaseModel):
    """İade/İptal talebi modeli"""
    order_id: str
    return_type: str  # 'return', 'cancel', 'refund'
    reason: Optional[str] = None
    reason_code: Optional[str] = None
    items: Optional[List[Dict[str, Any]]] = None
    notes: Optional[str] = None


class ReturnRefundResponse(BaseModel):
    """İade/İptal yanıt modeli"""
    id: int
    return_id: str
    order_id: str
    order_number: Optional[str]
    return_type: str
    status: str
    reason: Optional[str]
    total_amount: float
    refund_amount: float
    customer_name: Optional[str]
    created_at: str
    updated_at: str


class ReturnRefundStats(BaseModel):
    """İade/İptal istatistikleri"""
    total_returns: int
    total_cancels: int
    total_refunds: int
    pending_count: int
    approved_count: int
    rejected_count: int
    completed_count: int
    total_refund_amount: float
    return_rate: float  # İade oranı (%)
    top_reasons: List[Dict[str, Any]]


def get_trendyol_auth_headers():
    """Trendyol API için auth header'ları oluştur"""
    api_key = os.getenv("TRENDYOL_API_KEY")
    api_secret = os.getenv("TRENDYOL_API_SECRET")
    
    if not all([api_key, api_secret]):
        return None
    
    auth_string = f"{api_key}:{api_secret}"
    auth_bytes = auth_string.encode('ascii')
    auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
    
    return {
        "Authorization": f"Basic {auth_b64}",
        "Content-Type": "application/json"
    }


@router.get("/", response_model=List[ReturnRefundResponse])
async def get_returns(
    return_type: Optional[str] = None,
    status: Optional[str] = None,
    days: int = 30,
    store: Store = Depends(get_current_store),
    db: Session = Depends(get_db)
):
    """
    İade ve iptal listesini getirir

    Args:
        return_type: Filtreleme için tip ('return', 'cancel', 'refund')
        status: Filtreleme için durum ('pending', 'approved', 'rejected', 'completed')
        days: Son kaç günün verileri (varsayılan: 30)
    """
    query = db.query(ReturnRefund).filter(ReturnRefund.store_id == store.id)
    
    # Tarih filtresi
    date_filter = datetime.now() - timedelta(days=days)
    query = query.filter(ReturnRefund.created_at >= date_filter)
    
    # Tip filtresi
    if return_type:
        query = query.filter(ReturnRefund.return_type == return_type)
    
    # Durum filtresi
    if status:
        query = query.filter(ReturnRefund.status == status)
    
    returns = query.order_by(ReturnRefund.created_at.desc()).limit(100).all()
    
    return [
        ReturnRefundResponse(
            id=r.id,
            return_id=r.return_id,
            order_id=r.order_id,
            order_number=r.order_number,
            return_type=r.return_type,
            status=r.status,
            reason=r.reason,
            total_amount=r.total_amount,
            refund_amount=r.refund_amount,
            customer_name=r.customer_name,
            created_at=r.created_at.isoformat() if r.created_at else "",
            updated_at=r.updated_at.isoformat() if r.updated_at else ""
        )
        for r in returns
    ]


@router.get("/stats", response_model=ReturnRefundStats)
async def get_return_stats(
    days: int = 30,
    store: Store = Depends(get_current_store),
    db: Session = Depends(get_db)
):
    """İade ve iptal istatistiklerini getirir"""
    date_filter = datetime.now() - timedelta(days=days)
    sid = ReturnRefund.store_id == store.id

    # Toplam sayılar
    total_returns = db.query(ReturnRefund).filter(
        and_(sid, ReturnRefund.return_type == 'return', ReturnRefund.created_at >= date_filter)
    ).count()

    total_cancels = db.query(ReturnRefund).filter(
        and_(sid, ReturnRefund.return_type == 'cancel', ReturnRefund.created_at >= date_filter)
    ).count()

    total_refunds = db.query(ReturnRefund).filter(
        and_(sid, ReturnRefund.return_type == 'refund', ReturnRefund.created_at >= date_filter)
    ).count()

    # Durum bazlı sayılar
    pending_count = db.query(ReturnRefund).filter(
        and_(sid, ReturnRefund.status == 'pending', ReturnRefund.created_at >= date_filter)
    ).count()

    approved_count = db.query(ReturnRefund).filter(
        and_(sid, ReturnRefund.status == 'approved', ReturnRefund.created_at >= date_filter)
    ).count()

    rejected_count = db.query(ReturnRefund).filter(
        and_(sid, ReturnRefund.status == 'rejected', ReturnRefund.created_at >= date_filter)
    ).count()

    completed_count = db.query(ReturnRefund).filter(
        and_(sid, ReturnRefund.status == 'completed', ReturnRefund.created_at >= date_filter)
    ).count()

    # Toplam iade tutarı
    total_refund_amount_result = db.query(func.sum(ReturnRefund.refund_amount)).filter(
        and_(sid, ReturnRefund.created_at >= date_filter)
    ).scalar()
    total_refund_amount = float(total_refund_amount_result) if total_refund_amount_result else 0.0

    # Top nedenler
    reasons_query = db.query(
        ReturnRefund.reason,
        func.count(ReturnRefund.id).label('count')
    ).filter(
        and_(sid, ReturnRefund.reason.isnot(None), ReturnRefund.created_at >= date_filter)
    ).group_by(ReturnRefund.reason).order_by(func.count(ReturnRefund.id).desc()).limit(5).all()

    top_reasons = [
        {"reason": reason, "count": count}
        for reason, count in reasons_query
    ]

    # İade oranı hesaplama (toplam sipariş sayısına göre)
    total_orders = db.query(Order).filter(Order.store_id == store.id, Order.order_date >= date_filter).count()
    return_rate = (total_returns / total_orders * 100) if total_orders > 0 else 0.0
    
    return ReturnRefundStats(
        total_returns=total_returns,
        total_cancels=total_cancels,
        total_refunds=total_refunds,
        pending_count=pending_count,
        approved_count=approved_count,
        rejected_count=rejected_count,
        completed_count=completed_count,
        total_refund_amount=total_refund_amount,
        return_rate=round(return_rate, 2),
        top_reasons=top_reasons
    )


@router.get("/{return_id}", response_model=ReturnRefundResponse)
async def get_return_detail(
    return_id: str,
    store: Store = Depends(get_current_store),
    db: Session = Depends(get_db)
):
    """Belirli bir iade/iptal detayını getirir"""
    return_item = db.query(ReturnRefund).filter(ReturnRefund.store_id == store.id, ReturnRefund.return_id == return_id).first()
    
    if not return_item:
        raise HTTPException(status_code=404, detail="İade/İptal kaydı bulunamadı")
    
    return ReturnRefundResponse(
        id=return_item.id,
        return_id=return_item.return_id,
        order_id=return_item.order_id,
        order_number=return_item.order_number,
        return_type=return_item.return_type,
        status=return_item.status,
        reason=return_item.reason,
        total_amount=return_item.total_amount,
        refund_amount=return_item.refund_amount,
        customer_name=return_item.customer_name,
        created_at=return_item.created_at.isoformat() if return_item.created_at else "",
        updated_at=return_item.updated_at.isoformat() if return_item.updated_at else ""
    )


@router.post("/", response_model=ReturnRefundResponse)
async def create_return(
    request: ReturnRefundRequest,
    store: Store = Depends(get_current_store),
    db: Session = Depends(get_db)
):
    """Yeni bir iade/iptal kaydı oluşturur"""
    # Sipariş kontrolü
    order = db.query(Order).filter(Order.store_id == store.id, Order.order_id == request.order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Sipariş bulunamadı")

    # Return ID oluştur
    return_id = f"RET-{request.order_id}-{int(datetime.now().timestamp())}"

    # Yeni kayıt oluştur
    new_return = ReturnRefund(
        store_id=store.id,
        return_id=return_id,
        order_id=request.order_id,
        order_number=order.order_number,
        return_type=request.return_type,
        status='pending',
        reason=request.reason,
        reason_code=request.reason_code,
        customer_name=order.customer_name,
        total_amount=order.total_amount,
        refund_amount=order.total_amount,  # Varsayılan olarak tam tutar
        items=json.dumps(request.items) if request.items else None,
        notes=request.notes
    )
    
    db.add(new_return)
    db.commit()
    db.refresh(new_return)
    
    return ReturnRefundResponse(
        id=new_return.id,
        return_id=new_return.return_id,
        order_id=new_return.order_id,
        order_number=new_return.order_number,
        return_type=new_return.return_type,
        status=new_return.status,
        reason=new_return.reason,
        total_amount=new_return.total_amount,
        refund_amount=new_return.refund_amount,
        customer_name=new_return.customer_name,
        created_at=new_return.created_at.isoformat() if new_return.created_at else "",
        updated_at=new_return.updated_at.isoformat() if new_return.updated_at else ""
    )


@router.patch("/{return_id}/status", response_model=ReturnRefundResponse)
async def update_return_status(
    return_id: str,
    status: str,
    notes: Optional[str] = None,
    store: Store = Depends(get_current_store),
    db: Session = Depends(get_db)
):
    """İade/İptal durumunu günceller"""
    return_item = db.query(ReturnRefund).filter(ReturnRefund.store_id == store.id, ReturnRefund.return_id == return_id).first()
    
    if not return_item:
        raise HTTPException(status_code=404, detail="İade/İptal kaydı bulunamadı")
    
    valid_statuses = ['pending', 'approved', 'rejected', 'completed', 'cancelled']
    if status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Geçersiz durum. Geçerli durumlar: {', '.join(valid_statuses)}")
    
    return_item.status = status
    if notes:
        return_item.notes = notes
    if status in ['completed', 'rejected', 'cancelled']:
        return_item.processed_at = datetime.now()
    
    db.commit()
    db.refresh(return_item)
    
    return ReturnRefundResponse(
        id=return_item.id,
        return_id=return_item.return_id,
        order_id=return_item.order_id,
        order_number=return_item.order_number,
        return_type=return_item.return_type,
        status=return_item.status,
        reason=return_item.reason,
        total_amount=return_item.total_amount,
        refund_amount=return_item.refund_amount,
        customer_name=return_item.customer_name,
        created_at=return_item.created_at.isoformat() if return_item.created_at else "",
        updated_at=return_item.updated_at.isoformat() if return_item.updated_at else ""
    )


@router.get("/order/{order_id}", response_model=List[ReturnRefundResponse])
async def get_order_returns(
    order_id: str,
    store: Store = Depends(get_current_store),
    db: Session = Depends(get_db)
):
    """Belirli bir siparişe ait tüm iade/iptal kayıtlarını getirir"""
    returns = db.query(ReturnRefund).filter(ReturnRefund.store_id == store.id, ReturnRefund.order_id == order_id).order_by(ReturnRefund.created_at.desc()).all()
    
    return [
        ReturnRefundResponse(
            id=r.id,
            return_id=r.return_id,
            order_id=r.order_id,
            order_number=r.order_number,
            return_type=r.return_type,
            status=r.status,
            reason=r.reason,
            total_amount=r.total_amount,
            refund_amount=r.refund_amount,
            customer_name=r.customer_name,
            created_at=r.created_at.isoformat() if r.created_at else "",
            updated_at=r.updated_at.isoformat() if r.updated_at else ""
        )
        for r in returns
    ]


@router.delete("/{return_id}")
async def delete_return(
    return_id: str,
    store: Store = Depends(get_current_store),
    db: Session = Depends(get_db)
):
    """İade/İptal kaydını siler (sadece pending durumundakiler)"""
    return_item = db.query(ReturnRefund).filter(ReturnRefund.store_id == store.id, ReturnRefund.return_id == return_id).first()
    
    if not return_item:
        raise HTTPException(status_code=404, detail="İade/İptal kaydı bulunamadı")
    
    if return_item.status != 'pending':
        raise HTTPException(status_code=400, detail="Sadece bekleyen durumundaki kayıtlar silinebilir")
    
    db.delete(return_item)
    db.commit()
    
    return {"message": "İade/İptal kaydı silindi", "return_id": return_id}

