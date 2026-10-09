"""
Export/Import Router
Excel ve CSV formatında veri export/import işlemleri
"""
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
import io
import csv
import json
import os

# Database modülünü optional olarak yükle (ghost mode)
try:
    from database.db import get_db
    from database.models import Product, Order, PriceHistory, Campaign, ReturnRefund, Store
    from security import get_current_store
    _db_available = True
except Exception:
    _db_available = False
    def get_db():
        raise HTTPException(status_code=503, detail="Database not available (ghost mode)")

    def get_current_store():
        raise HTTPException(status_code=503, detail="Database not available (ghost mode)")

router = APIRouter()


def _format_trendyol_date(raw) -> str:
    """Ham Trendyol tarih değerini (epoch-ms int veya ISO string) okunabilir formata çevirir.
    w3-backend-cleanup Madde 3: önceden ham epoch-ms int CSV/Excel'e olduğu gibi yazılıyordu."""
    if not raw:
        return ""
    try:
        if isinstance(raw, (int, float)):
            ts = float(raw)
            if ts > 1e12:
                ts = ts / 1000
            dt = datetime.fromtimestamp(ts)
        elif isinstance(raw, str):
            if 'T' in raw:
                dt = datetime.fromisoformat(raw.replace('Z', '+00:00'))
                if dt.tzinfo:
                    dt = dt.replace(tzinfo=None)
            else:
                dt = datetime.strptime(raw, "%Y-%m-%d")
        else:
            return str(raw)
        return dt.strftime("%d.%m.%Y %H:%M")
    except Exception:
        return str(raw)


def _check_db():
    """Database kontrolü - ghost mode"""
    if not _db_available:
        raise HTTPException(status_code=503, detail="Database not available (ghost mode)")


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


# ==================== EXPORT ENDPOINTS ====================

