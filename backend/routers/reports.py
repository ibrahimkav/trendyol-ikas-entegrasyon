"""
Raporlama Router
Günlük/haftalık/aylık raporlar ve PDF/Excel export
"""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from collections import defaultdict
from sqlalchemy.orm import Session
import io
import csv

router = APIRouter()

# Database modülünü optional olarak yükle (ghost mode)
try:
    from database.db import get_db
    from database.models import Store
    from security import get_current_store
    from utils.store_trendyol import resolve_trendyol_creds, fetch_orders as _fetch_store_orders
    _db_available = True
except Exception:
    _db_available = False
    def get_db():
        raise HTTPException(status_code=503, detail="Database not available (ghost mode)")

    def get_current_store():
        raise HTTPException(status_code=503, detail="Database not available (ghost mode)")


def get_trendyol_orders_data(creds=None) -> List[Dict]:
    """Bu mağazanın Trendyol siparişlerini çeker (Wave3 kalıbı: per-store, env DEĞİL).
    NOT: creds=None → [] (henüz dönüştürülmemiş çağıranlar için güvenli köprü)."""
    if creds is None:
        return []
    try:
        return _fetch_store_orders(creds, max_pages=500, size=200)
    except Exception:
        return []


def parse_order_date(order_date_str):
    """Sipariş tarihini parse eder (orders.py ile aynı mantık)"""
    if not order_date_str:
        return None
    
    try:
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
                            return None
            else:
                # Sadece tarih formatı: 2024-01-15
                try:
                    order_date = datetime.strptime(order_date_str, "%Y-%m-%d")
                except:
                    # Timestamp string olabilir
                    try:
                        timestamp = float(order_date_str)
                        # Milisaniye cinsinden mi kontrol et (13+ haneli)
                        if timestamp > 1e12:  # Milisaniye cinsinden
                            timestamp = timestamp / 1000
                        order_date = datetime.fromtimestamp(timestamp)
                        if order_date.tzinfo:
                            order_date = order_date.replace(tzinfo=None)
                    except:
                        return None
        elif isinstance(order_date_str, (int, float)):
            # Timestamp formatı - milisaniye cinsinden mi kontrol et
            timestamp = float(order_date_str)
            # 13+ haneli sayılar milisaniye cinsinden timestamp'tir
            if timestamp > 1e12:  # Milisaniye cinsinden (1e12 = 1 trilyon = 2001-09-09)
                timestamp = timestamp / 1000
            order_date = datetime.fromtimestamp(timestamp)
            if order_date.tzinfo:
                order_date = order_date.replace(tzinfo=None)
        else:
            return None
        return order_date
    except Exception as e:
        return None


@router.get("/daily")
async def get_daily_report(
    date: Optional[str] = None,
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Session = Depends(get_db) if _db_available else None
):
    """
    Günlük rapor döner.
    date formatı: YYYY-MM-DD (varsayılan: bugün)
    """
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")
    
    try:
        target_date = datetime.strptime(date, "%Y-%m-%d")
    except:
        raise HTTPException(status_code=400, detail="Geçersiz tarih formatı. YYYY-MM-DD formatında olmalı.")
    
    creds = resolve_trendyol_creds(db, store)
    orders = get_trendyol_orders_data(creds)
    
    # O güne ait siparişleri filtrele
    daily_orders = []
    total_revenue = 0.0
    total_quantity = 0
    
    for order in orders:
        # Farklı tarih alanlarını kontrol et
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
            continue
        
        order_date = parse_order_date(order_date_str)
        if order_date and order_date.date() == target_date.date():
            daily_orders.append(order)
            
            total_price = order.get("totalPrice") or order.get("totalPriceValue") or order.get("totalAmount") or 0.0
            if isinstance(total_price, str):
                try:
                    total_price = float(total_price.replace(",", "."))
                except:
                    total_price = 0.0
            total_revenue += float(total_price) if total_price else 0.0
            
            # Ürün sayısını hesapla
            lines = order.get("lines", []) or order.get("orderLines", []) or order.get("items", []) or []
            if isinstance(lines, dict):
                lines = [lines]
            for line in lines:
                quantity = line.get("quantity", 1) or line.get("qty", 1) or 1
                total_quantity += quantity
    
    return {
        "date": date,
        "total_orders": len(daily_orders),
        "total_revenue": round(total_revenue, 2),
        "total_quantity": total_quantity,
        "average_order_value": round(total_revenue / len(daily_orders), 2) if daily_orders else 0.0,
        "orders": daily_orders[:100]  # İlk 100 sipariş
    }


