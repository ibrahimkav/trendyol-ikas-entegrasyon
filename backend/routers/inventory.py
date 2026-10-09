"""
Stok Yönetimi Router
Ürün stok takibi ve düşük stok uyarıları
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from collections import defaultdict
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
import os
import requests
import base64
import json

# Database modülünü optional olarak yükle (ghost mode)
try:
    from database.db import get_db
    from database.models import StockAlert, StockRecommendation, StockHistory, Product, OrderLine, Store
    from security import get_current_store
    from utils.store_trendyol import resolve_trendyol_creds, try_resolve_trendyol_creds, fetch_products as _fetch_store_products, fetch_orders as _fetch_store_orders
    from utils.thresholds import get_effective_thresholds, DEFAULT_LOW_STOCK_FLOOR, DEFAULT_LOW_STOCK_SALES_RATIO
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


class ProductStock(BaseModel):
    """Ürün stok modeli"""
    product_id: str
    product_name: str
    current_stock: int
    min_stock_level: int
    status: str  # "in_stock", "low_stock", "out_of_stock"
    last_updated: str
    category: Optional[str] = None
    barcode: Optional[str] = None


def get_trendyol_products_data(creds=None) -> Dict[str, Dict]:
    """Bu mağazanın Trendyol ürün/stok bilgilerini çeker (Wave3: per-store, env DEĞİL).
    creds = utils.store_trendyol.resolve_trendyol_creds(db, store) ile çözülür.
    NOT: creds=None → {} (henüz dönüştürülmemiş çağıranlar için güvenli köprü)."""
    if creds is None:
        return {}

    products = {}

    try:
        items = _fetch_store_products(creds, max_pages=10, size=500)

        if items:
            for item in items:
                try:
                    # Ürün ID'sini al
                    # w3-hardening (2026-09-26): operatör önceliği hatası düzeltildi —
                    # "X or Y or Z if W else V" aslında "(X or Y or Z) if W else V" olarak
                    # parse ediliyordu (ternary, or-zincirinden DÜŞÜK önceliklidir). item'da
                    # "id" alanı yoksa (fetch_products'ın ürettiği flat item'larda yok) TÜM
                    # ifade "" oluyordu — barcode/merchantSku/productId dolu olsa bile.
                    # Bu yüzden gerçek ürün verisi HİÇ eşleşmiyordu (dict hep boş kalıyordu).
                    product_id = (
                        item.get("barcode") or
                        item.get("merchantSku") or
                        item.get("productId") or
                        (str(item.get("id", "")) if item.get("id") else "")
                    )

                    if not product_id:
                        continue

                    product_id_str = str(product_id)

                    # Stok bilgisini al
                    stock_quantity = (
                        item.get("stockQuantity") or
                        item.get("stock_quantity") or
                        item.get("quantity") or
                        item.get("availableStock") or
                        item.get("available_stock") or
                        0
                    )
                    
                    if isinstance(stock_quantity, str):
                        try:
                            stock_quantity = int(float(stock_quantity))
                        except:
                            stock_quantity = 0
                    
                    stock_quantity = int(stock_quantity) if stock_quantity else 0
                    
                    products[product_id_str] = {
                        "product_id": product_id_str,
                        "product_name": item.get("productName") or item.get("product_name") or item.get("title") or "Bilinmeyen Ürün",
                        "stock_quantity": stock_quantity,
                        "price": item.get("salePrice") or item.get("listPrice") or item.get("price") or 0.0,
                        "category": item.get("categoryName") or item.get("category_name") or "",
                        "barcode": item.get("barcode") or item.get("merchantSku") or ""
                    }
                except Exception as e:
                    continue

    except Exception as e:
        print(f"[Inventory] Products API hatası: {str(e)}")
        return {}

    return products


def get_trendyol_orders_data(creds=None) -> List[Dict]:
    """Bu mağazanın Trendyol siparişlerini çeker (Wave3: per-store, env DEĞİL).
    NOT: creds=None → [] (henüz dönüştürülmemiş çağıranlar için güvenli köprü)."""
    if creds is None:
        return []
    try:
        return _fetch_store_orders(creds, max_pages=100, size=200)
    except Exception:
        return []


@router.get("/products")
async def get_product_stock(
    include_out_of_stock: bool = False,
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Session = Depends(get_db) if _db_available else None
):
    """
    Tüm ürünlerin stok durumunu döner.
    Önce Trendyol API'den gerçek stok bilgisini çeker, yoksa sipariş verilerinden tahmin yapar.
    """
    # Wave3: per-store credential (bağlı değilse creds=None → köprü, boş sonuç, 409 fırlatmaz)
    creds = try_resolve_trendyol_creds(db, store) if (_db_available and store) else None

    # Önce gerçek stok bilgisini Trendyol API'den çek
    trendyol_products = get_trendyol_products_data(creds)

    orders = get_trendyol_orders_data(creds)
    
    # Ürün bilgilerini topla
    products = {}
    product_sales = defaultdict(lambda: {"count": 0, "last_sale_date": None})
    
    # Trendyol API'den gelen gerçek stok bilgilerini kullan
    for product_id, product_info in trendyol_products.items():
        products[product_id] = {
            "product_id": product_id,
            "product_name": product_info.get("product_name", "Bilinmeyen Ürün"),
            "category": product_info.get("category", ""),
            "barcode": product_info.get("barcode", ""),
            "real_stock": product_info.get("stock_quantity", 0),
            "has_real_stock": True,
            "first_seen": datetime.now(),
            "last_seen": datetime.now()
        }
    
    if not orders and not trendyol_products:
        return {
            "products": [],
            "total_products": 0,
            "low_stock_count": 0,
            "out_of_stock_count": 0,
            "message": "Sipariş veya ürün verisi bulunamadı"
        }
    
    # Son 90 günün siparişlerini analiz et
    today = datetime.now()
    cutoff_date = today - timedelta(days=90)
    
    orders_processed = 0
    products_found = 0
    
    for order in orders:
        try:
            # Tarih kontrolü - daha esnek
            order_date = None
            order_date_str = (
                order.get("orderDate") or 
                order.get("order_date") or 
                order.get("orderDateStr") or
                order.get("createdDate") or
                order.get("created_date")
            )
            
            if order_date_str:
                try:
                    if isinstance(order_date_str, (int, float)):
                        # Trendyol orderDate epoch-ms (13 hane) gönderir, epoch-s DEĞİL —
                        # bu kontrol olmadan strptime'a düşüp her sipariş "bugün" sayılıyordu
                        # (90-günlük stok tahmini için tüm siparişler aynı gün gibi görünüyordu).
                        _ts = float(order_date_str)
                        if _ts > 1e12:
                            _ts = _ts / 1000
                        order_date = datetime.fromtimestamp(_ts)
                        if order_date.tzinfo:
                            order_date = order_date.replace(tzinfo=None)
                    elif 'T' in str(order_date_str):
                        order_date = datetime.fromisoformat(str(order_date_str).replace('Z', '+00:00'))
                        if order_date.tzinfo:
                            order_date = order_date.replace(tzinfo=None)
                    else:
                        order_date = datetime.strptime(str(order_date_str), "%Y-%m-%d")

                    if order_date < cutoff_date:
                        continue
                except:
                    # Tarih parse edilemezse, siparişi yine de işle (tarih filtresi olmadan)
                    order_date = today
            else:
                # Tarih yoksa, bugün olarak kabul et
                order_date = today
        except:
            order_date = today
        
        # Farklı alan adlarını dene
        lines = (
            order.get("lines") or 
            order.get("orderLines") or 
            order.get("items") or 
            order.get("lineItems") or
            order.get("orderItems") or
            []
        )
        
        # Eğer lines bir dict ise, listeye çevir
        if isinstance(lines, dict):
            lines = [lines]
        
        # Eğer lines yoksa, siparişin kendisinden ürün bilgisi çıkarmayı dene
        if not lines or len(lines) == 0:
            product_id = (
                order.get("productId") or 
                order.get("product_id") or 
                order.get("barcode") or 
                order.get("sku") or
                ""
            )
            if product_id:
                lines = [{
                    "productId": product_id,
                    "productName": order.get("productName") or order.get("product_name") or "Bilinmeyen Ürün",
                    "quantity": order.get("quantity", 1),
                    "categoryName": order.get("categoryName") or order.get("category_name") or "",
                    "barcode": order.get("barcode") or order.get("sku") or ""
                }]
        
        if lines and len(lines) > 0:
            orders_processed += 1
        
        for line in lines:
            try:
                # Debug: İlk line'ın yapısını göster
                if products_found == 0 and orders_processed == 1:
                    print(f"[Inventory] İlk line keys: {list(line.keys())[:20] if isinstance(line, dict) else 'Not a dict'}")
                    print(f"[Inventory] İlk line içeriği: {str(line)[:200]}")
                
                # Farklı alan adlarını dene (daha kapsamlı)
                product_id = None
                
                # w3-hardening (2026-09-26): barcode/sku ÖNCELİKLİ — get_trendyol_products_data()
                # (fetch_products, gerçek Trendyol ürün API'si) variant.barcode'u anahtar olarak
                # kullanıyor; eskiden productCode (bir contentId-benzeri numara, barcode'la HİÇ
                # eşleşmiyor) önce deneniyordu, bu yüzden gerçek stok verisi asla eşleşmiyordu
                # (gerçek çağrıyla kanıtlandı: productCode='1425243751', barcode='2317B34').
                # merchantSku ve stockCode bazen "merchantSku" string'i olabiliyor, bu yüzden kontrol et
                for key in ["barcode", "sku", "productCode", "product_code", "productId", "product_id",
                           "stockCode", "sellerSku", "productSku", "itemId", "item_id"]:
                    value = line.get(key)
                    if value:
                        val_str = str(value).strip()
                        # merchantSku veya stockCode'nun değeri "merchantSku" string'i ise atla
                        if val_str and val_str.lower() not in ["merchantsku", "stockcode"]:
                            product_id = val_str
                            break
                
                # merchantSku'yu sadece gerçek bir değer varsa kullan
                if not product_id:
                    merchant_sku = line.get("merchantSku")
                    if merchant_sku:
                        val_str = str(merchant_sku).strip()
                        if val_str and val_str.lower() != "merchantsku":
                            product_id = val_str
                
                # Hala bulunamadıysa, id alanlarını dene
                if not product_id:
                    if line.get("id"):
                        product_id = str(line.get("id"))
                    elif line.get("lineItemId"):
                        product_id = str(line.get("lineItemId"))
                    elif line.get("contentId"):
                        product_id = str(line.get("contentId"))
                
                # Hala yoksa, tüm değerleri kontrol et
                if not product_id and isinstance(line, dict):
                    for key, value in line.items():
                        if key.lower() in ["productcode", "productid", "barcode", "sku", "stockcode"] and value:
                            val_str = str(value).strip()
                            if val_str and val_str.lower() not in ["merchantsku", "stockcode"]:
                                product_id = val_str
                                break
                
                product_name = (
                    line.get("productName") or 
                    line.get("product_name") or 
                    line.get("name") or 
                    line.get("productTitle") or
                    line.get("product_title") or
                    line.get("title") or
                    "Bilinmeyen Ürün"
                )
                
                quantity = (
                    line.get("quantity") or 
                    line.get("qty") or 
                    line.get("amount") or
                    1
                )
                if quantity is None:
                    quantity = 1
                try:
                    quantity = int(quantity) if quantity else 1
                except:
                    quantity = 1
                
                if product_id and product_id != "None" and product_id != "":
                    product_id_str = str(product_id)
                    products_found += 1
                    
                    # Ürün bilgilerini kaydet
                    if product_id_str not in products:
                        products[product_id_str] = {
                            "product_id": product_id_str,
                            "product_name": product_name,
                            "category": line.get("categoryName") or line.get("category_name") or "",
                            "barcode": line.get("barcode") or line.get("sku") or "",
                            "real_stock": None,
                            "has_real_stock": False,
                            "first_seen": order_date,
                            "last_seen": order_date
                        }
                    else:
                        if order_date > products[product_id_str]["last_seen"]:
                            products[product_id_str]["last_seen"] = order_date
                        
                        # Eğer gerçek stok bilgisi yoksa, ürün adını güncelle
                        if not products[product_id_str].get("has_real_stock") and product_name != "Bilinmeyen Ürün":
                            products[product_id_str]["product_name"] = product_name
                    
                    # Satış sayısını güncelle
                    product_sales[product_id_str]["count"] += quantity
                    if not product_sales[product_id_str]["last_sale_date"] or order_date > product_sales[product_id_str]["last_sale_date"]:
                        product_sales[product_id_str]["last_sale_date"] = order_date
            except Exception as e:
                continue
    
    # Debug bilgisi
    print(f"[Inventory] İşlenen sipariş: {orders_processed}, Bulunan ürün: {products_found}, Benzersiz ürün: {len(products)}")
    
    # Stok tahmini yap (basit bir yöntem: son 30 günlük ortalama satış * 2)
    stock_products = []
    low_stock_count = 0
    out_of_stock_count = 0

    # w3-configurable-thresholds: store bazında ayarlanabilir (bkz. utils/thresholds.py).
    # Ghost mode veya store yoksa eski koddaki sabit varsayılanlar aynen kullanılır.
    if _db_available and store and db:
        _th = get_effective_thresholds(db, store.id)
        low_stock_floor, low_stock_sales_ratio = _th["low_stock_floor"], _th["low_stock_sales_ratio"]
    else:
        low_stock_floor, low_stock_sales_ratio = 5, 0.15

    for product_id, product_info in products.items():
        sales_data = product_sales.get(product_id, {})
        sales_count = sales_data.get("count", 0)
        last_sale_date = sales_data.get("last_sale_date")
        
        # Gerçek stok bilgisi varsa onu kullan, yoksa tahmin yap
        if product_info.get("has_real_stock") and product_info.get("real_stock") is not None:
            current_stock = int(product_info["real_stock"])
        else:
            # Son 30 günlük ortalama satış (basit tahmin)
            days_active = (today - product_info["first_seen"]).days
            if days_active > 0:
                daily_avg = sales_count / min(days_active, 90)
                estimated_stock = int(daily_avg * 30)  # 30 günlük stok tahmini
            else:
                estimated_stock = 0
            
            # Son satış tarihine göre stok azaltma
            if last_sale_date:
                days_since_last_sale = (today - last_sale_date).days
                if days_since_last_sale > 0:
                    # Son satıştan bu yana geçen günler için stok azalt
                    estimated_stock = max(0, estimated_stock - (days_since_last_sale * daily_avg))
            
            current_stock = estimated_stock
        
        # Minimum stok seviyesi (store bazında ayarlanabilir taban/oran)
        min_stock = max(low_stock_floor, int(sales_count * low_stock_sales_ratio)) if sales_count > 0 else low_stock_floor
        
        # Stok durumu
        if current_stock <= 0:
            status = "out_of_stock"
            out_of_stock_count += 1
        elif current_stock <= min_stock:
            status = "low_stock"
            low_stock_count += 1
        else:
            status = "in_stock"
        
        # Eğer son satış 60 günden eskiyse ve gerçek stok bilgisi yoksa, stok yok say
        if not product_info.get("has_real_stock") and last_sale_date:
            days_since_last_sale = (today - last_sale_date).days
            if days_since_last_sale > 60:
                status = "out_of_stock"
                current_stock = 0
                out_of_stock_count += 1
                if status == "low_stock":
                    low_stock_count -= 1
        
        if not include_out_of_stock and status == "out_of_stock":
            continue
        
        stock_products.append({
            "product_id": product_id,
            "product_name": product_info["product_name"],
            "current_stock": current_stock,
            "min_stock_level": min_stock,
            "status": status,
            "last_updated": product_info["last_seen"].strftime("%Y-%m-%d %H:%M:%S") if isinstance(product_info["last_seen"], datetime) else datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "category": product_info.get("category", ""),
            "barcode": product_info.get("barcode", ""),
            "total_sales_90days": sales_count,
            "days_since_last_sale": (today - last_sale_date).days if last_sale_date else None,
            "is_real_stock": product_info.get("has_real_stock", False)
        })
    
    # Stok seviyesine göre sırala (düşük stok önce)
    status_order = {"out_of_stock": 0, "low_stock": 1, "in_stock": 2}
    stock_products.sort(key=lambda x: (status_order.get(x["status"], 3), -x["current_stock"]))
    
    # Eğer hiç ürün bulunamadıysa, siparişlerden ürün çıkarılamıyor olabilir
    if len(stock_products) == 0 and len(orders) > 0:
        print(f"[Inventory] UYARI: {len(orders)} sipariş var ama hiç ürün bulunamadı. Sipariş yapısını kontrol edin.")
        # İlk siparişin yapısını göster
        if orders:
            first_order = orders[0]
            print(f"[Inventory] İlk sipariş keys: {list(first_order.keys())[:20]}")
            if "lines" in first_order:
                print(f"[Inventory] 'lines' var, tip: {type(first_order['lines'])}, uzunluk: {len(first_order['lines']) if isinstance(first_order['lines'], list) else 'N/A'}")
            if "orderLines" in first_order:
                print(f"[Inventory] 'orderLines' var, tip: {type(first_order['orderLines'])}, uzunluk: {len(first_order['orderLines']) if isinstance(first_order['orderLines'], list) else 'N/A'}")
    
    return {
        "products": stock_products,
        "total_products": len(stock_products),
        "low_stock_count": low_stock_count,
        "out_of_stock_count": out_of_stock_count,
        "in_stock_count": len(stock_products) - low_stock_count - out_of_stock_count,
        "debug_info": {
            "orders_processed": orders_processed,
            "products_found": products_found,
            "unique_products": len(products)
        }
    }


@router.get("/alerts")
async def get_stock_alerts(
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Session = Depends(get_db) if _db_available else None
):
    """
    Düşük stok ve tükenmiş stok uyarılarını döner.
    """
    stock_data = await get_product_stock(include_out_of_stock=True, store=store, db=db)
    
    alerts = []
    for product in stock_data["products"]:
        if product["status"] in ["low_stock", "out_of_stock"]:
            alerts.append({
                "product_id": product["product_id"],
                "product_name": product["product_name"],
                "current_stock": product["current_stock"],
                "min_stock_level": product["min_stock_level"],
                "alert_type": product["status"],
                "days_since_last_sale": product.get("days_since_last_sale"),
                "is_real_stock": product.get("is_real_stock", False)
            })
    
    # Öncelik sırasına göre sırala (tükenmiş > düşük)
    alert_priority = {"out_of_stock": 0, "low_stock": 1}
    alerts.sort(key=lambda x: (alert_priority.get(x["alert_type"], 2), x["current_stock"]))
    
    return {
        "alerts": alerts,
        "total_alerts": len(alerts),
        "low_stock_count": len([a for a in alerts if a["alert_type"] == "low_stock"]),
        "out_of_stock_count": len([a for a in alerts if a["alert_type"] == "out_of_stock"])
    }


@router.get("/summary")
async def get_stock_summary(
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Session = Depends(get_db) if _db_available else None
):
    """
    Stok özet bilgilerini döner.
    """
    stock_data = await get_product_stock(include_out_of_stock=True, store=store, db=db)
    
    return {
        "total_products": stock_data["total_products"],
        "in_stock_count": stock_data["in_stock_count"],
        "low_stock_count": stock_data["low_stock_count"],
        "out_of_stock_count": stock_data["out_of_stock_count"],
        "alert_percentage": round((stock_data["low_stock_count"] + stock_data["out_of_stock_count"]) / stock_data["total_products"] * 100, 1) if stock_data["total_products"] > 0 else 0
    }


class StockRecommendationResponse(BaseModel):
    """Stok önerisi yanıt modeli"""
    id: int
    product_id: str
    product_name: str
    current_stock: int
    recommended_quantity: int
    recommendation_reason: Optional[str]
    urgency_level: str
    estimated_cost: float
    estimated_arrival_days: int
    is_ordered: bool
    created_at: str
    is_real_stock: bool = False


@router.get("/recommendations", response_model=List[StockRecommendationResponse])
async def get_stock_recommendations(
    urgency_level: Optional[str] = None,
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Session = Depends(get_db) if _db_available else None
):
    """
    Otomatik stok sipariş önerilerini getirir
    AI destekli analiz ile önerilen sipariş miktarlarını hesaplar
    """
    if not _db_available:
        # Ghost mode - basit öneriler döndür
        stock_data = await get_product_stock(include_out_of_stock=True)
        recommendations = []
        
        for product in stock_data["products"]:
            if product["status"] in ["low_stock", "out_of_stock"]:
                # Basit öneri: min_stock_level * 2
                recommended_qty = max(product["min_stock_level"] * 2, 10)
                
                recommendations.append({
                    "id": len(recommendations) + 1,
                    "product_id": product["product_id"],
                    "product_name": product["product_name"],
                    "current_stock": product["current_stock"],
                    "recommended_quantity": recommended_qty,
                    "recommendation_reason": f"Stok seviyesi düşük. Minimum seviye: {product['min_stock_level']}",
                    "urgency_level": "critical" if product["status"] == "out_of_stock" else "high",
                    "estimated_cost": 0.0,
                    "estimated_arrival_days": 7,
                    "is_ordered": False,
                    "created_at": datetime.now().isoformat(),
                    "is_real_stock": product.get("is_real_stock", False)
                })
        
        return recommendations
    
    _check_db()
    
    query = db.query(StockRecommendation).filter(StockRecommendation.store_id == store.id, StockRecommendation.is_ordered == False)

    if urgency_level:
        query = query.filter(StockRecommendation.urgency_level == urgency_level)
    
    recommendations = query.order_by(
        StockRecommendation.urgency_level.desc(),
        StockRecommendation.created_at.desc()
    ).limit(50).all()

    # w3-backend-cleanup: is_real_stock ekle — ana listedeki (get_product_stock) aynı
    # mantığı kullanarak canlı bir product_id -> is_real_stock haritası çıkarıp
    # kalıcı StockRecommendation kayıtlarına eşle.
    stock_data = await get_product_stock(include_out_of_stock=True, store=store, db=db)
    real_stock_map = {p["product_id"]: p.get("is_real_stock", False) for p in stock_data["products"]}

    return [
        StockRecommendationResponse(
            id=r.id,
            product_id=r.product_id,
            product_name=r.product_name,
            current_stock=int(round(r.current_stock)) if r.current_stock is not None else 0,
            recommended_quantity=r.recommended_quantity,
            recommendation_reason=r.recommendation_reason,
            urgency_level=r.urgency_level,
            estimated_cost=r.estimated_cost,
            estimated_arrival_days=r.estimated_arrival_days,
            is_ordered=r.is_ordered,
            created_at=r.created_at.isoformat() if r.created_at else "",
            is_real_stock=real_stock_map.get(r.product_id, False)
        )
        for r in recommendations
    ]


@router.post("/recommendations/generate")
async def generate_stock_recommendations(
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Session = Depends(get_db) if _db_available else None
):
    """
    Stok önerilerini otomatik olarak oluşturur
    Mevcut stok durumunu analiz eder ve sipariş önerileri üretir
    """
    if not _db_available:
        raise HTTPException(status_code=503, detail="Database not available (ghost mode)")
    
    _check_db()

    # Stok verilerini al
    stock_data = await get_product_stock(include_out_of_stock=True, store=store, db=db)

    recommendations_created = 0
    
    for product in stock_data["products"]:
        if product["status"] in ["low_stock", "out_of_stock"]:
            # Mevcut öneriyi kontrol et
            existing = db.query(StockRecommendation).filter(
                and_(
                    StockRecommendation.store_id == store.id,
                    StockRecommendation.product_id == product["product_id"],
                    StockRecommendation.is_ordered == False
                )
            ).first()
            
            if existing:
                continue
            
            # Öneri miktarını hesapla
            min_stock = product["min_stock_level"]
            current_stock = product["current_stock"]
            
            # Günlük ortalama satış (son 90 gün)
            total_sales = product.get("total_sales_90days", 0)
            daily_avg = total_sales / 90 if total_sales > 0 else 1
            
            # Önerilen miktar: (min_stock * 2) + (günlük satış * teslimat süresi * 1.5)
            delivery_days = 7
            safety_multiplier = 1.5
            recommended_qty = int(
                max(
                    (min_stock * 2) - current_stock,
                    (daily_avg * delivery_days * safety_multiplier) - current_stock,
                    10  # Minimum 10 adet
                )
            )
            
            # Aciliyet seviyesi
            if product["status"] == "out_of_stock":
                urgency = "critical"
            elif current_stock <= min_stock * 0.5:
                urgency = "high"
            elif current_stock <= min_stock:
                urgency = "medium"
            else:
                urgency = "low"
            
            # Öneri nedeni
            reason = f"Stok seviyesi: {current_stock}, Minimum: {min_stock}. "
            if product.get("days_since_last_sale"):
                reason += f"Son satıştan {product['days_since_last_sale']} gün geçti. "
            reason += f"Günlük ortalama satış: {daily_avg:.1f} adet."
            
            # Yeni öneri oluştur
            recommendation = StockRecommendation(
                store_id=store.id,
                product_id=product["product_id"],
                product_name=product["product_name"],
                current_stock=current_stock,
                recommended_quantity=recommended_qty,
                recommendation_reason=reason,
                urgency_level=urgency,
                estimated_cost=0.0,  # Ürün fiyatı bilgisi eklendiğinde hesaplanabilir
                estimated_arrival_days=delivery_days
            )
            
            db.add(recommendation)
            recommendations_created += 1
    
    db.commit()
    
    return {
        "message": f"{recommendations_created} yeni stok önerisi oluşturuldu",
        "recommendations_created": recommendations_created
    }


@router.get("/alerts/advanced", response_model=List[Dict])
async def get_advanced_stock_alerts(
    include_acknowledged: bool = False,
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Session = Depends(get_db) if _db_available else None
):
    """
    Gelişmiş stok uyarıları - Database tabanlı
    """
    if not _db_available:
        # Ghost mode - basit uyarılar döndür
        alerts_data = await get_stock_alerts()
        return alerts_data.get("alerts", [])
    
    _check_db()

    query = db.query(StockAlert).filter(StockAlert.store_id == store.id)

    if not include_acknowledged:
        query = query.filter(StockAlert.is_acknowledged == False)

    alerts = query.order_by(
        StockAlert.alert_level.desc(),
        StockAlert.created_at.desc()
    ).limit(100).all()

    # w3-backend-cleanup: is_real_stock ekle — ana listedeki (get_product_stock) aynı
    # mantığı kullanarak canlı bir product_id -> is_real_stock haritası çıkarıp
    # kalıcı StockAlert kayıtlarına eşle (DB'de bu bayrak saklanmıyor, yeni mantık icat etmedik).
    stock_data = await get_product_stock(include_out_of_stock=True, store=store, db=db)
    real_stock_map = {p["product_id"]: p.get("is_real_stock", False) for p in stock_data["products"]}

    return [
        {
            "id": a.id,
            "product_id": a.product_id,
            "product_name": a.product_name,
            "current_stock": a.current_stock,
            "min_stock_level": a.min_stock_level,
            "alert_type": a.alert_type,
            "alert_level": a.alert_level,
            "days_since_last_sale": a.days_since_last_sale,
            "average_daily_sales": a.average_daily_sales,
            "estimated_days_until_out": a.estimated_days_until_out,
            "is_acknowledged": a.is_acknowledged,
            "created_at": a.created_at.isoformat() if a.created_at else "",
            "is_real_stock": real_stock_map.get(a.product_id, False)
        }
        for a in alerts
    ]


@router.post("/alerts/acknowledge/{alert_id}")
async def acknowledge_alert(
    alert_id: int,
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Session = Depends(get_db) if _db_available else None
):
    """Stok uyarısını görüldü olarak işaretle"""
    if not _db_available:
        raise HTTPException(status_code=503, detail="Database not available (ghost mode)")

    _check_db()

    alert = db.query(StockAlert).filter(StockAlert.store_id == store.id, StockAlert.id == alert_id).first()
    
    if not alert:
        raise HTTPException(status_code=404, detail="Uyarı bulunamadı")
    
    alert.is_acknowledged = True
    alert.acknowledged_at = datetime.now()
    
    db.commit()
    
    return {"message": "Uyarı görüldü olarak işaretlendi", "alert_id": alert_id}


@router.post("/recommendations/{recommendation_id}/order")
async def mark_recommendation_ordered(
    recommendation_id: int,
    order_reference: Optional[str] = None,
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Session = Depends(get_db) if _db_available else None
):
    """Stok önerisini sipariş verildi olarak işaretle"""
    if not _db_available:
        raise HTTPException(status_code=503, detail="Database not available (ghost mode)")

    _check_db()

    recommendation = db.query(StockRecommendation).filter(
        StockRecommendation.store_id == store.id,
        StockRecommendation.id == recommendation_id
    ).first()
    
    if not recommendation:
        raise HTTPException(status_code=404, detail="Öneri bulunamadı")
    
    recommendation.is_ordered = True
    recommendation.ordered_at = datetime.now()
    if order_reference:
        recommendation.order_reference = order_reference
    
    db.commit()
    
    return {
        "message": "Öneri sipariş verildi olarak işaretlendi",
        "recommendation_id": recommendation_id
    }


@router.get("/history/{product_id}")
async def get_stock_history(
    product_id: str,
    days: int = 30,
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Session = Depends(get_db) if _db_available else None
):
    """Ürün stok geçmişini getirir"""
    if not _db_available:
        return {"history": [], "message": "Database not available (ghost mode)"}

    _check_db()

    date_filter = datetime.now() - timedelta(days=days)

    history = db.query(StockHistory).filter(
        and_(
            StockHistory.store_id == store.id,
            StockHistory.product_id == product_id,
            StockHistory.created_at >= date_filter
        )
    ).order_by(StockHistory.created_at.desc()).limit(100).all()
    
    return {
        "product_id": product_id,
        "history": [
            {
                "id": h.id,
                "previous_stock": h.previous_stock,
                "new_stock": h.new_stock,
                "change_amount": h.change_amount,
                "change_type": h.change_type,
                "reference_id": h.reference_id,
                "notes": h.notes,
                "created_at": h.created_at.isoformat() if h.created_at else ""
            }
            for h in history
        ]
    }

