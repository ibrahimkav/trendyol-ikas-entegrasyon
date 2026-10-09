"""
Bildirim Sistemi Router
Sipariş, stok, kargo bildirimleri
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
import os
import requests
import base64
from database import notifications_db

router = APIRouter()


class Notification(BaseModel):
    """Bildirim modeli"""
    id: str
    type: str  # "order", "stock", "cargo", "payment"
    title: str
    message: str
    priority: str  # "low", "medium", "high", "urgent"
    timestamp: str
    read: bool = False
    action_url: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


def get_trendyol_orders_data() -> List[Dict]:
    """Trendyol API'den sipariş verilerini çeker"""
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
        total_elements = None
        total_pages = None
        
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
                
                if page == 0:
                    total_elements = data.get("totalElements") or data.get("total") or None
                    total_pages = data.get("totalPages") or None
                
                if not orders:
                    break
                
                all_orders.extend(orders)
                
                if total_pages is not None:
                    if page >= total_pages - 1:
                        break
                elif len(orders) < size:
                    break
                
                page += 1
                
                if page > 100:
                    break
            except Exception:
                break
        
        return all_orders
    except Exception:
        return []


# Son kontrol edilen sipariş ID'lerini sakla (gerçek uygulamada veritabanı kullanılmalı)
last_checked_order_ids = set()

@router.get("/")
async def get_notifications():
    """
    Tüm bildirimleri döner.
    Yeni siparişler, düşük stok, kargo durumları vb.
    """
    global last_checked_order_ids
    
    orders = get_trendyol_orders_data()
    notifications = []
    
    # Yeni siparişler (son 1 saat içinde gelenler)
    now = datetime.now()
    new_orders = []
    current_order_ids = set()
    
    for order in orders:
        try:
            order_id = str(order.get("id") or order.get("orderNumber") or "")
            current_order_ids.add(order_id)
            
            order_date_str = order.get("orderDate") or order.get("order_date")
            if order_date_str:
                if isinstance(order_date_str, (int, float)):
                    _ts = float(order_date_str)
                    if _ts > 1e12:
                        _ts = _ts / 1000
                    order_date = datetime.fromtimestamp(_ts)
                elif 'T' in order_date_str:
                    order_date = datetime.fromisoformat(order_date_str.replace('Z', '+00:00'))
                else:
                    order_date = datetime.strptime(order_date_str, "%Y-%m-%d")

                # Son 1 saat içindeki siparişler
                hours_ago = (now - order_date.replace(tzinfo=None)).total_seconds() / 3600
                if hours_ago <= 1:
                    status = order.get("status") or order.get("orderStatus") or ""
                    if status in ["Created", "Picking"]:
                        # Eğer bu sipariş daha önce görülmemişse yeni sipariş
                        if order_id not in last_checked_order_ids:
                            new_orders.append(order)
        except Exception:
            continue
    
    # Son kontrol edilen ID'leri güncelle
    last_checked_order_ids = current_order_ids
    
    # Yeni sipariş bildirimleri (her sipariş için ayrı bildirim)
    for order in new_orders:
        order_id = str(order.get("id") or order.get("orderNumber") or "")
        order_number = order.get("orderNumber") or order_id
        total_amount = float(str(order.get("totalPrice") or order.get("totalPriceValue") or 0).replace(",", "."))
        customer_name = f"{order.get('customerFirstName', '')} {order.get('customerLastName', '')}".strip() or "Müşteri"
        
        notifications.append({
            "id": f"new_order_{order_id}",
            "type": "order",
            "title": "🛒 Yeni Sipariş!",
            "message": f"{customer_name} - {order_number} - {total_amount:.2f} TL",
            "priority": "high",
            "timestamp": now.isoformat(),
            "read": False,
            "action_url": "/auto-barcode",
            "metadata": {
                "order_id": order_id,
                "order_number": order_number,
                "customer_name": customer_name,
                "total_amount": total_amount,
                "is_new": True  # Ses çalması için flag
            }
        })
    
    # Bekleyen ödemeler
    pending_payment_orders = [
        o for o in orders
        if (o.get("status") or o.get("orderStatus") or "") in ["Invoiced", "Picking"]
    ]
    
    if pending_payment_orders:
        total_pending = sum(
            float(str(o.get("totalPrice") or o.get("totalPriceValue") or 0).replace(",", "."))
            for o in pending_payment_orders
        )
        
        notifications.append({
            "id": "pending_payments",
            "type": "payment",
            "title": "Bekleyen Ödemeler",
            "message": f"{len(pending_payment_orders)} sipariş için {total_pending:.2f} TL ödeme bekleniyor.",
            "priority": "medium",
            "timestamp": now.isoformat(),
            "read": False,
            "action_url": "/live-performance",
            "metadata": {"order_count": len(pending_payment_orders), "total_amount": total_pending}
        })
    
    # Kargo teslim edilmiş siparişler (son 24 saat)
    delivered_orders = []
    for order in orders:
        try:
            status = order.get("status") or order.get("orderStatus") or ""
            if status in ["Shipped", "Delivered"]:
                order_date_str = order.get("orderDate") or order.get("order_date")
                if order_date_str:
                    if isinstance(order_date_str, (int, float)):
                        _ts = float(order_date_str)
                        if _ts > 1e12:
                            _ts = _ts / 1000
                        order_date = datetime.fromtimestamp(_ts)
                    elif 'T' in order_date_str:
                        order_date = datetime.fromisoformat(order_date_str.replace('Z', '+00:00'))
                    else:
                        order_date = datetime.strptime(order_date_str, "%Y-%m-%d")

                    hours_ago = (now - order_date.replace(tzinfo=None)).total_seconds() / 3600
                    if hours_ago <= 24:
                        delivered_orders.append(order)
        except Exception:
            continue
    
    if delivered_orders:
        notifications.append({
            "id": "delivered_orders",
            "type": "cargo",
            "title": f"{len(delivered_orders)} Sipariş Teslim Edildi",
            "message": f"Son 24 saatte {len(delivered_orders)} sipariş müşteriye teslim edildi.",
            "priority": "low",
            "timestamp": now.isoformat(),
            "read": False,
            "action_url": "/live-performance",
            "metadata": {"order_count": len(delivered_orders)}
        })
    
    # Bildirimleri önceliğe göre sırala
    priority_order = {"urgent": 0, "high": 1, "medium": 2, "low": 3}
    notifications.sort(key=lambda x: priority_order.get(x["priority"], 4))
    
    # Bildirimleri veritabanına kaydet
    for notification in notifications:
        notifications_db.save_notification(notification)
    
    return {
        "notifications": notifications,
        "unread_count": len([n for n in notifications if not n.get("read", False)]),
        "total_count": len(notifications)
    }