@router.get("/weekly")
async def get_weekly_report(
    week_start: Optional[str] = None,
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Session = Depends(get_db) if _db_available else None
):
    """
    Haftalık rapor döner.
    week_start formatı: YYYY-MM-DD (varsayılan: bu haftanın pazartesi)
    """
    if week_start:
        try:
            start_date = datetime.strptime(week_start, "%Y-%m-%d")
        except:
            raise HTTPException(status_code=400, detail="Geçersiz tarih formatı.")
    else:
        today = datetime.now()
        days_since_monday = today.weekday()
        start_date = today - timedelta(days=days_since_monday)
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
    
    end_date = start_date + timedelta(days=6)
    
    creds = resolve_trendyol_creds(db, store)
    orders = get_trendyol_orders_data(creds)
    
    # Haftaya ait siparişleri filtrele
    weekly_orders = []
    daily_stats = defaultdict(lambda: {"orders": 0, "revenue": 0.0, "quantity": 0})
    total_revenue = 0.0
    total_quantity = 0
    
    for order in orders:
        # Farklı tarih alanlarını kontrol et
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
            continue
        
        order_date = parse_order_date(order_date_str)
        if order_date and start_date.date() <= order_date.date() <= end_date.date():
            weekly_orders.append(order)
            
            day_key = order_date.strftime("%Y-%m-%d")
            daily_stats[day_key]["orders"] += 1
            
            total_price = order.get("totalPrice") or order.get("totalPriceValue") or order.get("totalAmount") or 0.0
            if isinstance(total_price, str):
                try:
                    total_price = float(total_price.replace(",", "."))
                except:
                    total_price = 0.0
            total_revenue += float(total_price) if total_price else 0.0
            daily_stats[day_key]["revenue"] += float(total_price) if total_price else 0.0
            
            # Ürün sayısını hesapla
            lines = order.get("lines", []) or order.get("orderLines", []) or order.get("items", []) or []
            if isinstance(lines, dict):
                lines = [lines]
            for line in lines:
                quantity = line.get("quantity", 1) or line.get("qty", 1) or 1
                total_quantity += quantity
                daily_stats[day_key]["quantity"] += quantity
    
    # Günlük istatistikleri sırala
    daily_stats_list = [
        {"date": date, **stats}
        for date, stats in sorted(daily_stats.items())
    ]
    
    return {
        "week_start": start_date.strftime("%Y-%m-%d"),
        "week_end": end_date.strftime("%Y-%m-%d"),
        "total_orders": len(weekly_orders),
        "total_revenue": round(total_revenue, 2),
        "total_quantity": total_quantity,
        "average_order_value": round(total_revenue / len(weekly_orders), 2) if weekly_orders else 0.0,
        "daily_stats": daily_stats_list,
        "orders": weekly_orders[:200]  # İlk 200 sipariş
    }


