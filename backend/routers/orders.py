"""
Sipariş Yönetimi Router
Trendyol siparişlerini yönetir.

Not (Trendyol 2026): Sayfalı `.../sapigw/.../orders` çekimleri 15 Mayıs 2026 sonrası
toplam 10.000 kayıt ve rate limit ile sınırlı; aşımda 429. Geniş tarama / senkron için
`utils.trendyol_api.iter_shipment_packages_stream` (getShipmentPackagesStream) kullanın.
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
import requests

from database.db import get_db
from database.models import Store
from security import get_current_store
from utils.store_trendyol import resolve_trendyol_creds, fetch_orders

router = APIRouter()


class Order(BaseModel):
    """Sipariş modeli"""
    order_id: str
    order_date: str
    items: List[dict]
    total_amount: float
    status: str
    customer_info: Optional[dict] = None


# ÖNEMLİ: Spesifik route'lar ({order_id} gibi) en sonda olmalı
# /stats ve /test-trendyol gibi spesifik endpoint'ler önce tanımlanmalı

@router.get("/stats")
async def get_order_stats(
    period: str = "all",
    store: Store = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    """
    Sipariş istatistiklerini döner.
    Trendyol API'den gerçek verileri çeker.
    
    Args:
        period: Zaman dilimi filtresi
            - "all": Tüm siparişler (varsayılan)
            - "7days": Son 7 gün
            - "15days": Son 15 gün
            - "30days": Son 30 gün
            - "1month": Son 1 ay (30 gün)
    """
    from datetime import datetime, timedelta

    # Wave3: bu mağazanın Trendyol kimliğini çöz (env DEĞİL); bağlı değilse 409
    creds = resolve_trendyol_creds(db, store)

    try:
        # Bu mağazanın tüm siparişlerini per-store creds ile çek
        all_orders = fetch_orders(creds)

        # Eğer sipariş bulunamadıysa
        if not all_orders:
            return {
                "total_orders": 0,
                "pending_orders": 0,
                "awaiting_shipment": 0,
                "shipped_orders": 0,
                "delivered_orders": 0,
                "average_order_value": 0.0,
                "total_revenue": 0.0,
                "message": "Henüz sipariş bulunmuyor",
                "period": period
            }
        
        # Zaman filtresi uygula
        from datetime import timezone
        today = datetime.now(timezone.utc) if hasattr(datetime.now(), 'astimezone') else datetime.now()
        filtered_orders = []
        
        if period == "all":
            # Tüm siparişleri dahil et
            filtered_orders = all_orders
        else:
            # Gün sayısını belirle
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
            
            for order in all_orders:
                try:
                    order_date_str = order.get("orderDate") or order.get("order_date") or order.get("orderDateValue")
                    if not order_date_str:
                        # Tarih yoksa, period "all" değilse atla
                        continue
                    
                    # Farklı tarih formatlarını destekle
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
                                    order_date = datetime.strptime(order_date_str.split('T')[0], "%Y-%m-%d")
                        else:
                            # Sadece tarih formatı: 2024-01-15
                            order_date = datetime.strptime(order_date_str, "%Y-%m-%d")
                    elif isinstance(order_date_str, (int, float)):
                        # Timestamp formatı — Trendyol epoch-ms (13 hane) gönderir, epoch-s DEĞİL
                        _ts = float(order_date_str)
                        if _ts > 1e12:
                            _ts = _ts / 1000
                        order_date = datetime.fromtimestamp(_ts)
                        if order_date.tzinfo:
                            order_date = order_date.replace(tzinfo=None)
                    else:
                        continue
                    
                    # Zaman filtresini uygula
                    if order_date and order_date >= cutoff_date:
                        filtered_orders.append(order)
                except Exception as e:
                    # Tarih parse edilemezse, period "all" değilse atla
                    if period == "all":
                        # Tüm zamanlar için, parse edilemeyen siparişleri de dahil et
                        filtered_orders.append(order)
                    continue
        
        # İstatistikleri hesapla
        total_orders = len(filtered_orders)
        
        # Sipariş durumlarını ayır (case-insensitive ve farklı alan isimlerini kontrol et)
        # NOT: pending-orders endpoint'i ile aynı mantık için sadece ["Created", "Picking", "Invoiced"] kullanıyoruz
        awaiting_shipment_statuses = ["Created", "Picking", "Invoiced"]  # Kargoya verilmesi gerekenler (pending-orders ile aynı)
        shipped_statuses = ["Shipped", "InTransit", "OnTheWay"]  # Kargoda
        delivered_statuses = ["Delivered", "Completed", "Closed"]  # Teslim edilmiş
        
        def get_order_status(order):
            """Sipariş durumunu farklı alan isimlerinden al"""
            # Farklı olası alan isimlerini kontrol et
            status = (
                order.get("status") or 
                order.get("orderStatus") or 
                order.get("statusName") or 
                order.get("orderStatusName") or
                order.get("shipmentPackageStatus") or
                ""
            )
            # Önce string'e çevir, sonra normalize et
            if status is None:
                return ""
            if isinstance(status, (int, float)):
                status = str(status)
            if isinstance(status, str):
                return status.strip()
            return str(status) if status else ""
        
        def has_cargo_tracking(order):
            """Siparişin kargo takip numarası var mı kontrol et - SADECE gerçek kargo takip numaraları"""
            # Kargo takip numarasını farklı alanlardan kontrol et
            cargo_tracking = (
                order.get("cargoTrackingNumber") or 
                order.get("trackingNumber") or 
                order.get("shipmentPackageBarcode") or
                order.get("packageBarcode") or
                order.get("cargoBarcode") or
                None
            )
            
            # Eğer sipariş detayında yoksa, shipment bilgilerinden kontrol et
            if not cargo_tracking:
                shipment = order.get("shipment", {})
                if isinstance(shipment, dict):
                    cargo_tracking = (
                        shipment.get("cargoTrackingNumber") or
                        shipment.get("trackingNumber") or
                        shipment.get("barcode") or
                        None
                    )
            
            # Geçerli bir kargo takip numarası kontrolü
            if cargo_tracking is None:
                return False
            
            # String'e çevir
            if not isinstance(cargo_tracking, str):
                cargo_tracking = str(cargo_tracking)
            
            # Boş string, sadece boşluk, "0", "null", "none" gibi değerleri geçersiz say
            cargo_tracking = cargo_tracking.strip()
            
            # Geçersiz değerler listesi (genişletilmiş)
            invalid_values = ["", "0", "null", "none", "undefined", "false", "true", "none", "n/a", "na"]
            
            # Kargo takip numarası en az 3 karakter olmalı (gerçek takip numaraları genelde daha uzun)
            if len(cargo_tracking) < 3:
                return False
            
            # Geçersiz değerler listesinde değilse ve yeterince uzunsa geçerli say
            return cargo_tracking.lower() not in invalid_values
        
        # Status listelerini normalize et (büyük harfe çevir)
        awaiting_shipment_statuses_normalized = [s.upper() for s in awaiting_shipment_statuses]
        shipped_statuses_normalized = [s.upper() for s in shipped_statuses]
        delivered_statuses_normalized = [s.upper() for s in delivered_statuses]
        
        awaiting_shipment = 0
        shipped_orders = 0
        delivered_orders = 0
        
        # Debug: Status değerlerini ve kargo takip durumlarını topla
        unique_statuses = set()
        debug_info_list = []
        awaiting_shipment_orders = []  # Kargoya verilmesi gereken siparişleri kaydet
        
        for order in filtered_orders:
            status = get_order_status(order)
            status_upper = status.upper() if status else ""
            has_tracking = has_cargo_tracking(order)
            
            # Kargoya verilmesi gereken siparişleri özel olarak kaydet (pending-orders ile aynı mantık - sadece status kontrolü)
            if status_upper in awaiting_shipment_statuses_normalized:
                awaiting_shipment_orders.append({
                    "order_id": order.get("orderNumber") or order.get("id", ""),
                    "status": status,
                    "status_upper": status_upper,
                    "has_tracking": has_tracking,
                    "cargo_tracking": order.get("cargoTrackingNumber") or order.get("trackingNumber") or "yok"
                })
            
            # İlk 20 siparişin detaylarını kaydet (debug için - daha fazla örnek)
            if len(debug_info_list) < 20:
                # Hangi kategoriye atandığını belirle
                category = "unknown"
                if status_upper in delivered_statuses_normalized:
                    category = "delivered"
                elif has_tracking:
                    category = "shipped"
                elif status_upper in shipped_statuses_normalized:
                    category = "shipped"
                elif status_upper in awaiting_shipment_statuses_normalized:
                    category = "awaiting_shipment"
                elif status:
                    category = "awaiting_shipment"
                
                debug_info_list.append({
                    "status": status,
                    "status_upper": status_upper,
                    "has_tracking": has_tracking,
                    "order_id": order.get("orderNumber") or order.get("id", ""),
                    "cargo_tracking": order.get("cargoTrackingNumber") or order.get("trackingNumber") or "yok",
                    "category": category,
                    "is_awaiting": status_upper in awaiting_shipment_statuses_normalized,
                    "is_shipped_status": status_upper in shipped_statuses_normalized,
                    "is_delivered": status_upper in delivered_statuses_normalized
                })
                if status:
                    unique_statuses.add(status)
            
            # KARGOYA VERİLMESİ GEREKEN: Status "Created", "Picking", "Invoiced" (pending-orders ile TAMAMEN AYNI mantık - sadece status kontrolü)
            # KARGODA: Status "Shipped" VEYA geçerli kargo takip numarası VAR
            # TESLİM EDİLDİ: Status "Delivered", "Completed"
            
            # Önce teslim edilmiş durumları kontrol et (en yüksek öncelik)
            if status_upper in delivered_statuses_normalized:
                delivered_orders += 1
            # Status "Shipped" ise -> kargoda
            elif status_upper in shipped_statuses_normalized:
                shipped_orders += 1
            # Status "Created", "Picking", "Invoiced" ise -> kargoya verilmesi gereken (pending-orders ile TAMAMEN AYNI mantık)
            elif status_upper in awaiting_shipment_statuses_normalized:
                # Bekleyen durumda -> kargoya verilmesi gereken (kargo takip numarası kontrolü YOK)
                awaiting_shipment += 1
            # Kargo takip numarası varsa VE geçerli bir takip numarasıysa -> kargoda (teslim edilmiş ve bekleyen değilse)
            elif has_tracking:
                # Geçerli kargo takip numarası var ama henüz teslim edilmemiş -> kargoda
                shipped_orders += 1
            # Eğer hiçbir kategoriye uymuyorsa ve status varsa, bekleyen olarak say
            elif status:
                # Bilinmeyen status -> varsayılan olarak bekleyen say
                awaiting_shipment += 1
        
        # Geriye uyumluluk için pending_orders (bekleyen + kargoda)
        pending_orders = awaiting_shipment + shipped_orders
        
        # Toplam tutarı hesapla
        total_amount = 0.0
        for order in filtered_orders:
            # Farklı API yanıt formatlarını destekle
            total_price = order.get("totalPrice") or order.get("totalPriceValue") or order.get("totalAmount") or 0.0
            if isinstance(total_price, str):
                try:
                    total_price = float(total_price.replace(",", "."))
                except:
                    total_price = 0.0
            total_amount += float(total_price) if total_price else 0.0
        
        average_order_value = total_amount / total_orders if total_orders > 0 else 0.0
        
        # Period açıklaması
        period_label = {
            "all": "Tüm Zamanlar",
            "30days": "Son 30 Gün",
            "1month": "Son 1 Ay",
            "7days": "Son 7 Gün",
            "15days": "Son 15 Gün"
        }.get(period, period)
        
        return {
            "total_orders": total_orders,
            "pending_orders": pending_orders,  # Geriye uyumluluk için
            "awaiting_shipment": awaiting_shipment,  # Kargoya verilmesi gerekenler
            "shipped_orders": shipped_orders,  # Kargoda
            "delivered_orders": delivered_orders,  # Teslim edilmiş
            "average_order_value": round(average_order_value, 2),
            "total_revenue": round(total_amount, 2),
            "last_updated": datetime.now().isoformat(),
            "period": period,
            "period_label": period_label,
            "total_orders_all_time": len(all_orders),  # Karşılaştırma için
            "total_orders_from_api": len(all_orders),  # API'den gelen toplam (fetch_orders zaten tüm sayfaları çekiyor)
            "debug_info": {
                "fetched_orders": len(all_orders),
                "filtered_orders": len(filtered_orders),
                "unique_statuses": list(unique_statuses)[:20],  # İlk 20 farklı status değeri
                "sample_orders": debug_info_list[:10],  # İlk 10 siparişin detaylı bilgisi
                "awaiting_shipment_orders": awaiting_shipment_orders,  # Kargoya verilmesi gereken siparişler
                "counts": {
                    "awaiting_shipment": awaiting_shipment,
                    "shipped_orders": shipped_orders,
                    "delivered_orders": delivered_orders
                }
            }
        }
    
    except requests.exceptions.Timeout:
        return {
            "total_orders": 0,
            "pending_orders": 0,
            "awaiting_shipment": 0,
            "shipped_orders": 0,
            "delivered_orders": 0,
            "average_order_value": 0.0,
            "total_revenue": 0.0,
            "error": "Trendyol API'ye bağlanırken zaman aşımı oluştu"
        }
    
    except requests.exceptions.ConnectionError:
        return {
            "total_orders": 0,
            "pending_orders": 0,
            "awaiting_shipment": 0,
            "shipped_orders": 0,
            "delivered_orders": 0,
            "average_order_value": 0.0,
            "total_revenue": 0.0,
            "error": "Trendyol API'ye bağlanılamadı"
        }
    
    except Exception as e:
        return {
            "total_orders": 0,
            "pending_orders": 0,
            "awaiting_shipment": 0,
            "shipped_orders": 0,
            "delivered_orders": 0,
            "average_order_value": 0.0,
            "total_revenue": 0.0,
            "error": f"Beklenmeyen hata: {str(e)}"
        }


@router.get("/test-trendyol")
async def test_trendyol_api(
    store: Store = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    """
    Trendyol API bağlantısını test eder (Wave3: per-store creds).
    """
    import requests
    import base64

    # Wave3: bu mağazanın Trendyol kimliğini çöz; bağlı değilse 409
    creds = resolve_trendyol_creds(db, store)
    api_key = creds.api_key
    supplier_id = creds.supplier_id

    url = f"https://api.trendyol.com/sapigw/suppliers/{supplier_id}/orders"
    auth_b64 = base64.b64encode(f"{creds.api_key}:{creds.api_secret}".encode('ascii')).decode('ascii')
    headers = {
        "Authorization": f"Basic {auth_b64}",
        "Content-Type": "application/json",
        "User-Agent": f"{supplier_id} - SelfIntegration",
    }

    try:
        # Test isteği - sadece 1 sipariş çek
        response = requests.get(
            url,
            headers=headers,
            params={"page": 0, "size": 1},
            timeout=10
        )
        
        return {
            "success": response.status_code == 200,
            "status_code": response.status_code,
            "message": "Trendyol API'ye başarıyla bağlanıldı" if response.status_code == 200 else f"API yanıt kodu: {response.status_code}",
            "response_preview": response.text[:500] if response.text else "Boş yanıt",
            "api_info": {
                "supplier_id": supplier_id,
                "api_key_prefix": api_key[:10] + "..." if api_key else None,
                "endpoint": url
            }
        }
    
    except requests.exceptions.Timeout:
        return {
            "success": False,
            "error": "Timeout",
            "message": "Trendyol API'ye bağlanırken zaman aşımı oluştu"
        }
    
    except requests.exceptions.ConnectionError:
        return {
            "success": False,
            "error": "Connection Error",
            "message": "Trendyol API'ye bağlanılamadı. İnternet bağlantınızı kontrol edin."
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": str(type(e).__name__),
            "message": f"Beklenmeyen hata: {str(e)}"
        }


@router.get("/")
async def get_orders(
    period: str = "all",
    store: Store = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    """
    Tüm siparişleri listeler (Wave3: per-store).

    Args:
        period: Zaman dilimi filtresi
            - "all": Tüm siparişler (varsayılan)
            - "7days": Son 7 gün
            - "15days": Son 15 gün
            - "30days": Son 30 gün
            - "1month": Son 1 ay (30 gün)
    """
    from datetime import datetime, timedelta, timezone

    # Wave3: bu mağazanın Trendyol kimliğini çöz; bağlı değilse 409
    creds = resolve_trendyol_creds(db, store)

    try:
        # Bu mağazanın tüm siparişlerini per-store creds ile çek
        all_orders = fetch_orders(creds)

        # Zaman filtresi uygula (stats endpoint'inde kullanılan aynı mantık)
        today = datetime.now(timezone.utc) if hasattr(datetime.now(), 'astimezone') else datetime.now()
        filtered_orders = []
        
        if period == "all":
            filtered_orders = all_orders
        else:
            days = 30
            if period == "7days":
                days = 7
            elif period == "15days":
                days = 15
            elif period == "30days" or period == "1month":
                days = 30
            
            cutoff_date = today - timedelta(days=days)
            if cutoff_date.tzinfo:
                cutoff_date = cutoff_date.replace(tzinfo=None)
            
            for order in all_orders:
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
                    if period == "all":
                        filtered_orders.append(order)
                    continue
        
        # Siparişleri formatla
        formatted_orders = []
        for order in filtered_orders:
            formatted_orders.append({
                "order_id": order.get("orderNumber", order.get("id", "")),
                "order_date": order.get("orderDate", ""),
                "items": order.get("lines", []),
                "total_amount": float(order.get("totalPrice", order.get("totalPriceValue", 0)) or 0),
                "status": order.get("status", order.get("orderStatus", "Unknown")),
                "total_price": order.get("totalPrice", order.get("totalPriceValue", 0)),
                "totalPriceValue": order.get("totalPriceValue", 0)
            })
        
        return {
            "orders": formatted_orders,
            "total": len(formatted_orders),
            "period": period
        }
    
    except Exception as e:
        return {
            "orders": [],
            "total": 0,
            "error": f"Hata: {str(e)}"
        }


@router.get("/{order_id}")
async def get_order(
    order_id: str,
    store: Store = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    """Belirli bir siparişi getirir (Wave3: per-store)"""
    from datetime import datetime

    # Wave3: bu mağazanın Trendyol kimliğini çöz; bağlı değilse 409
    creds = resolve_trendyol_creds(db, store)

    try:
        # Bu mağazanın tüm siparişlerini per-store creds ile çek, tek geçişte ara
        all_orders = fetch_orders(creds)
        orders = all_orders

        while True:
            if not orders:
                break

            try:
                # Sipariş bulundu mu kontrol et
                for order in orders:
                    current_order_id = str(order.get("orderNumber") or order.get("id", ""))
                    if current_order_id == str(order_id):
                        # Sipariş bulundu, detayları hazırla
                        lines = order.get("lines", []) or order.get("orderLines", []) or []
                        
                        # Tarih formatını düzelt
                        order_date_str = order.get("orderDate") or order.get("order_date", "")
                        if order_date_str:
                            try:
                                # ISO formatından parse et
                                if 'T' in order_date_str:
                                    order_date = datetime.fromisoformat(order_date_str.replace('Z', '+00:00'))
                                else:
                                    order_date = datetime.strptime(order_date_str, "%Y-%m-%d")
                                order_date_formatted = order_date.strftime("%d.%m.%Y %H:%M:%S")
                            except:
                                order_date_formatted = order_date_str
                        else:
                            order_date_formatted = ""
                        
                        # Toplam tutarı hesapla
                        total_price = order.get("totalPrice") or order.get("totalPriceValue") or order.get("totalAmount") or 0.0
                        if isinstance(total_price, str):
                            total_price = float(total_price.replace(",", "."))
                        
                        # Kargo takip numarası
                        cargo_tracking = (
                            order.get("cargoTrackingNumber") or 
                            order.get("trackingNumber") or
                            (order.get("shipment", {}).get("cargoTrackingNumber") if isinstance(order.get("shipment"), dict) else None) or
                            ""
                        )
                        
                        return {
                            "order_id": current_order_id,
                            "order_number": current_order_id,
                            "order_date": order_date_formatted,
                            "orderDate": order_date_str,
                            "status": order.get("status") or order.get("orderStatus", ""),
                            "total_amount": round(float(total_price), 2),
                            "totalPrice": total_price,
                            "totalPriceValue": total_price,
                            "cargo_tracking_number": cargo_tracking,
                            "cargoTrackingNumber": cargo_tracking,
                            "items": [
                                {
                                    "product_id": line.get("productId") or line.get("product_id", ""),
                                    "product_name": line.get("productName") or line.get("product_name") or line.get("name", "Ürün"),
                                    "name": line.get("productName") or line.get("product_name") or line.get("name", "Ürün"),
                                    "quantity": int(line.get("quantity", 0) or 0),
                                    "price": round(float(line.get("price") or line.get("salePrice") or line.get("unitPrice") or 0), 2)
                                }
                                for line in lines
                            ],
                            "customer": {
                                "first_name": order.get("customerFirstName", ""),
                                "last_name": order.get("customerLastName", ""),
                                "email": order.get("customerEmail", ""),
                                "phone": order.get("customerPhone", "")
                            },
                            "shipment": order.get("shipment", {})
                        }
                
                # Wave3: fetch_orders zaten tüm sayfaları çekti — tek geçiş yeter
                break

            except Exception as e:
                break

        # Sipariş bulunamadı
        raise HTTPException(status_code=404, detail=f"Sipariş bulunamadı: {order_id}")
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sipariş detayı alınamadı: {str(e)}")


@router.post("/sync")
async def sync_orders(
    store: Store = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    """
    Trendyol API'den siparişleri senkronize eder (Wave3: per-store).
    Tüm siparişleri çeker ve güncel durumlarını kontrol eder.
    """
    from datetime import datetime

    # Wave3: bu mağazanın Trendyol kimliğini çöz; bağlı değilse 409
    creds = resolve_trendyol_creds(db, store)

    try:
        # Bu mağazanın tüm siparişlerini per-store creds ile çek
        all_orders = fetch_orders(creds)

        # Sipariş durumlarını analiz et
        status_counts = {}
        for order in all_orders:
            status = order.get("status") or order.get("orderStatus") or "Unknown"
            status_counts[status] = status_counts.get(status, 0) + 1
        
        return {
            "message": "Siparişler başarıyla senkronize edildi",
            "synced_count": len(all_orders),
            "total_orders": len(all_orders),
            "status_breakdown": status_counts,
            "last_sync": datetime.now().isoformat(),
            "details": {
                "fetched_from_api": len(all_orders)
            }
        }
    
    except requests.exceptions.Timeout:
        raise HTTPException(
            status_code=504,
            detail="Trendyol API'ye bağlanırken zaman aşımı oluştu"
        )
    
    except requests.exceptions.ConnectionError:
        raise HTTPException(
            status_code=503,
            detail="Trendyol API'ye bağlanılamadı. İnternet bağlantınızı kontrol edin."
        )
    
    except HTTPException:
        raise
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Sipariş senkronizasyonu sırasında hata oluştu: {str(e)}"
        )