@router.post("/mark-read/{notification_id}")
async def mark_notification_read(notification_id: str):
    """Bildirimi okundu olarak işaretle"""
    success = notifications_db.mark_as_read(notification_id)
    return {
        "success": success,
        "message": f"Bildirim {notification_id} okundu olarak işaretlendi" if success else "Bildirim bulunamadı"
    }


@router.post("/mark-all-read")
async def mark_all_read():
    """Tüm bildirimleri okundu olarak işaretle"""
    count = notifications_db.mark_all_as_read()
    return {
        "success": True,
        "message": f"{count} bildirim okundu olarak işaretlendi"
    }


@router.get("/new-orders")
async def get_new_orders():
    """
    Sadece yeni siparişleri döner (gerçek zamanlı takip için)
    """
    global last_checked_order_ids
    
    orders = get_trendyol_orders_data()
    now = datetime.now()
    new_orders = []
    current_order_ids = set()
    
    for order in orders:
        try:
            order_id = str(order.get("id") or order.get("orderNumber") or "")
            current_order_ids.add(order_id)
            
            order_date_str = order.get("orderDate") or order.get("order_date")
            if order_date_str:
                if isinstance(order_date_str, (int, float)):
                    _ts = float(order_date_str)
                    if _ts > 1e12:
                        _ts = _ts / 1000
                    order_date = datetime.fromtimestamp(_ts)
                elif 'T' in order_date_str:
                    order_date = datetime.fromisoformat(order_date_str.replace('Z', '+00:00'))
                else:
                    order_date = datetime.strptime(order_date_str, "%Y-%m-%d")

                # Son 1 saat içindeki siparişler
                hours_ago = (now - order_date.replace(tzinfo=None)).total_seconds() / 3600
                if hours_ago <= 1:
                    status = order.get("status") or order.get("orderStatus") or ""
                    if status in ["Created", "Picking"]:
                        # Eğer bu sipariş daha önce görülmemişse yeni sipariş
                        if order_id not in last_checked_order_ids:
                            new_orders.append({
                                "id": order_id,
                                "order_number": order.get("orderNumber") or order_id,
                                "customer_name": f"{order.get('customerFirstName', '')} {order.get('customerLastName', '')}".strip() or "Müşteri",
                                "total_amount": float(str(order.get("totalPrice") or order.get("totalPriceValue") or 0).replace(",", ".")),
                                "timestamp": order_date_str
                            })
        except Exception:
            continue
    
    # Son kontrol edilen ID'leri güncelle
    last_checked_order_ids = current_order_ids
    
    return {
        "new_orders": new_orders,
        "count": len(new_orders)
    }