@router.get("/monthly")
async def get_monthly_report(
    year: Optional[int] = None,
    month: Optional[int] = None,
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Session = Depends(get_db) if _db_available else None
):
    """
    Aylık rapor döner.
    year ve month belirtilmezse bu ay kullanılır.
    """
    if year and month:
        try:
            start_date = datetime(year, month, 1)
        except:
            raise HTTPException(status_code=400, detail="Geçersiz yıl/ay değerleri.")
    else:
        today = datetime.now()
        start_date = datetime(today.year, today.month, 1)
    
    # Ayın son günü
    if start_date.month == 12:
        end_date = datetime(start_date.year + 1, 1, 1) - timedelta(days=1)
    else:
        end_date = datetime(start_date.year, start_date.month + 1, 1) - timedelta(days=1)
    
    creds = resolve_trendyol_creds(db, store)
    orders = get_trendyol_orders_data(creds)
    print(f"[Reports/Monthly] Filtre: {start_date.date()} - {end_date.date()}, Toplam sipariş: {len(orders)}")
    
    # Aya ait siparişleri filtrele
    monthly_orders = []
    daily_stats = defaultdict(lambda: {"orders": 0, "revenue": 0.0, "quantity": 0})
    total_revenue = 0.0
    total_quantity = 0
    parse_errors = 0
    filtered_out = 0
    
    for order in orders:
        # Farklı tarih alanlarını kontrol et (daha kapsamlı)
        order_date_str = (
            order.get("orderDate") or 
            order.get("order_date") or 
            order.get("orderDateValue") or
            order.get("packageDate") or
            order.get("shipmentPackageStatusDate") or
            order.get("createDate") or
            order.get("createdDate") or
            order.get("orderDateValue") or
            order.get("orderDateTimestamp") or
            order.get("orderDateTimestampValue") or
            order.get("orderDateLong") or
            order.get("orderDateLongValue")
        )
        
        # Eğer hala bulunamadıysa, tüm alanları kontrol et
        if not order_date_str:
            # Önce tüm anahtarları listele
            all_keys = list(order.keys())
            # Tarih içeren alanları bul
            date_keys = [k for k in all_keys if any(word in k.lower() for word in ['date', 'time', 'timestamp', 'created', 'order'])]
            
            # Bu alanları kontrol et
            for key in date_keys:
                value = order.get(key)
                if value:
                    order_date_str = value
                    if parse_errors <= 1:  # İlk hata için debug
                        print(f"[Reports/Monthly] Tarih alanı bulundu: {key} = {value} (type: {type(value)})")
                    break
            
            # Hala bulunamadıysa, tüm sayısal değerleri kontrol et (timestamp olabilir)
            if not order_date_str:
                for key, value in order.items():
                    if isinstance(value, (int, float)) and value > 1e10:  # Büyük sayılar timestamp olabilir
                        # Timestamp kontrolü: 2000-01-01'den sonra olmalı
                        test_date = datetime.fromtimestamp(value / 1000 if value > 1e12 else value)
                        if test_date.year >= 2000 and test_date.year <= 2100:
                            order_date_str = value
                            if parse_errors <= 1:
                                print(f"[Reports/Monthly] Timestamp bulundu: {key} = {value}")
                            break
        
        if not order_date_str:
            parse_errors += 1
            if parse_errors <= 3:  # İlk 3 hata için debug
                print(f"[Reports/Monthly] Tarih alanı bulunamadı. Order keys: {list(order.keys())[:20]}")
            continue
        
        order_date = parse_order_date(order_date_str)
        
        if not order_date:
            parse_errors += 1
            if parse_errors <= 3:  # İlk 3 hata için debug
                print(f"[Reports/Monthly] Parse hatası: {order_date_str} (type: {type(order_date_str)}, order keys: {list(order.keys())[:10]})")
            continue
        
        # Tarih filtresini uygula
        if start_date.date() <= order_date.date() <= end_date.date():
            monthly_orders.append(order)
            
            day_key = order_date.strftime("%Y-%m-%d")
            daily_stats[day_key]["orders"] += 1
            
            total_price = order.get("totalPrice") or order.get("totalPriceValue") or order.get("totalAmount") or 0.0
            if isinstance(total_price, str):
                try:
                    total_price = float(total_price.replace(",", "."))
                except:
                    total_price = 0.0
            total_revenue += float(total_price) if total_price else 0.0
            daily_stats[day_key]["revenue"] += float(total_price) if total_price else 0.0
            
            # Ürün sayısını hesapla
            lines = order.get("lines", []) or order.get("orderLines", []) or order.get("items", []) or []
            if isinstance(lines, dict):
                lines = [lines]
            for line in lines:
                quantity = line.get("quantity", 1) or line.get("qty", 1) or 1
                total_quantity += quantity
                daily_stats[day_key]["quantity"] += quantity
        else:
            filtered_out += 1
            if filtered_out <= 3:  # İlk 3 filtrelenmiş sipariş için debug
                print(f"[Reports/Monthly] Filtre dışı: {order_date.date()} (aralık: {start_date.date()} - {end_date.date()})")
    
    print(f"[Reports/Monthly] Sonuç: {len(monthly_orders)} sipariş bulundu, {parse_errors} parse hatası, {filtered_out} filtrelendi")
    
    # Günlük istatistikleri sırala
    daily_stats_list = [
        {"date": date, **stats}
        for date, stats in sorted(daily_stats.items())
    ]
    
    return {
        "year": start_date.year,
        "month": start_date.month,
        "month_name": start_date.strftime("%B"),
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
        "total_orders": len(monthly_orders),
        "total_revenue": round(total_revenue, 2),
        "total_quantity": total_quantity,
        "average_order_value": round(total_revenue / len(monthly_orders), 2) if monthly_orders else 0.0,
        "average_daily_revenue": round(total_revenue / len(daily_stats), 2) if daily_stats else 0.0,
        "daily_stats": daily_stats_list,
        "orders": monthly_orders[:500]  # İlk 500 sipariş
    }


