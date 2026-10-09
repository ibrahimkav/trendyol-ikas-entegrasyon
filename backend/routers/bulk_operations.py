"""
Toplu İşlemler Router
Toplu fiyat güncelleme, stok güncelleme ve diğer toplu işlemler
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
from collections import defaultdict
from sqlalchemy.orm import Session

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


class BulkPriceUpdateRequest(BaseModel):
    """Toplu fiyat güncelleme isteği"""
    product_ids: Optional[List[str]] = None  # None = tüm ürünler
    category: Optional[str] = None  # Kategori filtresi
    update_type: str  # "percentage" veya "fixed"
    value: float  # Yüzde veya sabit miktar
    min_price: Optional[float] = None  # Minimum fiyat sınırı
    max_price: Optional[float] = None  # Maksimum fiyat sınırı


class BulkStockUpdateRequest(BaseModel):
    """Toplu stok güncelleme isteği"""
    product_ids: Optional[List[str]] = None
    category: Optional[str] = None
    update_type: str  # "set", "add", "subtract"
    value: int  # Stok değeri


class BulkOperationResponse(BaseModel):
    """Toplu işlem yanıtı"""
    success: bool
    message: str
    affected_products: int
    details: Optional[Dict[str, Any]] = None


def get_trendyol_orders_data(creds=None) -> List[Dict]:
    """Bu mağazanın Trendyol siparişlerini çeker (Wave3 kalıbı: per-store, env DEĞİL).
    NOT: creds=None → [] (henüz dönüştürülmemiş çağıranlar için güvenli köprü)."""
    if creds is None:
        return []
    try:
        return _fetch_store_orders(creds, max_pages=100, size=200)
    except Exception as e:
        print(f"[BulkOperations] Error fetching orders: {e}")
        return []


def get_all_products_from_orders(creds=None) -> Dict[str, Dict]:
    """Siparişlerden tüm ürünleri çıkarır"""
    orders = get_trendyol_orders_data(creds)
    products = {}
    
    for order in orders:
        lines = order.get("lines", []) or order.get("orderLines", []) or order.get("items", []) or []
        
        if isinstance(lines, dict):
            lines = [lines]
        
        for line in lines:
            try:
                # w3-hardening (2026-09-26): operatör önceliği hatası düzeltildi — bkz.
                # inventory.py/sync_service.py aynı fix (ternary parantezsizken or-zincirini
                # yutuyordu, "id" alanı yoksa TÜM ifade "" oluyordu).
                product_id = (
                    line.get("productId") or
                    line.get("product_id") or
                    line.get("barcode") or
                    line.get("sku") or
                    line.get("merchantSku") or
                    (str(line.get("id", "")) if line.get("id") else "")
                )
                
                if not product_id:
                    continue
                
                product_id_str = str(product_id)
                
                if product_id_str not in products:
                    products[product_id_str] = {
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
                        "current_price": 0.0,
                        "current_stock": 0
                    }
                
                # Fiyat bilgisini güncelle
                price = (
                    line.get("price", 0) or 
                    line.get("salePrice", 0) or 
                    line.get("unitPrice", 0) or
                    line.get("amount", 0) or
                    0
                )
                
                if isinstance(price, str):
                    try:
                        price = float(price.replace(",", "."))
                    except:
                        price = 0.0
                
                price = float(price) if price else 0.0
                
                if price > 0 and (products[product_id_str]["current_price"] == 0 or price < products[product_id_str]["current_price"]):
                    products[product_id_str]["current_price"] = price
                
            except Exception as e:
                continue
    
    return products


@router.get("/products")
async def get_products_for_bulk_operations(
    category: Optional[str] = None,
    search: Optional[str] = None,
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Session = Depends(get_db) if _db_available else None
):
    """Toplu işlemler için ürün listesi. w3-hardening: per-store credential."""
    try:
        creds = resolve_trendyol_creds(db, store)
        products = get_all_products_from_orders(creds)
        
        # Filtreleme
        filtered_products = {}
        for product_id, product in products.items():
            if category and product["category"].lower() != category.lower():
                continue
            if search and search.lower() not in product["product_name"].lower():
                continue
            filtered_products[product_id] = product
        
        return {
            "products": list(filtered_products.values()),
            "total": len(filtered_products)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ürünler yüklenemedi: {str(e)}")


@router.post("/price-update", response_model=BulkOperationResponse)
async def bulk_price_update(
    request: BulkPriceUpdateRequest,
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Session = Depends(get_db) if _db_available else None
):
    """
    Toplu fiyat güncelleme. w3-hardening: per-store credential.
    NOT: Bu endpoint simüle edilmiş bir işlemdir. Gerçek Trendyol API entegrasyonu için
    Trendyol'un ürün güncelleme API'sini kullanmanız gerekir.
    """
    try:
        creds = resolve_trendyol_creds(db, store)
        products = get_all_products_from_orders(creds)
        
        # Filtreleme
        filtered_products = {}
        for product_id, product in products.items():
            # Product ID filtresi
            if request.product_ids and product_id not in request.product_ids:
                continue
            
            # Kategori filtresi
            if request.category and product["category"].lower() != request.category.lower():
                continue
            
            # Fiyat aralığı filtresi
            current_price = product["current_price"]
            if request.min_price and current_price < request.min_price:
                continue
            if request.max_price and current_price > request.max_price:
                continue
            
            filtered_products[product_id] = product
        
        # Fiyat güncelleme simülasyonu
        updated_count = 0
        update_details = []
        
        for product_id, product in filtered_products.items():
            current_price = product["current_price"]
            
            if request.update_type == "percentage":
                new_price = current_price * (1 + request.value / 100)
            elif request.update_type == "fixed":
                new_price = current_price + request.value
            else:
                continue
            
            # Negatif fiyat kontrolü
            if new_price < 0:
                new_price = 0
            
            updated_count += 1
            update_details.append({
                "product_id": product_id,
                "product_name": product["product_name"],
                "old_price": round(current_price, 2),
                "new_price": round(new_price, 2),
                "change": round(new_price - current_price, 2),
                "change_percent": round(((new_price - current_price) / current_price * 100) if current_price > 0 else 0, 2)
            })
        
        return BulkOperationResponse(
            success=True,
            message=f"{updated_count} ürünün fiyatı güncellendi (simüle edildi)",
            affected_products=updated_count,
            details={
                "updates": update_details[:50],  # İlk 50 ürünü göster
                "total_updates": len(update_details)
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fiyat güncelleme hatası: {str(e)}")


@router.post("/stock-update", response_model=BulkOperationResponse)
async def bulk_stock_update(
    request: BulkStockUpdateRequest,
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Session = Depends(get_db) if _db_available else None
):
    """
    Toplu stok güncelleme. w3-hardening: per-store credential.
    NOT: Bu endpoint simüle edilmiş bir işlemdir. Gerçek Trendyol API entegrasyonu için
    Trendyol'un stok güncelleme API'sini kullanmanız gerekir.
    """
    try:
        creds = resolve_trendyol_creds(db, store)
        products = get_all_products_from_orders(creds)
        
        # Filtreleme
        filtered_products = {}
        for product_id, product in products.items():
            # Product ID filtresi
            if request.product_ids and product_id not in request.product_ids:
                continue
            
            # Kategori filtresi
            if request.category and product["category"].lower() != request.category.lower():
                continue
            
            filtered_products[product_id] = product
        
        # Stok güncelleme simülasyonu
        updated_count = 0
        update_details = []
        
        for product_id, product in filtered_products.items():
            current_stock = product.get("current_stock", 0)
            
            if request.update_type == "set":
                new_stock = request.value
            elif request.update_type == "add":
                new_stock = current_stock + request.value
            elif request.update_type == "subtract":
                new_stock = max(0, current_stock - request.value)
            else:
                continue
            
            # Negatif stok kontrolü
            if new_stock < 0:
                new_stock = 0
            
            updated_count += 1
            update_details.append({
                "product_id": product_id,
                "product_name": product["product_name"],
                "old_stock": current_stock,
                "new_stock": new_stock,
                "change": new_stock - current_stock
            })
        
        return BulkOperationResponse(
            success=True,
            message=f"{updated_count} ürünün stoku güncellendi (simüle edildi)",
            affected_products=updated_count,
            details={
                "updates": update_details[:50],  # İlk 50 ürünü göster
                "total_updates": len(update_details)
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stok güncelleme hatası: {str(e)}")


@router.get("/categories")
async def get_categories(
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Session = Depends(get_db) if _db_available else None
):
    """Tüm kategorileri listeler. w3-hardening: per-store credential."""
    try:
        creds = resolve_trendyol_creds(db, store)
        products = get_all_products_from_orders(creds)
        categories = set()
        
        for product in products.values():
            if product["category"]:
                categories.add(product["category"])
        
        return {
            "categories": sorted(list(categories)),
            "total": len(categories)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Kategoriler yüklenemedi: {str(e)}")