@router.get("/export/products/{format}")
async def export_products(
    format: str = "csv",  # "csv" veya "excel"
    db: Optional[Any] = None
):
    """
    Ürünleri export eder
    
    Args:
        format: Export formatı ("csv" veya "excel")
    """
    # Siparişlerden ürünleri çıkar
    orders = get_trendyol_orders_data()
    products = {}
    
    for order in orders:
        lines = order.get("lines", []) or order.get("orderLines", []) or order.get("items", []) or []
        
        if isinstance(lines, dict):
            lines = [lines]
        
        for line in lines:
            try:
                # Farklı alan adlarını dene (daha kapsamlı)
                product_id = None
                
                # Önce en yaygın alan adlarını dene (productCode öncelikli)
                # merchantSku ve stockCode bazen "merchantSku" string'i olabiliyor, bu yüzden kontrol et
                for key in ["productCode", "product_code", "productId", "product_id", "sku", "barcode", 
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
                
                if not product_id or product_id == "None" or product_id == "":
                    continue
                
                product_id_str = str(product_id)
                
                if product_id_str not in products:
                    products[product_id_str] = {
                        "product_id": product_id_str,
                        "product_name": (
                            line.get("productName") or 
                            line.get("product_name") or 
                            line.get("name") or 
                            "Bilinmeyen Ürün"
                        ),
                        "category": line.get("categoryName") or line.get("category_name") or "",
                        "barcode": line.get("barcode") or line.get("sku") or "",
                        "current_price": 0.0
                    }
                
                price = line.get("price", 0) or line.get("salePrice", 0) or line.get("unitPrice", 0) or 0
                if isinstance(price, str):
                    try:
                        price = float(price.replace(',', '.'))
                    except:
                        price = 0.0
                
                if price > 0:
                    products[product_id_str]["current_price"] = float(price)
            except Exception:
                continue
    
    # Database'den ek bilgiler ekle
    if _db_available:
        try:
            from sqlalchemy.orm import Session
            db: Session = Depends(get_db) if _db_available else None
            if db:
                for product_id, product_data in products.items():
                    db_product = db.query(Product).filter(Product.product_id == product_id).first()
                    if db_product:
                        product_data["current_price"] = db_product.current_price or product_data["current_price"]
        except Exception:
            pass
    
    # CSV Export
    if format.lower() == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Başlık
        writer.writerow([
            "Ürün ID", "Ürün Adı", "Kategori", "Barkod", "Fiyat"
        ])
        
        # Veriler
        for product in products.values():
            writer.writerow([
                product["product_id"],
                product["product_name"],
                product["category"],
                product["barcode"],
                product["current_price"]
            ])
        
        output.seek(0)
        filename = f"urunler_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        return StreamingResponse(
            iter([output.getvalue().encode('utf-8-sig')]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    
    # Excel Export
    elif format.lower() == "excel":
        try:
            import openpyxl
            from openpyxl import Workbook
            
            wb = Workbook()
            ws = wb.active
            ws.title = "Ürünler"
            
            # Başlık
            ws.append(["Ürün ID", "Ürün Adı", "Kategori", "Barkod", "Fiyat"])
            
            # Veriler
            for product in products.values():
                ws.append([
                    product["product_id"],
                    product["product_name"],
                    product["category"],
                    product["barcode"],
                    product["current_price"]
                ])
            
            # Dosyayı memory'de oluştur
            output = io.BytesIO()
            wb.save(output)
            output.seek(0)
            
            filename = f"urunler_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            
            return StreamingResponse(
                output,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )
        except ImportError:
            raise HTTPException(
                status_code=500,
                detail="Excel export için openpyxl paketi gerekli. 'pip install openpyxl' komutu ile yükleyin."
            )
    
    else:
        raise HTTPException(status_code=400, detail="Geçersiz format. 'csv' veya 'excel' olmalı.")


@router.get("/export/orders/{format}")
async def export_orders(
    format: str = "csv",
    days: int = 30
):
    """
    Siparişleri export eder
    
    Args:
        format: Export formatı ("csv" veya "excel")
        days: Son kaç günün siparişleri
    """
    orders = get_trendyol_orders_data()
    
    # Tarih filtresi
    from datetime import timedelta
    cutoff_date = datetime.now() - timedelta(days=days)
    
    filtered_orders = []
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
                    if order_date.tzinfo:
                        order_date = order_date.replace(tzinfo=None)
                else:
                    order_date = datetime.strptime(order_date_str, "%Y-%m-%d")

                if order_date >= cutoff_date:
                    filtered_orders.append(order)
        except Exception:
            continue
    
    # CSV Export
    if format.lower() == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Başlık
        writer.writerow([
            "Sipariş No", "Tarih", "Müşteri", "Durum", "Toplam Tutar", "Ürün Sayısı"
        ])
        
        # Veriler
        for order in filtered_orders:
            order_number = order.get("orderNumber") or order.get("id") or ""
            order_date = _format_trendyol_date(order.get("orderDate") or order.get("order_date") or "")
            customer_name = (
                (order.get("customerFirstName") or "") + " " + (order.get("customerLastName") or "")
            ).strip() or "Bilinmeyen"
            status = order.get("status") or order.get("orderStatus") or ""
            total_price = order.get("totalPrice") or order.get("totalPriceValue") or order.get("totalAmount") or 0.0
            
            lines = order.get("lines", []) or order.get("orderLines", []) or []
            if isinstance(lines, dict):
                lines = [lines]
            quantity = sum(line.get("quantity", 1) or 1 for line in lines)
            
            writer.writerow([
                order_number,
                order_date,
                customer_name,
                status,
                total_price,
                quantity
            ])
        
        output.seek(0)
        filename = f"siparisler_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        return StreamingResponse(
            iter([output.getvalue().encode('utf-8-sig')]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    
    # Excel Export
    elif format.lower() == "excel":
        try:
            import openpyxl
            from openpyxl import Workbook
            
            wb = Workbook()
            ws = wb.active
            ws.title = "Siparişler"
            
            # Başlık
            ws.append(["Sipariş No", "Tarih", "Müşteri", "Durum", "Toplam Tutar", "Ürün Sayısı"])
            
            # Veriler
            for order in filtered_orders:
                order_number = order.get("orderNumber") or order.get("id") or ""
                order_date = _format_trendyol_date(order.get("orderDate") or order.get("order_date") or "")
                customer_name = (
                    (order.get("customerFirstName") or "") + " " + (order.get("customerLastName") or "")
                ).strip() or "Bilinmeyen"
                status = order.get("status") or order.get("orderStatus") or ""
                total_price = order.get("totalPrice") or order.get("totalPriceValue") or order.get("totalAmount") or 0.0
                
                lines = order.get("lines", []) or order.get("orderLines", []) or []
                if isinstance(lines, dict):
                    lines = [lines]
                quantity = sum(line.get("quantity", 1) or 1 for line in lines)
                
                ws.append([
                    order_number,
                    order_date,
                    customer_name,
                    status,
                    total_price,
                    quantity
                ])
            
            output = io.BytesIO()
            wb.save(output)
            output.seek(0)
            
            filename = f"siparisler_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            
            return StreamingResponse(
                output,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )
        except ImportError:
            raise HTTPException(
                status_code=500,
                detail="Excel export için openpyxl paketi gerekli."
            )
    
    else:
        raise HTTPException(status_code=400, detail="Geçersiz format.")


@router.get("/export/inventory/{format}")
async def export_inventory(
    format: str = "csv",
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Any = Depends(get_db) if _db_available else None
):
    """Stok bilgilerini export eder"""
    # Inventory router'dan veri çek
    from routers.inventory import get_product_stock

    stock_data = await get_product_stock(include_out_of_stock=True, store=store, db=db)
    products = stock_data.get("products", [])
    
    if format.lower() == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        
        writer.writerow([
            "Ürün ID", "Ürün Adı", "Mevcut Stok", "Min. Stok", "Durum", "Kategori"
        ])
        
        for product in products:
            writer.writerow([
                product.get("product_id", ""),
                product.get("product_name", ""),
                product.get("current_stock", 0),
                product.get("min_stock_level", 0),
                product.get("status", ""),
                product.get("category", "")
            ])
        
        output.seek(0)
        filename = f"stok_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        return StreamingResponse(
            iter([output.getvalue().encode('utf-8-sig')]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    
    elif format.lower() == "excel":
        try:
            import openpyxl
            from openpyxl import Workbook
            
            wb = Workbook()
            ws = wb.active
            ws.title = "Stok"
            
            ws.append(["Ürün ID", "Ürün Adı", "Mevcut Stok", "Min. Stok", "Durum", "Kategori"])
            
            for product in products:
                ws.append([
                    product.get("product_id", ""),
                    product.get("product_name", ""),
                    product.get("current_stock", 0),
                    product.get("min_stock_level", 0),
                    product.get("status", ""),
                    product.get("category", "")
                ])
            
            output = io.BytesIO()
            wb.save(output)
            output.seek(0)
            
            filename = f"stok_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            
            return StreamingResponse(
                output,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )
        except ImportError:
            raise HTTPException(status_code=500, detail="Excel export için openpyxl gerekli.")
    
    else:
        raise HTTPException(status_code=400, detail="Geçersiz format.")


# ==================== IMPORT ENDPOINTS ====================

@router.post("/import/prices")
async def import_prices(
    file: UploadFile = File(...),
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Any = Depends(get_db) if _db_available else None
):
    """
    Excel/CSV dosyasından toplu fiyat güncellemesi yapar
    
    Dosya formatı:
    - Ürün ID (veya Barkod)
    - Yeni Fiyat
    """
    if not _db_available or db is None:
        raise HTTPException(status_code=503, detail="Database not available (ghost mode)")
    
    _check_db()
    
    content = await file.read()
    filename = file.filename.lower()
    
    results = {
        "success": 0,
        "failed": 0,
        "errors": []
    }
    
    try:
        # CSV dosyası
        if filename.endswith('.csv'):
            content_str = content.decode('utf-8-sig')
            reader = csv.DictReader(io.StringIO(content_str))
            
            for row in reader:
                try:
                    product_id = row.get("Ürün ID") or row.get("product_id") or row.get("Barkod") or row.get("barcode")
                    new_price = row.get("Yeni Fiyat") or row.get("new_price") or row.get("Fiyat") or row.get("price")
                    
                    if not product_id or not new_price:
                        results["failed"] += 1
                        results["errors"].append(f"Satır eksik: {row}")
                        continue
                    
                    try:
                        price_float = float(str(new_price).replace(',', '.'))
                    except:
                        results["failed"] += 1
                        results["errors"].append(f"Geçersiz fiyat: {new_price}")
                        continue
                    
                    # Fiyat geçmişine kaydet
                    from database.models import PriceHistory, Product
                    
                    try:
                        # Önceki fiyatı bul
                        last_record = db.query(PriceHistory).filter(
                            PriceHistory.store_id == store.id,
                            PriceHistory.product_id == str(product_id)
                        ).order_by(PriceHistory.created_at.desc()).first()

                        previous_price = last_record.new_price if last_record else price_float

                        # Ürün adını bul
                        product = db.query(Product).filter(Product.store_id == store.id, Product.product_id == str(product_id)).first()
                        product_name = product.product_name if product else "Unknown"

                        # Değişim hesapla
                        price_change = price_float - previous_price
                        price_change_percent = ((price_float - previous_price) / previous_price * 100) if previous_price > 0 else 0.0

                        # Yeni kayıt oluştur
                        new_record = PriceHistory(
                            store_id=store.id,
                            product_id=str(product_id),
                            product_name=product_name,
                            previous_price=previous_price,
                            new_price=price_float,
                            price_change=price_change,
                            price_change_percent=price_change_percent,
                            change_reason="import"
                        )

                        db.add(new_record)
                        db.commit()
                        results["success"] += 1
                    except Exception as e:
                        db.rollback()
                        results["failed"] += 1
                        results["errors"].append(f"Ürün {product_id}: {str(e)}")

                except Exception as e:
                    results["failed"] += 1
                    results["errors"].append(f"Satır işleme hatası: {str(e)}")

        # Excel dosyası
        elif filename.endswith(('.xlsx', '.xls')):
            try:
                import openpyxl
                from openpyxl import load_workbook
                
                wb = load_workbook(io.BytesIO(content))
                ws = wb.active
                
                # İlk satır başlık olmalı
                headers = [cell.value for cell in ws[1]]
                
                # Ürün ID ve Fiyat kolonlarını bul
                product_id_col = None
                price_col = None
                
                for idx, header in enumerate(headers):
                    header_str = str(header or "").lower()
                    if "ürün" in header_str and "id" in header_str or "barkod" in header_str:
                        product_id_col = idx + 1
                    if "fiyat" in header_str or "price" in header_str:
                        price_col = idx + 1
                
                if not product_id_col or not price_col:
                    raise HTTPException(
                        status_code=400,
                        detail="Dosyada 'Ürün ID' ve 'Fiyat' kolonları bulunamadı."
                    )
                
                # Verileri işle
                for row in ws.iter_rows(min_row=2, values_only=False):
                    try:
                        product_id = row[product_id_col - 1].value
                        new_price = row[price_col - 1].value
                        
                        if not product_id or not new_price:
                            continue
                        
                        try:
                            price_float = float(str(new_price).replace(',', '.'))
                        except:
                            results["failed"] += 1
                            results["errors"].append(f"Geçersiz fiyat: {new_price}")
                            continue
                        
                        # Fiyat geçmişine kaydet
                        from database.models import PriceHistory, Product
                        
                        try:
                            # Önceki fiyatı bul
                            last_record = db.query(PriceHistory).filter(
                                PriceHistory.store_id == store.id,
                                PriceHistory.product_id == str(product_id)
                            ).order_by(PriceHistory.created_at.desc()).first()

                            previous_price = last_record.new_price if last_record else price_float

                            # Ürün adını bul
                            product = db.query(Product).filter(Product.store_id == store.id, Product.product_id == str(product_id)).first()
                            product_name = product.product_name if product else "Unknown"

                            # Değişim hesapla
                            price_change = price_float - previous_price
                            price_change_percent = ((price_float - previous_price) / previous_price * 100) if previous_price > 0 else 0.0

                            # Yeni kayıt oluştur
                            new_record = PriceHistory(
                                store_id=store.id,
                                product_id=str(product_id),
                                product_name=product_name,
                                previous_price=previous_price,
                                new_price=price_float,
                                price_change=price_change,
                                price_change_percent=price_change_percent,
                                change_reason="import"
                            )
                            
                            db.add(new_record)
                            db.commit()
                            results["success"] += 1
                        except Exception as e:
                            db.rollback()
                            results["failed"] += 1
                            results["errors"].append(f"Ürün {product_id}: {str(e)}")
                            
                    except Exception as e:
                        results["failed"] += 1
                        results["errors"].append(f"Satır işleme hatası: {str(e)}")
                        
            except ImportError:
                raise HTTPException(status_code=500, detail="Excel import için openpyxl gerekli.")
        
        else:
            raise HTTPException(status_code=400, detail="Desteklenmeyen dosya formatı. CSV veya Excel (.xlsx) olmalı.")
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Dosya işleme hatası: {str(e)}")
    
    return {
        "message": f"İşlem tamamlandı. {results['success']} başarılı, {results['failed']} başarısız.",
        "results": results
    }


@router.get("/export/template/{data_type}")
async def get_import_template(data_type: str):
    """
    Import için şablon dosyası indirir
    
    Args:
        data_type: "prices" (fiyatlar), "products" (ürünler), "inventory" (stok)
    """
    if data_type == "prices":
        output = io.StringIO()
        writer = csv.writer(output)
        
        writer.writerow(["Ürün ID", "Yeni Fiyat"])
        writer.writerow(["ÖRNEK123", "99.99"])
        writer.writerow(["ÖRNEK456", "149.50"])
        
        output.seek(0)
        
        return StreamingResponse(
            iter([output.getvalue().encode('utf-8-sig')]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=ornek_fiyat_guncelleme.csv"}
        )
    
    else:
        raise HTTPException(status_code=400, detail="Geçersiz data_type. 'prices' olmalı.")