@router.get("/yearly")
async def get_yearly_report(
    year: Optional[int] = None,
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Session = Depends(get_db) if _db_available else None
):
    """
    Yıllık rapor döner.
    year belirtilmezse bu yıl kullanılır.
    """
    if not year:
        year = datetime.now().year
    
    start_date = datetime(year, 1, 1)
    end_date = datetime(year, 12, 31)
    
    creds = resolve_trendyol_creds(db, store)
    orders = get_trendyol_orders_data(creds)
    print(f"[Reports/Yearly] Filtre: {start_date.date()} - {end_date.date()}, Toplam sipariş: {len(orders)}")
    
    # Yıla ait siparişleri filtrele
    yearly_orders = []
    monthly_stats = defaultdict(lambda: {"orders": 0, "revenue": 0.0, "quantity": 0})
    daily_stats = defaultdict(lambda: {"orders": 0, "revenue": 0.0, "quantity": 0})
    total_revenue = 0.0
    total_quantity = 0
    parse_errors = 0
    filtered_out = 0
    
    for order in orders:
        # Farklı tarih alanlarını kontrol et (monthly ile aynı mantık)
        order_date_str = (
            order.get("orderDate") or 
            order.get("order_date") or 
            order.get("orderDateValue") or
            order.get("packageDate") or
            order.get("shipmentPackageStatusDate") or
            order.get("createDate") or
            order.get("createdDate") or
            order.get("orderDateTimestamp") or
            order.get("orderDateTimestampValue") or
            order.get("orderDateLong") or
            order.get("orderDateLongValue")
        )
        
        # Eğer hala bulunamadıysa, tüm alanları kontrol et
        if not order_date_str:
            all_keys = list(order.keys())
            date_keys = [k for k in all_keys if any(word in k.lower() for word in ['date', 'time', 'timestamp', 'created', 'order'])]
            
            for key in date_keys:
                value = order.get(key)
                if value:
                    order_date_str = value
                    break
            
            # Hala bulunamadıysa, timestamp kontrolü
            if not order_date_str:
                for key, value in order.items():
                    if isinstance(value, (int, float)) and value > 1e10:
                        test_date = datetime.fromtimestamp(value / 1000 if value > 1e12 else value)
                        if test_date.year >= 2000 and test_date.year <= 2100:
                            order_date_str = value
                            break
        
        if not order_date_str:
            parse_errors += 1
            continue
        
        order_date = parse_order_date(order_date_str)
        
        if not order_date:
            parse_errors += 1
            continue
        
        # Tarih filtresini uygula
        if start_date.date() <= order_date.date() <= end_date.date():
            yearly_orders.append(order)
            
            month_key = order_date.strftime("%Y-%m")
            day_key = order_date.strftime("%Y-%m-%d")
            
            monthly_stats[month_key]["orders"] += 1
            daily_stats[day_key]["orders"] += 1
            
            total_price = order.get("totalPrice") or order.get("totalPriceValue") or order.get("totalAmount") or 0.0
            if isinstance(total_price, str):
                try:
                    total_price = float(total_price.replace(",", "."))
                except:
                    total_price = 0.0
            total_revenue += float(total_price) if total_price else 0.0
            monthly_stats[month_key]["revenue"] += float(total_price) if total_price else 0.0
            daily_stats[day_key]["revenue"] += float(total_price) if total_price else 0.0
            
            # Ürün sayısını hesapla
            lines = order.get("lines", []) or order.get("orderLines", []) or order.get("items", []) or []
            if isinstance(lines, dict):
                lines = [lines]
            for line in lines:
                quantity = line.get("quantity", 1) or line.get("qty", 1) or 1
                total_quantity += quantity
                monthly_stats[month_key]["quantity"] += quantity
                daily_stats[day_key]["quantity"] += quantity
        else:
            filtered_out += 1
    
    print(f"[Reports/Yearly] Sonuç: {len(yearly_orders)} sipariş bulundu, {parse_errors} parse hatası, {filtered_out} filtrelendi")
    
    # Aylık istatistikleri sırala
    monthly_stats_list = [
        {"month": month, **stats}
        for month, stats in sorted(monthly_stats.items())
    ]
    
    # Günlük istatistikleri sırala (ilk 100 gün)
    daily_stats_list = [
        {"date": date, **stats}
        for date, stats in sorted(daily_stats.items())[:100]
    ]
    
    return {
        "year": year,
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
        "total_orders": len(yearly_orders),
        "total_revenue": round(total_revenue, 2),
        "total_quantity": total_quantity,
        "average_order_value": round(total_revenue / len(yearly_orders), 2) if yearly_orders else 0.0,
        "average_daily_revenue": round(total_revenue / len(daily_stats), 2) if daily_stats else 0.0,
        "average_monthly_revenue": round(total_revenue / len(monthly_stats), 2) if monthly_stats else 0.0,
        "monthly_stats": monthly_stats_list,
        "daily_stats": daily_stats_list,
        "orders": yearly_orders[:1000]  # İlk 1000 sipariş
    }