@router.get("/history")
async def get_notification_history(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    type_filter: Optional[str] = None,
    priority_filter: Optional[str] = None,
    read_filter: Optional[bool] = None,
    search: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """Bildirim geçmişini getir (filtreleme ile)"""
    notifications = notifications_db.get_notifications(
        limit=limit,
        offset=offset,
        type_filter=type_filter,
        priority_filter=priority_filter,
        read_filter=read_filter,
        search_query=search,
        start_date=start_date,
        end_date=end_date
    )
    
    return {
        "notifications": notifications,
        "total": len(notifications),
        "limit": limit,
        "offset": offset
    }


@router.delete("/")
async def delete_notifications(notification_ids: List[str]):
    """Bildirimleri sil"""
    count = notifications_db.delete_notifications(notification_ids)
    return {
        "success": count > 0,
        "message": f"{count} bildirim silindi",
        "deleted_count": count
    }


@router.get("/stats")
async def get_notification_stats():
    """Bildirim istatistikleri"""
    stats = notifications_db.get_notification_stats()
    return stats


@router.get("/templates")
async def get_notification_templates():
    """Bildirim şablonlarını getir"""
    templates = [
        {
            "id": "new_order",
            "name": "Yeni Sipariş",
            "type": "order",
            "title_template": "🛒 Yeni Sipariş!",
            "message_template": "{customer_name} - {order_number} - {total_amount} TL",
            "priority": "high",
            "variables": ["customer_name", "order_number", "total_amount"]
        },
        {
            "id": "pending_payment",
            "name": "Bekleyen Ödeme",
            "type": "payment",
            "title_template": "💰 Bekleyen Ödeme",
            "message_template": "{count} sipariş için {total_amount} TL ödeme bekleniyor.",
            "priority": "medium",
            "variables": ["count", "total_amount"]
        },
        {
            "id": "delivered",
            "name": "Teslim Edildi",
            "type": "cargo",
            "title_template": "✅ Sipariş Teslim Edildi",
            "message_template": "{count} sipariş müşteriye teslim edildi.",
            "priority": "low",
            "variables": ["count"]
        },
        {
            "id": "low_stock",
            "name": "Düşük Stok",
            "type": "stock",
            "title_template": "⚠️ Düşük Stok Uyarısı",
            "message_template": "{product_name} ürününün stoğu {stock_count} adete düştü.",
            "priority": "high",
            "variables": ["product_name", "stock_count"]
        }
    ]
    return {"templates": templates}


@router.post("/smart-priority")
async def calculate_smart_priority(notification: Dict[str, Any]):
    """AI ile bildirim önceliğini hesapla"""
    try:
        from groq import Groq
        
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            # Fallback: Basit öncelik belirleme
            priority = "medium"
            if notification.get("type") == "order":
                priority = "high"
            elif notification.get("type") == "payment":
                priority = "medium"
            return {"priority": priority, "confidence": 0.5, "reasoning": "AI servisi yapılandırılmamış"}
        
        client = Groq(api_key=api_key)
        
        prompt = f"""Bir e-ticaret bildirim sistemi için öncelik belirleme yapıyorsun.

Bildirim Bilgileri:
- Tip: {notification.get('type', 'unknown')}
- Başlık: {notification.get('title', '')}
- Mesaj: {notification.get('message', '')}
- Metadata: {notification.get('metadata', {})}

Öncelik seviyeleri:
- urgent: Acil müdahale gerektiren (stok bitmesi, ödeme hatası)
- high: Önemli (yeni sipariş, yüksek tutarlı işlemler)
- medium: Normal öncelik (bekleyen ödemeler, günlük raporlar)
- low: Düşük öncelik (bilgilendirme, teslim bildirimleri)

Sadece öncelik seviyesini döndür (urgent, high, medium, low)."""

        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "Sen bir bildirim öncelik belirleme asistanısın. Sadece öncelik seviyesini döndür."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=50
        )
        
        priority = response.choices[0].message.content.strip().lower()
        
        # Öncelik doğrulama
        valid_priorities = ["urgent", "high", "medium", "low"]
        if priority not in valid_priorities:
            priority = "medium"
        
        return {
            "priority": priority,
            "confidence": 0.8,
            "reasoning": "AI ile öncelik belirlendi"
        }
    except Exception as e:
        # Fallback
        priority = "medium"
        if notification.get("type") == "order":
            priority = "high"
        return {
            "priority": priority,
            "confidence": 0.5,
            "reasoning": f"AI hatası: {str(e)}"
        }

