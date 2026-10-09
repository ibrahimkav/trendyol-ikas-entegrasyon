"""
Ürün Görsel Eşleştirme Router
Manuel görsel URL mapping yönetimi
"""
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_
import json
import io
import requests
from pathlib import Path

router = APIRouter()

# Database modülünü optional olarak yükle
_db_available = False
try:
    from database.db import get_db, init_db
    from database.models import ProductImageMapping, Store
    from security import get_current_store
    try:
        init_db()
        _db_available = True
        print("[ProductImages] Database initialized successfully")
    except Exception as db_init_error:
        print(f"[ProductImages] Database initialization warning: {db_init_error}")
        _db_available = True
except Exception as import_error:
    print(f"[ProductImages] Database module not available (ghost mode): {import_error}")
    pass


def _check_db():
    """Database kontrolü"""
    if not _db_available:
        raise HTTPException(status_code=503, detail="Database not available (ghost mode)")


class ImageMappingRequest(BaseModel):
    """Görsel eşleştirme oluşturma/güncelleme isteği"""
    product_code: str
    barcode: Optional[str] = None
    content_id: Optional[str] = None
    product_name: Optional[str] = None
    image_urls: List[str]  # Görsel URL'leri listesi
    primary_image_url: Optional[str] = None  # Ana görsel URL
    notes: Optional[str] = None


class ImageMappingResponse(BaseModel):
    """Görsel eşleştirme yanıtı"""
    id: int
    product_code: str
    barcode: Optional[str]
    content_id: Optional[str]
    product_name: Optional[str]
    image_urls: List[str]
    primary_image_url: Optional[str]
    is_active: bool
    notes: Optional[str]
    created_at: str
    updated_at: str


@router.get("/", response_model=List[ImageMappingResponse])
async def get_all_image_mappings(
    active_only: bool = False,
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Session = Depends(get_db) if _db_available else None
):
    """Tüm görsel eşleştirmelerini listeler"""
    _check_db()

    try:
        query = db.query(ProductImageMapping).filter(ProductImageMapping.store_id == store.id)
        if active_only:
            query = query.filter(ProductImageMapping.is_active == True)
        
        mappings = query.order_by(ProductImageMapping.updated_at.desc()).all()
        
        result = []
        for mapping in mappings:
            image_urls = json.loads(mapping.image_urls) if mapping.image_urls else []
            result.append(ImageMappingResponse(
                id=mapping.id,
                product_code=mapping.product_code,
                barcode=mapping.barcode,
                content_id=mapping.content_id,
                product_name=mapping.product_name,
                image_urls=image_urls,
                primary_image_url=mapping.primary_image_url,
                is_active=mapping.is_active,
                notes=mapping.notes,
                created_at=mapping.created_at.isoformat() if mapping.created_at else "",
                updated_at=mapping.updated_at.isoformat() if mapping.updated_at else ""
            ))
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Görsel eşleştirmeleri getirilemedi: {str(e)}")