@router.get("/export/csv")
async def export_csv_report(
    period: str = "monthly",
    date: Optional[str] = None,
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Session = Depends(get_db) if _db_available else None
):
    """
    CSV formatında rapor export eder.
    period: "daily", "weekly", "monthly", "yearly"
    """
    if period == "daily":
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")
        report_data = await get_daily_report(date, store=store, db=db)
        filename = f"gunluk_rapor_{date}.csv"
    elif period == "weekly":
        report_data = await get_weekly_report(date, store=store, db=db)
        filename = f"haftalik_rapor_{report_data['week_start']}.csv"
    elif period == "monthly":
        if date:
            try:
                year, month = map(int, date.split("-"))
                report_data = await get_monthly_report(year, month, store=store, db=db)
            except:
                raise HTTPException(status_code=400, detail="Geçersiz tarih formatı. YYYY-MM formatında olmalı.")
        else:
            report_data = await get_monthly_report(store=store, db=db)
        filename = f"aylik_rapor_{report_data['year']}_{report_data['month']:02d}.csv"
    elif period == "yearly":
        if date:
            try:
                year = int(date)
                report_data = await get_yearly_report(year, store=store, db=db)
            except:
                raise HTTPException(status_code=400, detail="Geçersiz yıl formatı.")
        else:
            report_data = await get_yearly_report(store=store, db=db)
        filename = f"yillik_rapor_{report_data['year']}.csv"
    else:
        raise HTTPException(status_code=400, detail="Geçersiz period. 'daily', 'weekly', 'monthly' veya 'yearly' olmalı.")
    
    # CSV oluştur
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Başlık satırı
    writer.writerow([
        "Sipariş No", "Tarih", "Müşteri", "Durum", "Toplam Tutar", "Ürün Sayısı"
    ])
    
    # Sipariş verileri
    for order in report_data.get("orders", []):
        order_number = order.get("orderNumber") or order.get("id") or ""
        order_date = order.get("orderDate") or order.get("order_date") or ""
        customer_name = (
            (order.get("customerFirstName") or "") + " " + (order.get("customerLastName") or "")
        ).strip() or "Bilinmeyen"
        status = order.get("status") or order.get("orderStatus") or ""
        total_price = order.get("totalPrice") or order.get("totalPriceValue") or order.get("totalAmount") or 0.0
        if isinstance(total_price, str):
            try:
                total_price = float(total_price.replace(",", "."))
            except:
                total_price = 0.0
        
        # Ürün sayısını hesapla
        lines = order.get("lines", []) or order.get("orderLines", []) or order.get("items", []) or []
        if isinstance(lines, dict):
            lines = [lines]
        quantity = sum(line.get("quantity", 1) or line.get("qty", 1) or 1 for line in lines)
        
        writer.writerow([
            order_number,
            order_date,
            customer_name,
            status,
            f"{total_price:.2f}",
            quantity
        ])
    
    # Özet satırları
    writer.writerow([])
    writer.writerow(["ÖZET"])
    writer.writerow(["Toplam Sipariş", report_data.get("total_orders", 0)])
    writer.writerow(["Toplam Gelir", f"{report_data.get('total_revenue', 0):.2f} TL"])
    writer.writerow(["Ortalama Sipariş Değeri", f"{report_data.get('average_order_value', 0):.2f} TL"])
    
    output.seek(0)
    
    return StreamingResponse(
        iter([output.getvalue().encode('utf-8-sig')]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/export/json")
async def export_json_report(
    period: str = "monthly",
    date: Optional[str] = None,
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Session = Depends(get_db) if _db_available else None
):
    """
    JSON formatında rapor export eder.
    period: "daily", "weekly", "monthly"
    """
    if period == "daily":
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")
        report_data = await get_daily_report(date, store=store, db=db)
    elif period == "weekly":
        report_data = await get_weekly_report(date, store=store, db=db)
    elif period == "monthly":
        if date:
            try:
                year, month = map(int, date.split("-"))
                report_data = await get_monthly_report(year, month, store=store, db=db)
            except:
                raise HTTPException(status_code=400, detail="Geçersiz tarih formatı. YYYY-MM formatında olmalı.")
        else:
            report_data = await get_monthly_report(store=store, db=db)
    else:
        raise HTTPException(status_code=400, detail="Geçersiz period.")
    
    return JSONResponse(content=report_data)

