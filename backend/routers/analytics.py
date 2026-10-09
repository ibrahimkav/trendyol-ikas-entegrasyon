"""
Analitik Router
Sipariş tahminleri, müşteri davranış analizi, fiyat optimizasyonu
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os
import requests
import base64
from datetime import datetime, timedelta
from collections import Counter, defaultdict
import math
from sqlalchemy.orm import Session

from database.db import get_db
from database.models import Store
from security import get_current_store
from utils.store_trendyol import resolve_trendyol_creds, fetch_orders

router = APIRouter()


class OrderPrediction(BaseModel):
    """Sipariş tahmini"""
    predicted_orders: int
    confidence: float
    timeframe: str
    factors: List[str]
    trend: str  # "increasing", "decreasing", "stable"


class CustomerBehavior(BaseModel):
    """Müşteri davranış analizi"""
    repeat_customer_rate: float
    average_order_frequency: float
    customer_segments: Dict[str, int]
    top_customers: List[Dict[str, Any]]
    purchase_patterns: Dict[str, Any]


class PriceOptimization(BaseModel):
    """Fiyat optimizasyonu önerisi"""
    product_id: Optional[str] = None
    product_name: str
    current_price: float
    recommended_price: float
    expected_increase: float  # Beklenen satış artışı (%)
    reasoning: str
    risk_level: str  # "low", "medium", "high"


def get_trendyol_orders_data(creds=None) -> List[Dict]:
    """Bu mağazanın Trendyol siparişlerini çeker (Wave3: per-store, env DEĞİL).
    creds=None → [] (güvenli köprü); çağıranlar resolve_trendyol_creds(db, store) geçer."""
    if creds is None:
        return []
    return fetch_orders(creds)


@router.get("/debug-orders")
async def debug_orders(store: Store = Depends(get_current_store), db: Session = Depends(get_db)):
    """Sipariş verilerini debug için gösterir"""
    creds = resolve_trendyol_creds(db, store)
    orders = get_trendyol_orders_data(creds)
    
    if not orders:
        return {"message": "Sipariş bulunamadı", "count": 0}
    
    # İlk 3 siparişin detaylarını göster
    sample_orders = []
    for i, order in enumerate(orders[:3]):
        sample_orders.append({
            "index": i,
            "orderNumber": order.get("orderNumber"),
            "orderDate": order.get("orderDate"),
            "order_date": order.get("order_date"),
            "packageDate": order.get("packageDate"),
            "shipmentPackageStatusDate": order.get("shipmentPackageStatusDate"),
            "createDate": order.get("createDate"),
            "createdDate": order.get("createdDate"),
            "all_date_fields": {k: v for k, v in order.items() if "date" in k.lower() or "Date" in k},
            "status": order.get("status"),
            "keys": list(order.keys())[:20]  # İlk 20 alan
        })
    
    return {
        "total_orders": len(orders),
        "sample_orders": sample_orders
    }


@router.get("/order-predictions")
async def get_order_predictions(store: Store = Depends(get_current_store), db: Session = Depends(get_db)):
    """
    Gelecek sipariş tahminleri yapar.
    Geçmiş verilere dayanarak trend analizi yapar.
    """
    creds = resolve_trendyol_creds(db, store)
    orders = get_trendyol_orders_data(creds)
    
    # Debug: İlk siparişin yapısını kontrol et
    if orders and len(orders) > 0:
        first_order = orders[0]
        print(f"[DEBUG] İlk sipariş örnek alanlar: {list(first_order.keys())[:10]}")
        print(f"[DEBUG] orderDate: {first_order.get('orderDate')}")
        print(f"[DEBUG] order_date: {first_order.get('order_date')}")
        print(f"[DEBUG] packageDate: {first_order.get('packageDate')}")
        print(f"[DEBUG] shipmentPackageStatusDate: {first_order.get('shipmentPackageStatusDate')}")
    
    # Tüm siparişler için günlük sipariş sayılarını hesapla
    daily_orders_all = defaultdict(int)
    today = datetime.now()
    last_30_days = []
    parse_errors = 0
    
    for order in orders:
        try:
            # Trendyol API'den gelen farklı tarih alanlarını kontrol et
            order_date_str = (
                order.get("orderDate") or 
                order.get("order_date") or 
                order.get("orderDateValue") or
                order.get("packageDate") or
                order.get("shipmentPackageStatusDate") or
                order.get("createDate") or
                order.get("createdDate")
            )
            if not order_date_str:
                parse_errors += 1
                continue
                
            # Farklı tarih formatlarını destekle (orders.py ile aynı mantık)
            order_date = None
            if isinstance(order_date_str, str):
                # ISO format: 2024-01-15T10:30:00Z veya 2024-01-15T10:30:00+00:00
                if 'T' in order_date_str:
                    try:
                        # Z'yi +00:00'a çevir
                        date_str_clean = order_date_str.replace('Z', '+00:00')
                        order_date = datetime.fromisoformat(date_str_clean)
                        # Timezone bilgisini kaldır (naive datetime)
                        if order_date.tzinfo:
                            order_date = order_date.replace(tzinfo=None)
                    except:
                        try:
                            # Alternatif format: 2024-01-15 10:30:00
                            order_date = datetime.strptime(order_date_str, "%Y-%m-%d %H:%M:%S")
                        except:
                            # Sadece tarih: 2024-01-15
                            try:
                                order_date = datetime.strptime(order_date_str.split('T')[0], "%Y-%m-%d")
                            except:
                                parse_errors += 1
                                continue
                else:
                    # Sadece tarih formatı: 2024-01-15
                    try:
                        order_date = datetime.strptime(order_date_str, "%Y-%m-%d")
                    except:
                        parse_errors += 1
                        continue
            elif isinstance(order_date_str, (int, float)):
                # Timestamp formatı — Trendyol epoch-ms (13 hane) gönderir, epoch-s DEĞİL
                try:
                    _ts = float(order_date_str)
                    if _ts > 1e12:
                        _ts = _ts / 1000
                    order_date = datetime.fromtimestamp(_ts)
                    if order_date.tzinfo:
                        order_date = order_date.replace(tzinfo=None)
                except:
                    parse_errors += 1
                    continue
            else:
                parse_errors += 1
                continue
            
            if not order_date:
                parse_errors += 1
                continue
                
            day_key = order_date.strftime("%Y-%m-%d")
            daily_orders_all[day_key] += 1
            
            # Son 30 günlük siparişleri de topla
            days_diff = (today - order_date).days
            if days_diff <= 30 and days_diff >= 0:
                last_30_days.append(order)
        except Exception as e:
            # Debug için hata logla
            parse_errors += 1
            if parse_errors <= 3:  # İlk 3 hatayı göster
                print(f"[order-predictions] Tarih parse hatası: {str(e)}, order_date_str: {order.get('orderDate')}")
            continue
    
    # Günlük trend verilerini hazırla (son 30 gün için)
    daily_trend = []
    day_names_tr = {
        'Mon': 'Pzt', 'Tue': 'Sal', 'Wed': 'Çar', 'Thu': 'Per',
        'Fri': 'Cum', 'Sat': 'Cmt', 'Sun': 'Paz'
    }
    
    # Son 30 günün tarihlerini oluştur
    today = datetime.now()
    for i in range(29, -1, -1):  # Son 30 gün (bugünden geriye)
        day_date = today - timedelta(days=i)
        day_key = day_date.strftime("%Y-%m-%d")
        day_name_en = day_date.strftime("%a")
        
        daily_trend.append({
            "date": day_key,
            "orders": daily_orders_all.get(day_key, 0),  # Eğer o gün sipariş yoksa 0
            "day_name": day_names_tr.get(day_name_en, day_name_en)
        })
    
    # Debug bilgisi
    debug_info = {
        "total_orders": len(orders),
        "daily_orders_count": len(daily_orders_all),
        "daily_trend_count": len(daily_trend),
        "parse_errors": parse_errors,
        "sample_dates": list(daily_orders_all.keys())[:5] if daily_orders_all else [],
        "sample_trend": daily_trend[:3] if daily_trend else [],
        "total_orders_with_dates": sum(daily_orders_all.values()),
        "max_orders_in_day": max(daily_orders_all.values()) if daily_orders_all else 0
    }
    print(f"[DEBUG order-predictions] Toplam sipariş: {len(orders)}, Tarih parse edilen: {sum(daily_orders_all.values())}, Hatalar: {parse_errors}")
    if daily_orders_all:
        print(f"[DEBUG order-predictions] Örnek tarihler: {list(daily_orders_all.keys())[:5]}")
        print(f"[DEBUG order-predictions] En çok sipariş olan gün: {max(daily_orders_all.items(), key=lambda x: x[1]) if daily_orders_all else 'Yok'}")
    
    if not orders or len(orders) < 7:
        return {
            "predicted_orders": 0,
            "confidence": 0.0,
            "timeframe": "7 gün",
            "factors": ["Yetersiz veri"],
            "trend": "stable",
            "message": "Tahmin için yeterli veri yok (en az 7 günlük veri gerekli)",
            "daily_trend": daily_trend,  # Mevcut verilerle grafik göster
            "debug_info": debug_info
        }
    
    if len(last_30_days) < 7:
        return {
            "predicted_orders": 0,
            "confidence": 0.0,
            "timeframe": "7 gün",
            "factors": ["Yetersiz veri"],
            "trend": "stable",
            "message": "Tahmin için yeterli veri yok",
            "daily_trend": daily_trend,  # Mevcut verilerle grafik göster
            "debug_info": debug_info
        }
    
    # Son 30 gün için günlük sipariş sayılarını hesapla (tahmin için)
    daily_orders_last30 = defaultdict(int)
    for order in last_30_days:
        try:
            order_date_str = order.get("orderDate") or order.get("order_date")
            if isinstance(order_date_str, (int, float)):
                _ts = float(order_date_str)
                if _ts > 1e12:
                    _ts = _ts / 1000
                order_date = datetime.fromtimestamp(_ts)
            elif 'T' in order_date_str:
                order_date = datetime.fromisoformat(order_date_str.replace('Z', '+00:00'))
            else:
                order_date = datetime.strptime(order_date_str, "%Y-%m-%d")
            day_key = order_date.strftime("%Y-%m-%d")
            daily_orders_last30[day_key] += 1
        except Exception:
            continue
    
    # Ortalama günlük sipariş (son 30 gün için)
    avg_daily_orders = sum(daily_orders_last30.values()) / len(daily_orders_last30) if daily_orders_last30 else 0
    
    # Trend analizi (son 7 gün vs önceki 7 gün)
    sorted_days = sorted(daily_orders_last30.keys())
    if len(sorted_days) >= 14:
        recent_7_days = sorted_days[-7:]
        previous_7_days = sorted_days[-14:-7]
        
        recent_avg = sum(daily_orders_last30[d] for d in recent_7_days) / 7
        previous_avg = sum(daily_orders_last30[d] for d in previous_7_days) / 7
        
        trend_change = ((recent_avg - previous_avg) / previous_avg * 100) if previous_avg > 0 else 0
        
        if trend_change > 10:
            trend = "increasing"
        elif trend_change < -10:
            trend = "decreasing"
        else:
            trend = "stable"
    else:
        trend = "stable"
        trend_change = 0
    
    # 7 günlük tahmin
    predicted_orders = int(avg_daily_orders * 7)
    
    # Güven seviyesi (daha fazla veri = daha yüksek güven)
    confidence = min(0.95, 0.5 + (len(daily_orders_last30) / 30) * 0.45)
    
    factors = []
    if trend == "increasing":
        factors.append("Son dönemde sipariş artışı gözlemlendi")
    elif trend == "decreasing":
        factors.append("Son dönemde sipariş azalışı gözlemlendi")
    else:
        factors.append("Sipariş trendi stabil")
    
    factors.append(f"Ortalama günlük sipariş: {avg_daily_orders:.1f}")
    
    # Debug bilgisi ekle
    debug_info = {
        "total_orders": len(orders),
        "daily_orders_count": len(daily_orders_all),
        "daily_trend_count": len(daily_trend),
        "sample_dates": list(daily_orders_all.keys())[:5] if daily_orders_all else [],
        "sample_trend": daily_trend[:3] if daily_trend else []
    }
    
    return {
        "predicted_orders": predicted_orders,
        "confidence": round(confidence, 2),
        "timeframe": "7 gün",
        "factors": factors,
        "trend": trend,
        "average_daily_orders": round(avg_daily_orders, 1),
        "trend_change_percent": round(trend_change, 1),
        "daily_trend": daily_trend,  # Günlük trend verileri (zaten son 30 gün için hesaplandı)
        "debug_info": debug_info  # Debug bilgisi
    }


@router.get("/customer-behavior")
async def get_customer_behavior(store: Store = Depends(get_current_store), db: Session = Depends(get_db)):
    """
    Müşteri davranış analizi yapar.
    Tekrar satın alma oranı, müşteri segmentasyonu vb.
    """
    creds = resolve_trendyol_creds(db, store)
    orders = get_trendyol_orders_data(creds)
    
    if not orders:
        return {
            "repeat_customer_rate": 0.0,
            "average_order_frequency": 0.0,
            "customer_segments": {},
            "top_customers": [],
            "purchase_patterns": {},
            "message": "Analiz için yeterli veri yok"
        }
    
    # Müşteri ID'lerini topla
    customer_orders = defaultdict(list)
    for order in orders:
        customer_id = order.get("customerId") or order.get("customer_id") or order.get("id")
        if customer_id:
            customer_orders[str(customer_id)].append(order)
    
    total_customers = len(customer_orders)
    repeat_customers = len([c for c in customer_orders.values() if len(c) > 1])
    
    repeat_customer_rate = (repeat_customers / total_customers * 100) if total_customers > 0 else 0
    
    # Ortalama sipariş sıklığı
    order_counts = [len(orders) for orders in customer_orders.values()]
    average_order_frequency = sum(order_counts) / len(order_counts) if order_counts else 0
    
    # Müşteri segmentasyonu
    customer_segments = {
        "yeni_musteri": len([c for c in customer_orders.values() if len(c) == 1]),
        "tekrar_musteri": len([c for c in customer_orders.values() if 2 <= len(c) <= 4]),
        "sadik_musteri": len([c for c in customer_orders.values() if len(c) >= 5])
    }
    
    # En çok sipariş veren müşteriler
    top_customers = []
    for customer_id, customer_order_list in customer_orders.items():
        total_value = 0
        for order in customer_order_list:
            total_price = order.get("totalPrice") or order.get("totalPriceValue") or 0
            if isinstance(total_price, str):
                try:
                    total_price = float(total_price.replace(",", "."))
                except:
                    total_price = 0
            total_value += float(total_price) if total_price else 0
        
        top_customers.append({
            "customer_id": customer_id,
            "order_count": len(customer_order_list),
            "total_value": round(total_value, 2)
        })
    
    top_customers = sorted(top_customers, key=lambda x: x["total_value"], reverse=True)[:10]
    
    # Satın alma kalıpları
    # Haftanın günü analizi
    weekday_orders = defaultdict(int)
    for order in orders:
        try:
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
                weekday = order_date.strftime("%A")
                weekday_orders[weekday] += 1
        except Exception:
            continue
    
    purchase_patterns = {
        "most_active_day": max(weekday_orders.items(), key=lambda x: x[1])[0] if weekday_orders else "N/A",
        "weekday_distribution": dict(weekday_orders)
    }
    
    return {
        "repeat_customer_rate": round(repeat_customer_rate, 2),
        "average_order_frequency": round(average_order_frequency, 2),
        "customer_segments": customer_segments,
        "top_customers": top_customers,
        "purchase_patterns": purchase_patterns,
        "total_customers": total_customers
    }


@router.get("/financial-stats")
async def get_financial_stats(period: str = "all", store: Store = Depends(get_current_store), db: Session = Depends(get_db)):
    """
    Finansal istatistikleri döner:
    - Bankaya yatan tutarlar (teslim edilmiş siparişler)
    - Yatacak tutarlar (faturalanmış ama henüz teslim edilmemiş)
    - Kargo teslimi sonrası yatacak tutarlar
    
    Args:
        period: Zaman dilimi filtresi
            - "all": Tüm siparişler (varsayılan)
            - "30days": Son 30 gün
            - "7days": Son 7 gün
            - "1month": Son 1 ay (30 gün)
    """
    creds = resolve_trendyol_creds(db, store)
    orders = get_trendyol_orders_data(creds)
    
    if not orders:
        return {
            "deposited_amount": 0.0,
            "pending_amount": 0.0,
            "after_delivery_amount": 0.0,
            "total_revenue": 0.0,
            "message": "Analiz için yeterli veri yok",
            "period": period
        }
    
    # Zaman filtresi uygula
    if period != "all":
        from datetime import timezone
        today = datetime.now(timezone.utc) if hasattr(datetime.now(), 'astimezone') else datetime.now()
        days = 30
        if period == "7days":
            days = 7
        elif period == "15days":
            days = 15
        elif period == "30days" or period == "1month":
            days = 30
        
        cutoff_date = today - timedelta(days=days)
        # Timezone bilgisi olmadan karşılaştırma için naive datetime'a çevir
        if cutoff_date.tzinfo:
            cutoff_date = cutoff_date.replace(tzinfo=None)
        
        filtered_orders = []
        
        for order in orders:
            try:
                order_date_str = order.get("orderDate") or order.get("order_date") or order.get("orderDateValue")
                if not order_date_str:
                    continue
                
                order_date = None
                if isinstance(order_date_str, str):
                    if 'T' in order_date_str:
                        try:
                            date_str_clean = order_date_str.replace('Z', '+00:00')
                            order_date = datetime.fromisoformat(date_str_clean)
                            if order_date.tzinfo:
                                order_date = order_date.replace(tzinfo=None)
                        except:
                            try:
                                order_date = datetime.strptime(order_date_str, "%Y-%m-%d %H:%M:%S")
                            except:
                                order_date = datetime.strptime(order_date_str.split('T')[0], "%Y-%m-%d")
                    else:
                        order_date = datetime.strptime(order_date_str, "%Y-%m-%d")
                elif isinstance(order_date_str, (int, float)):
                    _ts = float(order_date_str)
                    if _ts > 1e12:
                        _ts = _ts / 1000
                    order_date = datetime.fromtimestamp(_ts)
                    if order_date.tzinfo:
                        order_date = order_date.replace(tzinfo=None)
                else:
                    continue
                
                if order_date and order_date >= cutoff_date:
                    filtered_orders.append(order)
            except Exception:
                continue
        
        orders = filtered_orders
    
    # Sipariş durumlarına göre kategorize et
    deposited_amount = 0.0  # Bankaya yatan (teslim edilmiş)
    pending_amount = 0.0  # Yatacak (faturalanmış ama henüz teslim edilmemiş)
    after_delivery_amount = 0.0  # Kargo teslimi sonrası yatacak
    total_revenue = 0.0
    
    # Teslim edilmiş sipariş durumları
    delivered_statuses = ["Shipped", "Delivered", "Completed", "Closed"]
    # Faturalanmış ama henüz teslim edilmemiş
    invoiced_statuses = ["Invoiced", "Picking", "ReadyToShip"]
    # Henüz faturalanmamış
    pending_statuses = ["Created", "Pending"]
    
    for order in orders:
        try:
            status = order.get("status") or order.get("orderStatus") or ""
            total_price = order.get("totalPrice") or order.get("totalPriceValue") or order.get("totalAmount") or 0.0
            
            if isinstance(total_price, str):
                try:
                    total_price = float(total_price.replace(",", "."))
                except:
                    total_price = 0.0
            
            total_price = float(total_price) if total_price else 0.0
            total_revenue += total_price
            
            if status in delivered_statuses:
                # Teslim edilmiş - bankaya yatan
                deposited_amount += total_price
            elif status in invoiced_statuses:
                # Faturalanmış ama henüz teslim edilmemiş - yatacak
                pending_amount += total_price
            elif status in pending_statuses:
                # Henüz faturalanmamış - kargo teslimi sonrası yatacak
                after_delivery_amount += total_price
        except Exception:
            continue
    
    period_label = {
        "all": "Tüm Zamanlar",
        "30days": "Son 30 Gün",
        "1month": "Son 1 Ay",
        "7days": "Son 7 Gün",
        "15days": "Son 15 Gün"
    }.get(period, period)
    
    return {
        "deposited_amount": round(deposited_amount, 2),
        "pending_amount": round(pending_amount, 2),
        "after_delivery_amount": round(after_delivery_amount, 2),
        "total_revenue": round(total_revenue, 2),
        "period": period,
        "period_label": period_label,
        "breakdown": {
            "delivered_orders": len([o for o in orders if (o.get("status") or o.get("orderStatus") or "") in delivered_statuses]),
            "invoiced_orders": len([o for o in orders if (o.get("status") or o.get("orderStatus") or "") in invoiced_statuses]),
            "pending_orders": len([o for o in orders if (o.get("status") or o.get("orderStatus") or "") in pending_statuses])
        }
    }


@router.get("/period-comparison")
async def get_period_comparison(store: Store = Depends(get_current_store), db: Session = Depends(get_db)):
    """
    Bu hafta vs geçen hafta karşılaştırması yapar.
    """
    creds = resolve_trendyol_creds(db, store)
    orders = get_trendyol_orders_data(creds)
    
    if not orders:
        return {
            "this_week": {},
            "last_week": {},
            "comparison": {},
            "message": "Analiz için yeterli veri yok"
        }
    
    today = datetime.now()
    # Bu haftanın başlangıcı (Pazartesi)
    days_since_monday = today.weekday()
    this_week_start = today - timedelta(days=days_since_monday)
    this_week_start = this_week_start.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Geçen haftanın başlangıcı ve bitişi
    last_week_start = this_week_start - timedelta(days=7)
    last_week_end = this_week_start
    
    # Bu hafta ve geçen hafta siparişlerini filtrele
    this_week_orders = []
    last_week_orders = []
    
    for order in orders:
        try:
            order_date_str = order.get("orderDate") or order.get("order_date") or order.get("orderDateValue")
            if not order_date_str:
                continue
            
            # Tarih parse et
            order_date = None
            if isinstance(order_date_str, str):
                if 'T' in order_date_str:
                    try:
                        date_str_clean = order_date_str.replace('Z', '+00:00')
                        order_date = datetime.fromisoformat(date_str_clean)
                        if order_date.tzinfo:
                            order_date = order_date.replace(tzinfo=None)
                    except:
                        try:
                            order_date = datetime.strptime(order_date_str, "%Y-%m-%d %H:%M:%S")
                        except:
                            order_date = datetime.strptime(order_date_str.split('T')[0], "%Y-%m-%d")
                else:
                    order_date = datetime.strptime(order_date_str, "%Y-%m-%d")
            elif isinstance(order_date_str, (int, float)):
                _ts = float(order_date_str)
                if _ts > 1e12:
                    _ts = _ts / 1000
                order_date = datetime.fromtimestamp(_ts)
                if order_date.tzinfo:
                    order_date = order_date.replace(tzinfo=None)
            else:
                continue
            
            if not order_date:
                continue
            
            # Bu hafta mı geçen hafta mı?
            if order_date >= this_week_start:
                this_week_orders.append(order)
            elif last_week_start <= order_date < last_week_end:
                last_week_orders.append(order)
        except Exception:
            continue
    
    # Bu hafta istatistikleri
    this_week_stats = {
        "total_orders": len(this_week_orders),
        "total_revenue": 0.0,
        "average_order_value": 0.0
    }
    
    for order in this_week_orders:
        total_price = order.get("totalPrice") or order.get("totalPriceValue") or order.get("totalAmount") or 0.0
        if isinstance(total_price, str):
            try:
                total_price = float(total_price.replace(",", "."))
            except:
                total_price = 0.0
        this_week_stats["total_revenue"] += float(total_price) if total_price else 0.0
    
    if this_week_stats["total_orders"] > 0:
        this_week_stats["average_order_value"] = this_week_stats["total_revenue"] / this_week_stats["total_orders"]
    
    this_week_stats["total_revenue"] = round(this_week_stats["total_revenue"], 2)
    this_week_stats["average_order_value"] = round(this_week_stats["average_order_value"], 2)
    
    # Geçen hafta istatistikleri
    last_week_stats = {
        "total_orders": len(last_week_orders),
        "total_revenue": 0.0,
        "average_order_value": 0.0
    }
    
    for order in last_week_orders:
        total_price = order.get("totalPrice") or order.get("totalPriceValue") or order.get("totalAmount") or 0.0
        if isinstance(total_price, str):
            try:
                total_price = float(total_price.replace(",", "."))
            except:
                total_price = 0.0
        last_week_stats["total_revenue"] += float(total_price) if total_price else 0.0
    
    if last_week_stats["total_orders"] > 0:
        last_week_stats["average_order_value"] = last_week_stats["total_revenue"] / last_week_stats["total_orders"]
    
    last_week_stats["total_revenue"] = round(last_week_stats["total_revenue"], 2)
    last_week_stats["average_order_value"] = round(last_week_stats["average_order_value"], 2)
    
    # Karşılaştırma
    comparison = {}
    if last_week_stats["total_orders"] > 0:
        comparison["orders_change"] = round(((this_week_stats["total_orders"] - last_week_stats["total_orders"]) / last_week_stats["total_orders"]) * 100, 1)
    else:
        comparison["orders_change"] = 100.0 if this_week_stats["total_orders"] > 0 else 0.0
    
    if last_week_stats["total_revenue"] > 0:
        comparison["revenue_change"] = round(((this_week_stats["total_revenue"] - last_week_stats["total_revenue"]) / last_week_stats["total_revenue"]) * 100, 1)
    else:
        comparison["revenue_change"] = 100.0 if this_week_stats["total_revenue"] > 0 else 0.0
    
    if last_week_stats["average_order_value"] > 0:
        comparison["avg_order_value_change"] = round(((this_week_stats["average_order_value"] - last_week_stats["average_order_value"]) / last_week_stats["average_order_value"]) * 100, 1)
    else:
        comparison["avg_order_value_change"] = 0.0
    
    return {
        "this_week": this_week_stats,
        "last_week": last_week_stats,
        "comparison": comparison
    }


@router.get("/revenue-trend")
async def get_revenue_trend(days: int = 30, store: Store = Depends(get_current_store), db: Session = Depends(get_db)):
    """
    Günlük gelir trendi verilerini döner.
    """
    creds = resolve_trendyol_creds(db, store)
    orders = get_trendyol_orders_data(creds)
    
    if not orders:
        return {
            "daily_revenue": [],
            "weekly_revenue": [],
            "message": "Analiz için yeterli veri yok"
        }
    
    # Günlük gelir hesapla
    daily_revenue = defaultdict(float)
    today = datetime.now()
    
    for order in orders:
        try:
            order_date_str = order.get("orderDate") or order.get("order_date") or order.get("orderDateValue")
            if not order_date_str:
                continue
            
            # Tarih parse et
            order_date = None
            if isinstance(order_date_str, str):
                if 'T' in order_date_str:
                    try:
                        date_str_clean = order_date_str.replace('Z', '+00:00')
                        order_date = datetime.fromisoformat(date_str_clean)
                        if order_date.tzinfo:
                            order_date = order_date.replace(tzinfo=None)
                    except:
                        try:
                            order_date = datetime.strptime(order_date_str, "%Y-%m-%d %H:%M:%S")
                        except:
                            order_date = datetime.strptime(order_date_str.split('T')[0], "%Y-%m-%d")
                else:
                    order_date = datetime.strptime(order_date_str, "%Y-%m-%d")
            elif isinstance(order_date_str, (int, float)):
                _ts = float(order_date_str)
                if _ts > 1e12:
                    _ts = _ts / 1000
                order_date = datetime.fromtimestamp(_ts)
                if order_date.tzinfo:
                    order_date = order_date.replace(tzinfo=None)
            else:
                continue
            
            if not order_date:
                continue
            
            # Son N gün içinde mi kontrol et
            days_diff = (today - order_date).days
            if days_diff > days or days_diff < 0:
                continue
            
            # Gelir hesapla
            total_price = order.get("totalPrice") or order.get("totalPriceValue") or order.get("totalAmount") or 0.0
            if isinstance(total_price, str):
                try:
                    total_price = float(total_price.replace(",", "."))
                except:
                    total_price = 0.0
            
            day_key = order_date.strftime("%Y-%m-%d")
            daily_revenue[day_key] += float(total_price) if total_price else 0.0
        except Exception:
            continue
    
    # Günlük trend verilerini hazırla
    daily_trend = []
    day_names_tr = {
        'Mon': 'Pzt', 'Tue': 'Sal', 'Wed': 'Çar', 'Thu': 'Per',
        'Fri': 'Cum', 'Sat': 'Cmt', 'Sun': 'Paz'
    }
    
    # Son N günün tarihlerini oluştur
    for i in range(days - 1, -1, -1):
        day_date = today - timedelta(days=i)
        day_key = day_date.strftime("%Y-%m-%d")
        day_name_en = day_date.strftime("%a")
        
        daily_trend.append({
            "date": day_key,
            "revenue": round(daily_revenue.get(day_key, 0.0), 2),
            "day_name": day_names_tr.get(day_name_en, day_name_en)
        })
    
    # Haftalık trend hesapla (son 8 hafta)
    weekly_revenue = defaultdict(float)
    for day_data in daily_trend:
        try:
            day_date = datetime.strptime(day_data["date"], "%Y-%m-%d")
            # ISO hafta numarası ve yıl
            year, week_num, _ = day_date.isocalendar()
            week_key = f"{year}-W{week_num:02d}"
            weekly_revenue[week_key] += day_data["revenue"]
        except:
            continue
    
    # Haftalık trend verilerini hazırla
    weekly_trend = []
    sorted_weeks = sorted(weekly_revenue.keys())
    for week_key in sorted_weeks[-8:]:  # Son 8 hafta
        weekly_trend.append({
            "week": week_key,
            "revenue": round(weekly_revenue[week_key], 2)
        })
    
    return {
        "daily_revenue": daily_trend,
        "weekly_revenue": weekly_trend,
        "total_revenue": round(sum(daily_revenue.values()), 2),
        "average_daily_revenue": round(sum(daily_revenue.values()) / len(daily_trend) if daily_trend else 0, 2)
    }


@router.get("/top-products")
async def get_top_products(limit: int = 10, store: Store = Depends(get_current_store), db: Session = Depends(get_db)):
    """
    En çok satan ürünleri döner.
    """
    creds = resolve_trendyol_creds(db, store)
    orders = get_trendyol_orders_data(creds)
    
    if not orders:
        return {
            "products": [],
            "message": "Analiz için yeterli veri yok"
        }
    
    # Ürün bazlı satış analizi
    product_sales = defaultdict(lambda: {"count": 0, "total_revenue": 0, "orders": []})
    
    for order in orders:
        lines = order.get("lines", []) or order.get("orderLines", []) or []
        for line in lines:
            product_id = line.get("productId") or line.get("product_id") or line.get("barcode") or ""
            product_name = line.get("productName") or line.get("product_name") or line.get("name") or "Bilinmeyen Ürün"
            quantity = line.get("quantity", 1)
            price = line.get("price", 0) or line.get("salePrice", 0) or line.get("unitPrice", 0)
            
            if isinstance(price, str):
                try:
                    price = float(price.replace(",", "."))
                except:
                    price = 0
            
            if product_id:
                product_sales[str(product_id)]["count"] += quantity
                product_sales[str(product_id)]["total_revenue"] += price * quantity
                product_sales[str(product_id)]["orders"].append({
                    "price": price,
                    "quantity": quantity
                })
                if "name" not in product_sales[str(product_id)]:
                    product_sales[str(product_id)]["name"] = product_name
    
    # En çok satan ürünleri bul (satış adedine göre)
    top_products = sorted(
        product_sales.items(),
        key=lambda x: x[1]["count"],
        reverse=True
    )[:limit]
    
    products = []
    for product_id, data in top_products:
        avg_price = data["total_revenue"] / data["count"] if data["count"] > 0 else 0
        products.append({
            "product_id": product_id,
            "product_name": data.get("name", "Bilinmeyen Ürün"),
            "sales_count": data["count"],
            "total_revenue": round(data["total_revenue"], 2),
            "average_price": round(avg_price, 2)
        })
    
    return {
        "products": products,
        "total_products": len(product_sales)
    }


@router.get("/price-optimization")
async def get_price_optimization(store: Store = Depends(get_current_store), db: Session = Depends(get_db)):
    """
    Fiyat optimizasyonu önerileri sunar.
    En çok satan ürünler için fiyat analizi yapar.
    """
    creds = resolve_trendyol_creds(db, store)
    orders = get_trendyol_orders_data(creds)
    
    if not orders:
        return {
            "recommendations": [],
            "message": "Analiz için yeterli veri yok"
        }
    
    # Ürün bazlı satış analizi
    product_sales = defaultdict(lambda: {"count": 0, "total_revenue": 0, "orders": []})
    
    for order in orders:
        lines = order.get("lines", [])
        for line in lines:
            product_id = line.get("productId") or line.get("product_id") or ""
            product_name = line.get("productName") or line.get("product_name") or "Bilinmeyen Ürün"
            quantity = line.get("quantity", 1)
            price = line.get("price", 0)
            
            if isinstance(price, str):
                try:
                    price = float(price.replace(",", "."))
                except:
                    price = 0
            
            if product_id:
                product_sales[str(product_id)]["count"] += quantity
                product_sales[str(product_id)]["total_revenue"] += price * quantity
                product_sales[str(product_id)]["orders"].append({
                    "price": price,
                    "quantity": quantity
                })
                if "name" not in product_sales[str(product_id)]:
                    product_sales[str(product_id)]["name"] = product_name
    
    # En çok satan ürünleri bul
    top_products = sorted(
        product_sales.items(),
        key=lambda x: x[1]["count"],
        reverse=True
    )[:5]
    
    recommendations = []
    
    for product_id, data in top_products:
        if data["count"] < 3:  # En az 3 satış olmalı
            continue
        
        orders_list = data["orders"]
        prices = [o["price"] for o in orders_list]
        
        if not prices:
            continue
        
        current_price = prices[-1]  # Son satış fiyatı
        avg_price = sum(prices) / len(prices)
        min_price = min(prices)
        max_price = max(prices)
        
        # Basit optimizasyon önerisi
        # Eğer fiyat ortalamanın altındaysa artırılabilir
        if current_price < avg_price * 0.9:
            recommended_price = avg_price * 0.95
            expected_increase = 5.0
            reasoning = f"Fiyat ortalamanın altında. Küçük bir artış satış hacmini koruyabilir."
            risk_level = "low"
        elif current_price > avg_price * 1.1:
            recommended_price = avg_price * 1.05
            expected_increase = -2.0
            reasoning = f"Fiyat ortalamanın üstünde. Küçük bir indirim satış hacmini artırabilir."
            risk_level = "medium"
        else:
            # Altın oran fiyatı öner
            golden_price = min_price + (max_price - min_price) / 1.618
            recommended_price = golden_price
            expected_increase = 3.0
            reasoning = f"Altın oran fiyatı psikolojik olarak daha çekici olabilir."
            risk_level = "low"
        
        recommendations.append({
            "product_id": product_id,
            "product_name": data.get("name", "Bilinmeyen Ürün"),
            "current_price": round(current_price, 2),
            "recommended_price": round(recommended_price, 2),
            "expected_increase": round(expected_increase, 1),
            "reasoning": reasoning,
            "risk_level": risk_level,
            "sales_count": data["count"],
            "average_price": round(avg_price, 2)
        })
    
    return {
        "recommendations": recommendations,
        "total_products_analyzed": len(product_sales)
    }