@router.get("/search")
async def search_image_mapping(
    product_code: Optional[str] = None,
    barcode: Optional[str] = None,
    content_id: Optional[str] = None,
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Session = Depends(get_db) if _db_available else None
):
    """Görsel eşleştirmesini ara (product_code, barcode veya content_id ile)"""
    _check_db()

    if not any([product_code, barcode, content_id]):
        raise HTTPException(status_code=400, detail="En az bir arama kriteri gerekli (product_code, barcode veya content_id)")

    try:
        query = db.query(ProductImageMapping).filter(ProductImageMapping.store_id == store.id, ProductImageMapping.is_active == True)
        
        conditions = []
        if product_code:
            conditions.append(ProductImageMapping.product_code == product_code)
        if barcode:
            conditions.append(ProductImageMapping.barcode == barcode)
        if content_id:
            conditions.append(ProductImageMapping.content_id == content_id)
        
        if conditions:
            query = query.filter(or_(*conditions))
        
        mapping = query.first()
        
        if not mapping:
            return {"found": False, "images": []}
        
        image_urls = json.loads(mapping.image_urls) if mapping.image_urls else []
        
        return {
            "found": True,
            "id": mapping.id,
            "product_code": mapping.product_code,
            "barcode": mapping.barcode,
            "content_id": mapping.content_id,
            "product_name": mapping.product_name,
            "images": image_urls,
            "primary_image_url": mapping.primary_image_url or (image_urls[0] if image_urls else None)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Görsel eşleştirmesi aranırken hata: {str(e)}")


@router.post("/", response_model=ImageMappingResponse)
async def create_image_mapping(
    request: ImageMappingRequest,
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Session = Depends(get_db) if _db_available else None
):
    """Yeni görsel eşleştirmesi oluştur"""
    _check_db()

    try:
        # Aynı product_code ile aktif mapping var mı kontrol et
        existing = db.query(ProductImageMapping).filter(
            ProductImageMapping.store_id == store.id,
            ProductImageMapping.product_code == request.product_code,
            ProductImageMapping.is_active == True
        ).first()

        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Bu product_code için zaten aktif bir eşleştirme var (ID: {existing.id})"
            )

        # Primary image URL belirlenmediyse, ilk görseli kullan
        primary_url = request.primary_image_url
        if not primary_url and request.image_urls:
            primary_url = request.image_urls[0]

        new_mapping = ProductImageMapping(
            store_id=store.id,
            product_code=request.product_code,
            barcode=request.barcode,
            content_id=request.content_id,
            product_name=request.product_name,
            image_urls=json.dumps(request.image_urls),
            primary_image_url=primary_url,
            notes=request.notes,
            is_active=True
        )
        
        db.add(new_mapping)
        db.commit()
        db.refresh(new_mapping)
        
        image_urls = json.loads(new_mapping.image_urls) if new_mapping.image_urls else []
        
        return ImageMappingResponse(
            id=new_mapping.id,
            product_code=new_mapping.product_code,
            barcode=new_mapping.barcode,
            content_id=new_mapping.content_id,
            product_name=new_mapping.product_name,
            image_urls=image_urls,
            primary_image_url=new_mapping.primary_image_url,
            is_active=new_mapping.is_active,
            notes=new_mapping.notes,
            created_at=new_mapping.created_at.isoformat() if new_mapping.created_at else "",
            updated_at=new_mapping.updated_at.isoformat() if new_mapping.updated_at else ""
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Görsel eşleştirmesi oluşturulamadı: {str(e)}")


@router.put("/{mapping_id}", response_model=ImageMappingResponse)
async def update_image_mapping(
    mapping_id: int,
    request: ImageMappingRequest,
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Session = Depends(get_db) if _db_available else None
):
    """Görsel eşleştirmesini güncelle"""
    _check_db()

    try:
        mapping = db.query(ProductImageMapping).filter(ProductImageMapping.store_id == store.id, ProductImageMapping.id == mapping_id).first()
        
        if not mapping:
            raise HTTPException(status_code=404, detail="Görsel eşleştirmesi bulunamadı")
        
        # Primary image URL belirlenmediyse, ilk görseli kullan
        primary_url = request.primary_image_url
        if not primary_url and request.image_urls:
            primary_url = request.image_urls[0]
        
        mapping.product_code = request.product_code
        mapping.barcode = request.barcode
        mapping.content_id = request.content_id
        mapping.product_name = request.product_name
        mapping.image_urls = json.dumps(request.image_urls)
        mapping.primary_image_url = primary_url
        mapping.notes = request.notes
        
        db.commit()
        db.refresh(mapping)
        
        image_urls = json.loads(mapping.image_urls) if mapping.image_urls else []
        
        return ImageMappingResponse(
            id=mapping.id,
            product_code=mapping.product_code,
            barcode=mapping.barcode,
            content_id=mapping.content_id,
            product_name=mapping.product_name,
            image_urls=image_urls,
            primary_image_url=mapping.primary_image_url,
            is_active=mapping.is_active,
            notes=mapping.notes,
            created_at=mapping.created_at.isoformat() if mapping.created_at else "",
            updated_at=mapping.updated_at.isoformat() if mapping.updated_at else ""
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Görsel eşleştirmesi güncellenemedi: {str(e)}")


@router.delete("/{mapping_id}")
async def delete_image_mapping(
    mapping_id: int,
    hard_delete: bool = False,
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Session = Depends(get_db) if _db_available else None
):
    """Görsel eşleştirmesini sil (soft delete veya hard delete)"""
    _check_db()

    try:
        mapping = db.query(ProductImageMapping).filter(ProductImageMapping.store_id == store.id, ProductImageMapping.id == mapping_id).first()
        
        if not mapping:
            raise HTTPException(status_code=404, detail="Görsel eşleştirmesi bulunamadı")
        
        if hard_delete:
            db.delete(mapping)
        else:
            mapping.is_active = False
        
        db.commit()
        
        return {"message": "Görsel eşleştirmesi silindi", "id": mapping_id}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Görsel eşleştirmesi silinemedi: {str(e)}")


@router.post("/bulk", response_model=List[ImageMappingResponse])
async def bulk_create_image_mappings(
    mappings: List[ImageMappingRequest],
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Session = Depends(get_db) if _db_available else None
):
    """Toplu görsel eşleştirmesi oluştur"""
    _check_db()

    try:
        created_mappings = []
        errors = []

        for request in mappings:
            try:
                # Aynı product_code ile aktif mapping var mı kontrol et
                existing = db.query(ProductImageMapping).filter(
                    ProductImageMapping.store_id == store.id,
                    ProductImageMapping.product_code == request.product_code,
                    ProductImageMapping.is_active == True
                ).first()

                if existing:
                    errors.append({
                        "product_code": request.product_code,
                        "error": "Zaten aktif bir eşleştirme var"
                    })
                    continue

                # Primary image URL belirlenmediyse, ilk görseli kullan
                primary_url = request.primary_image_url
                if not primary_url and request.image_urls:
                    primary_url = request.image_urls[0]

                new_mapping = ProductImageMapping(
                    store_id=store.id,
                    product_code=request.product_code,
                    barcode=request.barcode,
                    content_id=request.content_id,
                    product_name=request.product_name,
                    image_urls=json.dumps(request.image_urls),
                    primary_image_url=primary_url,
                    notes=request.notes,
                    is_active=True
                )
                
                db.add(new_mapping)
                created_mappings.append(new_mapping)
            except Exception as e:
                errors.append({
                    "product_code": request.product_code,
                    "error": str(e)
                })
        
        db.commit()
        
        # Refresh all created mappings
        for mapping in created_mappings:
            db.refresh(mapping)
        
        result = []
        for mapping in created_mappings:
            image_urls = json.loads(mapping.image_urls) if mapping.image_urls else []
            result.append(ImageMappingResponse(
                id=mapping.id,
                product_code=mapping.product_code,
                barcode=mapping.barcode,
                content_id=mapping.content_id,
                product_name=mapping.product_name,
                image_urls=image_urls,
                primary_image_url=mapping.primary_image_url,
                is_active=mapping.is_active,
                notes=mapping.notes,
                created_at=mapping.created_at.isoformat() if mapping.created_at else "",
                updated_at=mapping.updated_at.isoformat() if mapping.updated_at else ""
            ))
        
        return {
            "created": result,
            "errors": errors,
            "success_count": len(result),
            "error_count": len(errors)
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Toplu görsel eşleştirmesi oluşturulamadı: {str(e)}")


@router.post("/auto-sync")
async def auto_sync_image_mappings(
    overwrite_existing: bool = False,
    download_images: bool = True,  # Görselleri fiziksel olarak da indir
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Session = Depends(get_db) if _db_available else None
):
    """
    Siparişlerden otomatik olarak görsel eşleştirmeleri oluşturur.
    Sipariş satırlarından görsel URL'lerini çıkarır, mapping'e ekler ve fiziksel olarak indirir.
    """
    _check_db()
    
    try:
        # Trendyol siparişlerini çek
        from routers.products import get_trendyol_orders_data
        orders = get_trendyol_orders_data()
        
        if not orders:
            return {
                "message": "Sipariş bulunamadı",
                "created": 0,
                "updated": 0,
                "skipped": 0,
                "downloaded": 0,
                "errors": []
            }
        
        created_count = 0
        updated_count = 0
        skipped_count = 0
        downloaded_count = 0
        errors = []
        processed_products = {}  # product_code -> mapping data
        
        # Tüm siparişleri işle
        for order in orders:
            lines = (
                order.get("lines") or 
                order.get("orderLines") or 
                order.get("items") or 
                order.get("lineItems") or
                order.get("orderItems") or
                []
            )
            
            if isinstance(lines, dict):
                lines = [lines]
            
            for line in lines:
                try:
                    product_code = line.get("productCode") or line.get("productId")
                    if not product_code:
                        continue
                    
                    product_code_str = str(product_code)
                    barcode = line.get("barcode") or line.get("sku")
                    content_id = line.get("contentId")
                    product_name = line.get("productName") or line.get("product_name")
                    
                    # Görsel URL'lerini çıkar - tüm olası alanları kontrol et
                    image_urls = []
                    
                    # Direkt görsel alanlarını kontrol et
                    image_fields = [
                        "productImage", "imageUrl", "productImageUrl", "image", 
                        "thumbnail", "thumbnailUrl", "mediaUrl", "images",
                        "productImageList", "mediaUrls", "imageList", "productImages"
                    ]
                    
                    for img_key in image_fields:
                        img_value = line.get(img_key)
                        if img_value:
                            if isinstance(img_value, str) and img_value.startswith("http"):
                                if img_value not in image_urls:
                                    image_urls.append(img_value)
                            elif isinstance(img_value, list):
                                for img in img_value:
                                    if isinstance(img, str) and img.startswith("http") and img not in image_urls:
                                        image_urls.append(img)
                                    elif isinstance(img, dict):
                                        img_url = (
                                            img.get("url") or 
                                            img.get("imageUrl") or 
                                            img.get("src") or
                                            img.get("originalUrl") or
                                            img.get("zoomUrl")
                                        )
                                        if img_url and isinstance(img_url, str) and img_url.startswith("http") and img_url not in image_urls:
                                            image_urls.append(img_url)
                    
                    # Nested objelerden de görsel çıkar
                    for key, value in line.items():
                        if isinstance(value, (list, dict)):
                            def extract_urls_from_nested(obj, depth=0):
                                if depth > 3:
                                    return []
                                urls = []
                                if isinstance(obj, dict):
                                    for k, v in obj.items():
                                        if isinstance(v, str) and v.startswith("http") and "cdn.dsmcdn.com" in v:
                                            urls.append(v)
                                        elif isinstance(v, (dict, list)):
                                            urls.extend(extract_urls_from_nested(v, depth + 1))
                                elif isinstance(obj, list):
                                    for item in obj:
                                        urls.extend(extract_urls_from_nested(item, depth + 1))
                                return urls
                            
                            nested_urls = extract_urls_from_nested(value)
                            for url in nested_urls:
                                if url not in image_urls:
                                    image_urls.append(url)
                    
                    # Eğer görsel bulunduysa, mapping'e ekle
                    if image_urls:
                        # Aynı product_code için daha fazla görsel varsa, birleştir
                        if product_code_str in processed_products:
                            existing_urls = processed_products[product_code_str]["image_urls"]
                            for url in image_urls:
                                if url not in existing_urls:
                                    existing_urls.append(url)
                        else:
                            processed_products[product_code_str] = {
                                "product_code": product_code_str,
                                "barcode": str(barcode) if barcode and barcode != "merchantSku" else None,
                                "content_id": str(content_id) if content_id else None,
                                "product_name": product_name,
                                "image_urls": image_urls
                            }
                except Exception as e:
                    errors.append({
                        "product_code": str(line.get("productCode", "bilinmeyen")),
                        "error": str(e)
                    })
                    continue
        
        # Görselleri indir ve database'e kaydet
        import requests
        from pathlib import Path
        from routers.images import UPLOAD_DIR, get_image_path
        
        for product_code_str, product_data in processed_products.items():
            try:
                # Mevcut mapping'i kontrol et
                existing = db.query(ProductImageMapping).filter(
                    ProductImageMapping.store_id == store.id,
                    ProductImageMapping.product_code == product_code_str,
                    ProductImageMapping.is_active == True
                ).first()

                # Görselleri indir (eğer isteniyorsa)
                downloaded_urls = product_data["image_urls"]
                if download_images:
                    downloaded_urls = []
                    for idx, img_url in enumerate(product_data["image_urls"]):
                        try:
                            # Görseli indir
                            response = requests.get(img_url, timeout=10, headers={
                                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                                "Referer": "https://www.trendyol.com/"
                            }, stream=True)
                            
                            if response.status_code == 200:
                                # Dosya uzantısını belirle
                                content_type = response.headers.get("content-type", "image/jpeg")
                                ext = ".jpg"
                                if "png" in content_type:
                                    ext = ".png"
                                elif "webp" in content_type:
                                    ext = ".webp"
                                elif "gif" in content_type:
                                    ext = ".gif"
                                
                                # Dosya adı oluştur
                                filename = f"trendyol_{idx + 1}{ext}"
                                image_path = get_image_path(product_code_str, filename)
                                
                                # Görseli kaydet
                                with open(image_path, "wb") as f:
                                    for chunk in response.iter_content(chunk_size=8192):
                                        f.write(chunk)
                                
                                # Yerel URL oluştur
                                local_url = f"/api/images/{product_code_str}/{filename}"
                                downloaded_urls.append(local_url)
                                downloaded_count += 1
                            else:
                                # İndirilemediyse orijinal URL'i kullan
                                downloaded_urls.append(img_url)
                        except Exception as e:
                            # Hata durumunda orijinal URL'i kullan
                            downloaded_urls.append(img_url)
                            import sys
                            print(f"[AutoSync] Görsel indirme hatası ({product_code_str}): {e}", file=sys.stderr)
                
                if existing:
                    if overwrite_existing:
                        # Güncelle
                        existing.image_urls = json.dumps(downloaded_urls if download_images else product_data["image_urls"])
                        existing.primary_image_url = downloaded_urls[0] if downloaded_urls else (product_data["image_urls"][0] if product_data["image_urls"] else None)
                        if product_data["product_name"]:
                            existing.product_name = product_data["product_name"]
                        if product_data["barcode"]:
                            existing.barcode = product_data["barcode"]
                        if product_data["content_id"]:
                            existing.content_id = product_data["content_id"]
                        updated_count += 1
                    else:
                        skipped_count += 1
                else:
                    # Yeni oluştur
                    new_mapping = ProductImageMapping(
                        store_id=store.id,
                        product_code=product_data["product_code"],
                        barcode=product_data["barcode"],
                        content_id=product_data["content_id"],
                        product_name=product_data["product_name"],
                        image_urls=json.dumps(downloaded_urls if download_images else product_data["image_urls"]),
                        primary_image_url=downloaded_urls[0] if downloaded_urls else (product_data["image_urls"][0] if product_data["image_urls"] else None),
                        is_active=True
                    )
                    db.add(new_mapping)
                    created_count += 1
            except Exception as e:
                errors.append({
                    "product_code": product_code_str,
                    "error": str(e)
                })
        
        db.commit()
        
        return {
            "message": f"Otomatik senkronizasyon tamamlandı",
            "created": created_count,
            "updated": updated_count,
            "skipped": skipped_count,
            "downloaded": downloaded_count,
            "total_products": len(processed_products),
            "errors": errors,
            "error_count": len(errors)
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Otomatik senkronizasyon hatası: {str(e)}")


@router.post("/import-excel")
async def import_excel_and_fetch_images(
    file: UploadFile = File(...),
    download_images: bool = True,
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Session = Depends(get_db) if _db_available else None
):
    """
    Excel dosyasından ürün bilgilerini okuyup Trendyol API'den görselleri çeker ve veritabanına kaydeder.
    Excel dosyasında Product Code, Barcode, Content ID gibi alanlar olmalı.
    """
    _check_db()
    
    try:
        # Dosya içeriğini oku
        content = await file.read()
        filename = file.filename.lower()
        
        if not (filename.endswith('.xlsx') or filename.endswith('.xls')):
            raise HTTPException(status_code=400, detail="Sadece Excel dosyaları (.xlsx, .xls) desteklenir")
        
        # Excel dosyasını aç
        try:
            import openpyxl
            from openpyxl import load_workbook
            
            wb = load_workbook(io.BytesIO(content))
            ws = wb.active
            
            # İlk satır başlık olmalı
            headers = [str(cell.value or "").strip() for cell in ws[1]]
            
            # Kolon indekslerini bul
            product_code_col = None
            barcode_col = None
            content_id_col = None
            product_name_col = None
            image_url_col = None
            
            for idx, header in enumerate(headers):
                header_lower = header.lower()
                if "product" in header_lower and "code" in header_lower:
                    product_code_col = idx
                elif "barcode" in header_lower or "barkod" in header_lower:
                    barcode_col = idx
                elif "content" in header_lower and "id" in header_lower:
                    content_id_col = idx
                elif "product" in header_lower and "name" in header_lower or "ürün" in header_lower and "ad" in header_lower:
                    product_name_col = idx
                elif "image" in header_lower or "görsel" in header_lower or "resim" in header_lower:
                    image_url_col = idx
            
            if product_code_col is None and barcode_col is None and content_id_col is None:
                raise HTTPException(
                    status_code=400,
                    detail="Excel dosyasında 'Product Code', 'Barcode' veya 'Content ID' kolonlarından biri bulunmalı"
                )
            
            # Verileri işle
            created_count = 0
            updated_count = 0
            skipped_count = 0
            downloaded_count = 0
            errors = []
            
            # Görsel kaydetme için path fonksiyonu
            def get_image_path(product_id: str, filename: str) -> Path:
                """Ürün görseli için dosya yolu oluşturur"""
                from routers.images import UPLOAD_DIR
                product_dir = UPLOAD_DIR / product_id
                product_dir.mkdir(parents=True, exist_ok=True)
                return product_dir / filename
            
            for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
                try:
                    # Satır verilerini al
                    product_code = str(row[product_code_col]).strip() if product_code_col is not None and row[product_code_col] else None
                    barcode = str(row[barcode_col]).strip() if barcode_col is not None and row[barcode_col] else None
                    content_id = str(row[content_id_col]).strip() if content_id_col is not None and row[content_id_col] else None
                    product_name = str(row[product_name_col]).strip() if product_name_col is not None and row[product_name_col] else None
                    image_url = str(row[image_url_col]).strip() if image_url_col is not None and row[image_url_col] else None
                    
                    # Boş satırları atla
                    if not product_code and not barcode and not content_id:
                        continue
                    
                    # Eğer Excel'de görsel URL varsa, onu kullan
                    image_urls = []
                    if image_url and image_url.startswith("http"):
                        image_urls = [image_url]
                    else:
                        # Trendyol API'den görselleri çek
                        search_terms = []
                        if barcode and barcode != "merchantSku" and barcode.lower() != "none":
                            search_terms.append(("barcode", barcode))
                        if product_code and product_code.lower() != "none":
                            search_terms.append(("productCode", product_code))
                        if content_id and content_id.lower() != "none":
                            search_terms.append(("contentId", content_id))
                        
                        # Trendyol API'den görselleri çek
                        for search_type, search_value in search_terms:
                            try:
                                # Trendyol Public API'yi dene
                                if search_type == "barcode":
                                    api_url = f"https://public.trendyol.com/discovery-web-productgw-service/api/product/{search_value}"
                                else:
                                    # Product Code veya Content ID için farklı endpoint
                                    api_url = f"https://public.trendyol.com/discovery-web-productgw-service/api/product/{search_value}"
                                
                                response = requests.get(api_url, timeout=10, headers={
                                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                                    "Referer": "https://www.trendyol.com/"
                                })
                                
                                if response.status_code == 200:
                                    data = response.json()
                                    product_data = data.get("result", {}) or data.get("data", {}) or data
                                    
                                    # Görsel URL'lerini çıkar
                                    images_data = (
                                        product_data.get("images", []) or 
                                        product_data.get("imageUrls", []) or 
                                        product_data.get("mediaUrls", []) or
                                        []
                                    )
                                    
                                    for img in images_data:
                                        if isinstance(img, str) and img.startswith("http") and img not in image_urls:
                                            image_urls.append(img)
                                        elif isinstance(img, dict):
                                            img_url = (
                                                img.get("url") or 
                                                img.get("imageUrl") or 
                                                img.get("src") or
                                                img.get("originalUrl") or
                                                img.get("zoomUrl")
                                            )
                                            if img_url and isinstance(img_url, str) and img_url.startswith("http") and img_url not in image_urls:
                                                image_urls.append(img_url)
                                    
                                    # Eğer görsel bulunduysa, diğer aramaları atla
                                    if image_urls:
                                        break
                            except Exception as e:
                                import sys
                                print(f"[ImportExcel] API hatası ({search_type}={search_value}): {e}", file=sys.stderr)
                                continue
                        
                        # Eğer API'den görsel bulunamadıysa, contentId ile CDN URL oluştur
                        if not image_urls and content_id:
                            try:
                                cdn_url = f"https://cdn.dsmcdn.com/mnresize/1200/1200/ty{content_id}.jpg"
                                # URL'in geçerli olup olmadığını kontrol et
                                test_response = requests.head(cdn_url, timeout=5)
                                if test_response.status_code == 200:
                                    image_urls.append(cdn_url)
                            except:
                                pass
                    
                    # Eğer görsel bulunduysa, veritabanına kaydet
                    if image_urls:
                        # Product code'u belirle (öncelikli)
                        primary_product_code = product_code or barcode or content_id
                        
                        # Mevcut mapping'i kontrol et
                        existing = None
                        if primary_product_code:
                            existing = db.query(ProductImageMapping).filter(
                                ProductImageMapping.store_id == store.id,
                                or_(
                                    ProductImageMapping.product_code == str(primary_product_code),
                                    ProductImageMapping.barcode == str(primary_product_code) if barcode else False,
                                    ProductImageMapping.content_id == str(primary_product_code) if content_id else False
                                ),
                                ProductImageMapping.is_active == True
                            ).first()
                        
                        # Görselleri indir (eğer isteniyorsa)
                        final_urls = image_urls
                        if download_images:
                            downloaded_urls = []
                            for idx, img_url in enumerate(image_urls):
                                try:
                                    response = requests.get(img_url, timeout=10, headers={
                                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                                        "Referer": "https://www.trendyol.com/"
                                    }, stream=True)
                                    
                                    if response.status_code == 200:
                                        # Dosya uzantısını belirle
                                        content_type = response.headers.get("content-type", "image/jpeg")
                                        ext = ".jpg"
                                        if "png" in content_type:
                                            ext = ".png"
                                        elif "webp" in content_type:
                                            ext = ".webp"
                                        elif "gif" in content_type:
                                            ext = ".gif"
                                        
                                        # Dosya adı oluştur
                                        filename_img = f"trendyol_{idx + 1}{ext}"
                                        image_path = get_image_path(str(primary_product_code), filename_img)
                                        
                                        # Görseli kaydet
                                        with open(image_path, "wb") as f:
                                            for chunk in response.iter_content(chunk_size=8192):
                                                f.write(chunk)
                                        
                                        # Yerel URL oluştur
                                        local_url = f"/api/images/{primary_product_code}/{filename_img}"
                                        downloaded_urls.append(local_url)
                                        downloaded_count += 1
                                    else:
                                        downloaded_urls.append(img_url)
                                except Exception as e:
                                    downloaded_urls.append(img_url)
                                    import sys
                                    print(f"[ImportExcel] Görsel indirme hatası: {e}", file=sys.stderr)
                            
                            final_urls = downloaded_urls if downloaded_urls else image_urls
                        
                        if existing:
                            # Güncelle
                            existing.image_urls = json.dumps(final_urls)
                            existing.primary_image_url = final_urls[0] if final_urls else None
                            if product_name:
                                existing.product_name = product_name
                            if barcode:
                                existing.barcode = barcode
                            if content_id:
                                existing.content_id = content_id
                            updated_count += 1
                        else:
                            # Yeni oluştur
                            new_mapping = ProductImageMapping(
                                store_id=store.id,
                                product_code=str(primary_product_code),
                                barcode=barcode if barcode and barcode.lower() != "none" else None,
                                content_id=content_id if content_id and content_id.lower() != "none" else None,
                                product_name=product_name if product_name and product_name.lower() != "none" else None,
                                image_urls=json.dumps(final_urls),
                                primary_image_url=final_urls[0] if final_urls else None,
                                is_active=True
                            )
                            db.add(new_mapping)
                            created_count += 1
                    else:
                        skipped_count += 1
                        errors.append({
                            "row": row_idx,
                            "product_code": product_code or barcode or content_id,
                            "error": "Görsel bulunamadı"
                        })
                        
                except Exception as e:
                    errors.append({
                        "row": row_idx,
                        "error": str(e)
                    })
                    import sys
                    print(f"[ImportExcel] Satır {row_idx} hatası: {e}", file=sys.stderr)
            
            db.commit()
            
            return {
                "message": "Excel import tamamlandı",
                "created": created_count,
                "updated": updated_count,
                "skipped": skipped_count,
                "downloaded": downloaded_count,
                "total_rows": ws.max_row - 1,
                "errors": errors[:50],  # İlk 50 hatayı göster
                "error_count": len(errors)
            }
            
        except ImportError:
            raise HTTPException(
                status_code=500,
                detail="Excel import için openpyxl paketi gerekli. 'pip install openpyxl' komutu ile yükleyin."
            )
    except Exception as e:
        if _db_available and db:
            db.rollback()
        raise HTTPException(status_code=500, detail=f"Excel import hatası: {str(e)}")


@router.post("/sync-from-trendyol")
async def sync_products_from_trendyol(
    download_images: bool = True,
    use_orders_fallback: bool = True,  # 403 hatası alırsa siparişlerden çek
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Session = Depends(get_db) if _db_available else None
):
    """
    Trendyol API'den tüm ürünleri çekip görsellerini veritabanına kaydeder.
    Products API'ye erişim yoksa siparişlerden çeker.
    """
    _check_db()
    
    try:
        import os
        import requests
        import base64
        
        api_key = os.getenv("TRENDYOL_API_KEY")
        api_secret = os.getenv("TRENDYOL_API_SECRET")
        supplier_id = os.getenv("TRENDYOL_SUPPLIER_ID")
        
        if not all([api_key, api_secret, supplier_id]):
            raise HTTPException(
                status_code=400,
                detail="Trendyol API credentials eksik. Lütfen .env dosyasını kontrol edin."
            )
        
        all_products = []
        products_api_available = False
        
        # Önce Products API'yi dene
        try:
            url = f"https://api.trendyol.com/sapigw/suppliers/{supplier_id}/products"
            
            auth_string = f"{api_key}:{api_secret}"
            auth_bytes = auth_string.encode('ascii')
            auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
            
            headers = {
                "Authorization": f"Basic {auth_b64}",
                "Content-Type": "application/json",
                "User-Agent": "Trendyol-AI-Assistant/1.0"
            }
            
            page = 0
            page_size = 500
            
            # Tüm sayfaları çek
            while True:
                params = {
                    "page": page,
                    "size": page_size,
                    "approved": "true"
                }
                
                response = requests.get(url, headers=headers, params=params, timeout=30)
                
                if response.status_code == 403:
                    # 403 hatası alırsak, siparişlerden çekmeye geç
                    import sys
                    print(f"[SyncTrendyol] Products API 403 hatası, siparişlerden çekiliyor...", file=sys.stderr)
                    products_api_available = False
                    break
                
                if response.status_code != 200:
                    import sys
                    print(f"[SyncTrendyol] API hatası (sayfa {page}): {response.status_code}", file=sys.stderr)
                    break
                
                data = response.json()
                items = data.get("content", []) or data.get("items", []) or []
                
                if not items:
                    break
                
                all_products.extend(items)
                products_api_available = True
                
                if len(items) < page_size:
                    break
                
                page += 1
                
                # Güvenlik için maksimum sayfa limiti
                if page > 100:
                    break
        except Exception as e:
            import sys
            print(f"[SyncTrendyol] Products API hatası: {e}", file=sys.stderr)
            products_api_available = False
        
        # Eğer Products API'den veri çekilemediyse, siparişlerden çek
        if not all_products and use_orders_fallback:
            import sys
            print(f"[SyncTrendyol] Siparişlerden ürün bilgileri çekiliyor...", file=sys.stderr)
            
            from routers.products import get_trendyol_orders_data
            orders = get_trendyol_orders_data()
            
            # Siparişlerden ürünleri çıkar
            seen_products = {}  # Duplicate kontrolü için
            
            for order in orders:
                lines = (
                    order.get("lines") or 
                    order.get("orderLines") or 
                    order.get("items") or 
                    order.get("lineItems") or
                    order.get("orderItems") or
                    []
                )
                
                if isinstance(lines, dict):
                    lines = [lines]
                
                for line in lines:
                    product_code = line.get("productCode") or line.get("productId")
                    barcode = line.get("barcode") or line.get("sku")
                    content_id = line.get("contentId")
                    
                    # Unique key oluştur
                    unique_key = product_code or barcode or content_id
                    if not unique_key or unique_key in seen_products:
                        continue
                    
                    seen_products[unique_key] = True
                    
                    # Ürün objesi oluştur
                    product_item = {
                        "productCode": product_code,
                        "barcode": barcode,
                        "contentId": content_id,
                        "productName": line.get("productName") or line.get("product_name"),
                        "merchantSku": line.get("merchantSku"),
                        "sku": line.get("sku")
                    }
                    
                    all_products.append(product_item)
        
        if not all_products:
            return {
                "message": "Trendyol API'den ürün bulunamadı",
                "created": 0,
                "updated": 0,
                "skipped": 0,
                "downloaded": 0,
                "total_products": 0,
                "errors": []
            }
        
        created_count = 0
        updated_count = 0
        skipped_count = 0
        downloaded_count = 0
        errors = []
        
        # Görsel kaydetme için path fonksiyonu
        def get_image_path(product_id: str, filename: str) -> Path:
            """Ürün görseli için dosya yolu oluşturur"""
            from routers.images import UPLOAD_DIR
            product_dir = UPLOAD_DIR / product_id
            product_dir.mkdir(parents=True, exist_ok=True)
            return product_dir / filename
        
        # Her ürünü işle
        for item in all_products:
            try:
                # Ürün bilgilerini çıkar
                product_code = None
                barcode = None
                content_id = None
                product_name = None
                
                # Product Code
                for key in ["productCode", "product_code", "productId", "product_id", "merchantSku", "sku"]:
                    value = item.get(key)
                    if value:
                        val_str = str(value).strip()
                        if val_str and val_str.lower() not in ["merchantsku", "stockcode", "none"]:
                            product_code = val_str
                            break
                
                # Barcode
                barcode_value = item.get("barcode") or item.get("barcodeNumber")
                if barcode_value:
                    barcode_str = str(barcode_value).strip()
                    if barcode_str and barcode_str.lower() not in ["merchantsku", "none"]:
                        barcode = barcode_str
                
                # Content ID
                content_id_value = item.get("contentId") or item.get("content_id")
                if content_id_value:
                    content_id = str(content_id_value).strip()
                
                # Product Name
                product_name = (
                    item.get("productName") or 
                    item.get("product_name") or 
                    item.get("title") or 
                    item.get("name") or
                    None
                )
                
                if not product_code and not barcode and not content_id:
                    skipped_count += 1
                    continue
                
                # Görsel URL'lerini çıkar
                image_urls = []
                
                # Önce direkt görsel alanlarını kontrol et
                image_fields = [
                    "images", "productImages", "mediaUrls", "imageUrls",
                    "imageList", "productImageList", "mediaList",
                    "mainImage", "thumbnailImage", "image", "productImage",
                    "imageUrl", "productImageUrl", "mediaUrl"
                ]
                
                for img_key in image_fields:
                    img_value = item.get(img_key)
                    if img_value:
                        if isinstance(img_value, str) and img_value.startswith("http"):
                            if img_value not in image_urls:
                                image_urls.append(img_value)
                        elif isinstance(img_value, list):
                            for img in img_value:
                                if isinstance(img, str) and img.startswith("http") and img not in image_urls:
                                    image_urls.append(img)
                                elif isinstance(img, dict):
                                    img_url = (
                                        img.get("url") or 
                                        img.get("imageUrl") or 
                                        img.get("src") or
                                        img.get("originalUrl") or
                                        img.get("zoomUrl")
                                    )
                                    if img_url and isinstance(img_url, str) and img_url.startswith("http") and img_url not in image_urls:
                                        image_urls.append(img_url)
                
                # Eğer görsel bulunamadıysa, contentId ile CDN URL oluştur (öncelikli)
                if not image_urls and content_id:
                    try:
                        # Trendyol CDN formatı: https://cdn.dsmcdn.com/mnresize/{width}/{height}/ty{contentId}.jpg
                        # Farklı boyutlarda görselleri dene
                        cdn_formats = [
                            f"https://cdn.dsmcdn.com/mnresize/1200/1200/ty{content_id}.jpg",
                            f"https://cdn.dsmcdn.com/mnresize/800/800/ty{content_id}.jpg",
                            f"https://cdn.dsmcdn.com/mnresize/600/600/ty{content_id}.jpg",
                            f"https://cdn.dsmcdn.com/mnresize/400/400/ty{content_id}.jpg",
                            f"https://cdn.dsmcdn.com/mnresize/200/200/ty{content_id}.jpg",
                            f"https://cdn.dsmcdn.com/mnresize/1200/1200/ty{content_id}.webp",
                            f"https://cdn.dsmcdn.com/mnresize/800/800/ty{content_id}.webp"
                        ]
                        
                        # İlk geçerli URL'i bul
                        for cdn_url in cdn_formats:
                            try:
                                test_response = requests.head(cdn_url, timeout=5, allow_redirects=True)
                                if test_response.status_code == 200:
                                    image_urls.append(cdn_url)
                                    # İlk görseli bulduktan sonra diğer formatları da ekle (farklı boyutlar)
                                    for alt_url in cdn_formats[cdn_formats.index(cdn_url)+1:]:
                                        if alt_url not in image_urls:
                                            image_urls.append(alt_url)
                                    break
                            except:
                                continue
                    except Exception as e:
                        import sys
                        print(f"[SyncTrendyol] CDN URL oluşturma hatası: {e}", file=sys.stderr)
                
                # Eğer hala görsel bulunamadıysa, Public API'yi dene (son çare, DNS hatası olabilir)
                if not image_urls:
                    search_terms = []
                    if barcode and barcode != "merchantSku":
                        search_terms.append(("barcode", barcode))
                    if product_code:
                        search_terms.append(("productCode", product_code))
                    if content_id:
                        search_terms.append(("contentId", content_id))
                    
                    # Public API'yi sadece son çare olarak dene (DNS hatası olabilir)
                    for search_type, search_value in search_terms[:1]:  # Sadece ilkini dene (zaman tasarrufu)
                        try:
                            # Trendyol Public API'yi dene (DNS hatası olabilir, bu yüzden try-except içinde)
                            api_url = f"https://public.trendyol.com/discovery-web-productgw-service/api/product/{search_value}"
                            response = requests.get(api_url, timeout=5, headers={
                                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                                "Referer": "https://www.trendyol.com/"
                            })
                            
                            if response.status_code == 200:
                                data = response.json()
                                product_data = data.get("result", {}) or data.get("data", {}) or data
                                
                                images_data = (
                                    product_data.get("images", []) or 
                                    product_data.get("imageUrls", []) or 
                                    product_data.get("mediaUrls", []) or
                                    []
                                )
                                
                                for img in images_data:
                                    if isinstance(img, str) and img.startswith("http") and img not in image_urls:
                                        image_urls.append(img)
                                    elif isinstance(img, dict):
                                        img_url = (
                                            img.get("url") or 
                                            img.get("imageUrl") or 
                                            img.get("src") or
                                            img.get("originalUrl") or
                                            img.get("zoomUrl")
                                        )
                                        if img_url and isinstance(img_url, str) and img_url.startswith("http") and img_url not in image_urls:
                                            image_urls.append(img_url)
                                
                                if image_urls:
                                    break
                        except Exception as e:
                            # DNS hatası veya bağlantı hatası - sessizce geç (CDN URL zaten denenmiş)
                            # Hata mesajını yazdırma, CDN URL'leri zaten kullanılıyor
                            continue
                
                # Primary product code belirle
                primary_product_code = product_code or barcode or content_id
                
                if not primary_product_code:
                    skipped_count += 1
                    continue
                
                # Görselleri indir (eğer isteniyorsa)
                final_urls = image_urls
                if download_images and image_urls:
                    downloaded_urls = []
                    for idx, img_url in enumerate(image_urls):
                        try:
                            response = requests.get(img_url, timeout=10, headers={
                                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                                "Referer": "https://www.trendyol.com/"
                            }, stream=True)
                            
                            if response.status_code == 200:
                                content_type = response.headers.get("content-type", "image/jpeg")
                                ext = ".jpg"
                                if "png" in content_type:
                                    ext = ".png"
                                elif "webp" in content_type:
                                    ext = ".webp"
                                elif "gif" in content_type:
                                    ext = ".gif"
                                
                                filename_img = f"trendyol_{idx + 1}{ext}"
                                image_path = get_image_path(str(primary_product_code), filename_img)
                                
                                with open(image_path, "wb") as f:
                                    for chunk in response.iter_content(chunk_size=8192):
                                        f.write(chunk)
                                
                                local_url = f"/api/images/{primary_product_code}/{filename_img}"
                                downloaded_urls.append(local_url)
                                downloaded_count += 1
                            else:
                                downloaded_urls.append(img_url)
                        except Exception as e:
                            downloaded_urls.append(img_url)
                            import sys
                            print(f"[SyncTrendyol] Görsel indirme hatası: {e}", file=sys.stderr)
                    
                    final_urls = downloaded_urls if downloaded_urls else image_urls
                
                # Veritabanına kaydet
                if final_urls:
                    # Mevcut mapping'i kontrol et
                    existing = db.query(ProductImageMapping).filter(
                        ProductImageMapping.store_id == store.id,
                        or_(
                            ProductImageMapping.product_code == str(primary_product_code),
                            ProductImageMapping.barcode == str(primary_product_code) if barcode else False,
                            ProductImageMapping.content_id == str(primary_product_code) if content_id else False
                        ),
                        ProductImageMapping.is_active == True
                    ).first()

                    if existing:
                        # Güncelle
                        existing.image_urls = json.dumps(final_urls)
                        existing.primary_image_url = final_urls[0] if final_urls else None
                        if product_name:
                            existing.product_name = product_name
                        if barcode:
                            existing.barcode = barcode
                        if content_id:
                            existing.content_id = content_id
                        updated_count += 1
                    else:
                        # Yeni oluştur
                        new_mapping = ProductImageMapping(
                            store_id=store.id,
                            product_code=str(primary_product_code),
                            barcode=barcode if barcode and barcode.lower() != "none" else None,
                            content_id=content_id if content_id and content_id.lower() != "none" else None,
                            product_name=product_name if product_name and product_name.lower() != "none" else None,
                            image_urls=json.dumps(final_urls),
                            primary_image_url=final_urls[0] if final_urls else None,
                            is_active=True
                        )
                        db.add(new_mapping)
                        created_count += 1
                else:
                    skipped_count += 1
                    errors.append({
                        "product_code": primary_product_code,
                        "error": "Görsel bulunamadı"
                    })
                    
            except Exception as e:
                errors.append({
                    "product_code": str(item.get("productCode", "bilinmeyen")),
                    "error": str(e)
                })
                import sys
                print(f"[SyncTrendyol] Ürün işleme hatası: {e}", file=sys.stderr)
                continue
        
        db.commit()
        
        return {
            "message": "Trendyol API'den senkronizasyon tamamlandı",
            "created": created_count,
            "updated": updated_count,
            "skipped": skipped_count,
            "downloaded": downloaded_count,
            "total_products": len(all_products),
            "errors": errors[:50],  # İlk 50 hatayı göster
            "error_count": len(errors)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        if _db_available and db:
            db.rollback()
        raise HTTPException(status_code=500, detail=f"Trendyol senkronizasyon hatası: {str(e)}")

