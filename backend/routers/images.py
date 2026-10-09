"""
Görsel Yönetim Sistemi Router
Ürün görsellerini yükleme, yönetme ve silme işlemleri
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Depends, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional, Any, Dict
from sqlalchemy.orm import Session
import os
import shutil
from pathlib import Path
from datetime import datetime
import uuid
from PIL import Image
import io

# Database modülünü optional olarak yükle (ghost mode)
try:
    from database.db import get_db
    from database.models import Product, Store
    from security import get_current_store
    _db_available = True
except Exception:
    _db_available = False
    def get_db():
        raise HTTPException(status_code=503, detail="Database not available (ghost mode)")

    def get_current_store():
        raise HTTPException(status_code=503, detail="Database not available (ghost mode)")

router = APIRouter()

# Görseller için klasör yapısı
UPLOAD_DIR = Path("uploads/images")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# İzin verilen görsel formatları
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def _check_db():
    """Database kontrolü - ghost mode"""
    if not _db_available:
        raise HTTPException(status_code=503, detail="Database not available (ghost mode)")


class ImageInfo(BaseModel):
    """Görsel bilgisi modeli"""
    id: str
    product_id: str
    product_name: Optional[str] = None
    filename: str
    url: str
    size: int
    width: Optional[int] = None
    height: Optional[int] = None
    uploaded_at: str
    is_primary: bool = False


class ImageUploadResponse(BaseModel):
    """Görsel yükleme yanıtı"""
    message: str
    image: ImageInfo


def get_image_path(product_id: str, filename: str) -> Path:
    """Ürün görseli için dosya yolu oluşturur"""
    product_dir = UPLOAD_DIR / product_id
    product_dir.mkdir(parents=True, exist_ok=True)
    return product_dir / filename


def validate_image(file: UploadFile) -> tuple:
    """Görsel dosyasını doğrular ve işler"""
    # Dosya uzantısı kontrolü
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Geçersiz dosya formatı. İzin verilen formatlar: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    # Dosya boyutu kontrolü (dosya okunmadan önce)
    file.file.seek(0, 2)  # Dosyanın sonuna git
    file_size = file.file.tell()
    file.file.seek(0)  # Başa dön
    
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"Dosya boyutu çok büyük. Maksimum boyut: {MAX_FILE_SIZE / 1024 / 1024}MB"
        )
    
    return file_ext, file_size


def process_image(file_content: bytes, max_size: tuple = (1200, 1200)) -> tuple:
    """Görseli işler ve optimize eder"""
    try:
        img = Image.open(io.BytesIO(file_content))
        
        # Orijinal boyutlar
        original_size = img.size
        
        # Görseli optimize et (boyut küçültme)
        img.thumbnail(max_size, Image.Resampling.LANCZOS)
        
        # Optimize edilmiş görseli bytes'a çevir
        output = io.BytesIO()
        if img.format == 'PNG':
            img.save(output, format='PNG', optimize=True)
        else:
            img.save(output, format='JPEG', quality=85, optimize=True)
        
        return output.getvalue(), original_size, img.size
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Görsel işleme hatası: {str(e)}")


@router.post("/upload", response_model=ImageUploadResponse)
async def upload_product_image(
    product_id: str = Form(...),
    file: UploadFile = File(...),
    is_primary: bool = Form(False),
    store: Any = Depends(get_current_store) if _db_available else None,
    db: Any = Depends(get_db) if _db_available else None
):
    """
    Ürün görseli yükler
    
    Args:
        product_id: Ürün ID'si
        file: Yüklenecek görsel dosyası
        is_primary: Ana görsel mi?
    """
    try:
        # Dosya doğrulama
        file_ext, file_size = validate_image(file)
        
        # Dosya içeriğini oku
        file_content = await file.read()
        
        # Görseli işle ve optimize et
        processed_content, original_size, optimized_size = process_image(file_content)
        
        # Benzersiz dosya adı oluştur
        unique_filename = f"{uuid.uuid4()}{file_ext}"
        image_path = get_image_path(product_id, unique_filename)
        
        # Dosyayı kaydet
        with open(image_path, "wb") as f:
            f.write(processed_content)
        
        # Database'de ürün bilgisini kontrol et
        product_name = None
        if _db_available and db:
            try:
                product = db.query(Product).filter(Product.store_id == store.id, Product.product_id == product_id).first()
                if product:
                    product_name = product.product_name
            except:
                pass

        # Eğer ana görsel seçildiyse, diğer görselleri ana görsel yapma
        if is_primary:
            product_dir = UPLOAD_DIR / product_id
            if product_dir.exists():
                # Mevcut ana görseli bul ve işaretini kaldır (metadata dosyası ile)
                metadata_file = product_dir / ".metadata.json"
                if metadata_file.exists():
                    import json
                    try:
                        with open(metadata_file, "r", encoding="utf-8") as f:
                            metadata = json.load(f)
                        for img_info in metadata.get("images", []):
                            if img_info.get("is_primary"):
                                img_info["is_primary"] = False
                        with open(metadata_file, "w", encoding="utf-8") as f:
                            json.dump(metadata, f, indent=2)
                    except:
                        pass
        
        # Metadata dosyasına kaydet
        metadata_file = UPLOAD_DIR / product_id / ".metadata.json"
        metadata = {"images": []}
        if metadata_file.exists():
            import json
            try:
                with open(metadata_file, "r", encoding="utf-8") as f:
                    metadata = json.load(f)
            except:
                metadata = {"images": []}
        
        image_info = {
            "id": str(uuid.uuid4()),
            "filename": unique_filename,
            "size": len(processed_content),
            "width": optimized_size[0],
            "height": optimized_size[1],
            "original_width": original_size[0],
            "original_height": original_size[1],
            "uploaded_at": datetime.now().isoformat(),
            "is_primary": is_primary
        }
        
        metadata["images"].append(image_info)
        
        with open(metadata_file, "w", encoding="utf-8") as f:
            import json
            json.dump(metadata, f, indent=2)
        
        # URL oluştur
        image_url = f"/api/images/{product_id}/{unique_filename}"
        
        return ImageUploadResponse(
            message="Görsel başarıyla yüklendi",
            image=ImageInfo(
                id=image_info["id"],
                product_id=product_id,
                product_name=product_name,
                filename=unique_filename,
                url=image_url,
                size=image_info["size"],
                width=image_info["width"],
                height=image_info["height"],
                uploaded_at=image_info["uploaded_at"],
                is_primary=is_primary
            )
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Görsel yükleme hatası: {str(e)}")


@router.get("/{product_id}", response_model=List[ImageInfo])
async def get_product_images(
    product_id: str,
    include_trendyol: bool = True,
    store: Any = Depends(get_current_store) if _db_available else None,
    db: Any = Depends(get_db) if _db_available else None
):
    """
    Ürünün tüm görsellerini getirir (yerel + Trendyol API'den)
    """
    images = []
    product_name = None

    # Database'den ürün adını al
    if _db_available and db:
        try:
            product = db.query(Product).filter(Product.store_id == store.id, Product.product_id == product_id).first()
            if product:
                product_name = product.product_name
        except:
            pass
    
    # Yerel görselleri al
    product_dir = UPLOAD_DIR / product_id
    if product_dir.exists():
        metadata_file = product_dir / ".metadata.json"
        if metadata_file.exists():
            try:
                import json
                with open(metadata_file, "r", encoding="utf-8") as f:
                    metadata = json.load(f)
                
                for img_info in metadata.get("images", []):
                    image_url = f"/api/images/{product_id}/{img_info['filename']}"
                    images.append(ImageInfo(
                        id=img_info.get("id", ""),
                        product_id=product_id,
                        product_name=product_name,
                        filename=img_info["filename"],
                        url=image_url,
                        size=img_info.get("size", 0),
                        width=img_info.get("width"),
                        height=img_info.get("height"),
                        uploaded_at=img_info.get("uploaded_at", datetime.now().isoformat()),
                        is_primary=img_info.get("is_primary", False)
                    ))
            except:
                pass
    
    # Trendyol API'den görselleri çek
    if include_trendyol:
        try:
            print(f"[Images] Trendyol görselleri çekiliyor: {product_id}")
            trendyol_images = await get_trendyol_product_images(product_id)
            print(f"[Images] Trendyol'dan {len(trendyol_images)} görsel bulundu")
            
            for idx, img_url in enumerate(trendyol_images):
                images.append(ImageInfo(
                    id=f"trendyol_{product_id}_{idx}",
                    product_id=product_id,
                    product_name=product_name,
                    filename=f"trendyol_{idx}.jpg",
                    url=img_url,
                    size=0,
                    width=None,
                    height=None,
                    uploaded_at=datetime.now().isoformat(),
                    is_primary=(idx == 0 and len(images) == 0)  # İlk görsel ana görsel
                ))
        except Exception as e:
            print(f"[Images] Trendyol görsel çekme hatası: {e}")
            import traceback
            traceback.print_exc()
    
    # Ana görseli önce göster
    images.sort(key=lambda x: (not x.is_primary, x.uploaded_at), reverse=True)
    
    return images


async def get_trendyol_product_images(product_id: str) -> List[str]:
    """
    Trendyol API'den ürün görsellerini çeker
    Önce siparişlerden, sonra Products API'den dener
    """
    import os
    import requests
    import base64
    
    images = []
    
    # Önce siparişlerden görsel bilgilerini çek
    try:
        from routers.products import get_trendyol_orders_data
        orders = get_trendyol_orders_data()
        
        print(f"[Images] {len(orders)} sipariş kontrol ediliyor...")
        
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
                # Ürün ID'sini kontrol et
                line_product_id = None
                for key in ["productCode", "product_code", "productId", "product_id", "sku", "barcode", 
                           "stockCode", "sellerSku", "productSku"]:
                    value = line.get(key)
                    if value:
                        val_str = str(value).strip()
                        if val_str and val_str.lower() not in ["merchantsku", "stockcode"]:
                            line_product_id = val_str
                            break
                
                if not line_product_id:
                    if line.get("id"):
                        line_product_id = str(line.get("id"))
                    elif line.get("contentId"):
                        line_product_id = str(line.get("contentId"))
                
                if str(line_product_id) == str(product_id):
                    print(f"[Images] Ürün eşleşti: {product_id}")
                    print(f"[Images] Satır tüm keys: {list(line.keys())}")
                    print(f"[Images] Satır değerleri (ilk 5): {[(k, str(v)[:100]) for k, v in list(line.items())[:5]]}")
                    
                    # Görsel URL'lerini çıkar - tüm olası alanları kontrol et
                    for img_key in ["imageUrl", "image_url", "productImage", "productImageUrl", 
                                   "image", "thumbnail", "thumbnailUrl", "mediaUrl", "images",
                                   "productImageUrl", "productImageList", "mediaUrls"]:
                        img_value = line.get(img_key)
                        if img_value:
                            print(f"[Images] Görsel alanı bulundu: {img_key} = {type(img_value).__name__}")
                            if isinstance(img_value, str) and img_value.startswith("http"):
                                if img_value not in images:
                                    images.append(img_value)
                                    print(f"[Images] Görsel URL eklendi: {img_value[:100]}")
                            elif isinstance(img_value, list):
                                for img in img_value:
                                    if isinstance(img, str) and img.startswith("http") and img not in images:
                                        images.append(img)
                                        print(f"[Images] Görsel URL eklendi (liste): {img[:100]}")
                                    elif isinstance(img, dict):
                                        img_url = (
                                            img.get("url") or 
                                            img.get("imageUrl") or 
                                            img.get("image") or
                                            img.get("mediaUrl") or
                                            img.get("src")
                                        )
                                        if img_url and isinstance(img_url, str) and img_url.startswith("http") and img_url not in images:
                                            images.append(img_url)
                                            print(f"[Images] Görsel URL eklendi (dict): {img_url[:100]}")
                    
                    # Eğer görsel alanlarında bulunamadıysa, tüm değerleri tara
                    if not images:
                        print(f"[Images] Görsel alanlarında bulunamadı, tüm değerler taranıyor...")
                        for key, value in line.items():
                            if isinstance(value, str) and ("http" in value.lower() or "image" in key.lower()):
                                if value.startswith("http") and any(ext in value.lower() for ext in [".jpg", ".jpeg", ".png", ".gif", ".webp"]):
                                    if value not in images:
                                        images.append(value)
                                        print(f"[Images] Görsel URL bulundu (taramadan): {key} = {value[:100]}")
                    
                    if images:
                        print(f"[Images] Siparişlerden {len(images)} görsel bulundu: {product_id}")
                        return images
                    else:
                        print(f"[Images] Ürün eşleşti ama görsel bulunamadı: {product_id}")
                        # contentId ile Trendyol CDN'inden görsel URL'lerini oluştur
                        content_id = line.get("contentId")
                        if content_id:
                            print(f"[Images] contentId ile CDN görsel URL'leri oluşturuluyor: {content_id}")
                            try:
                                # Trendyol CDN formatları - farklı boyutlar ve formatlar dene
                                cdn_formats = [
                                    f"https://cdn.dsmcdn.com/mnresize/1200/1200/ty{content_id}.jpg",
                                    f"https://cdn.dsmcdn.com/mnresize/800/800/ty{content_id}.jpg",
                                    f"https://cdn.dsmcdn.com/mnresize/1200/1200/ty{content_id}.webp",
                                ]
                                
                                # İlk görseli kontrol et (genellikle en yaygın format)
                                for cdn_url in cdn_formats[:2]:  # İlk 2 formatı dene
                                    try:
                                        test_response = requests.head(cdn_url, timeout=5, allow_redirects=True)
                                        if test_response.status_code == 200:
                                            images.append(cdn_url)
                                            print(f"[Images] CDN'den görsel bulundu: {cdn_url}")
                                            # İlk görseli bulduktan sonra diğer görselleri de ekle (index ile)
                                            # Trendyol genellikle ty{contentId}-{index}.jpg formatını kullanır
                                            for idx in range(1, 5):  # 4 ek görsel daha dene
                                                additional_url = f"https://cdn.dsmcdn.com/mnresize/1200/1200/ty{content_id}-{idx}.jpg"
                                                try:
                                                    test_response = requests.head(additional_url, timeout=3, allow_redirects=True)
                                                    if test_response.status_code == 200:
                                                        images.append(additional_url)
                                                except:
                                                    break  # Daha fazla görsel yok
                                            return images
                                    except:
                                        continue
                                
                                # Eğer HEAD request başarısız olursa, farklı formatları dene
                                if not images:
                                    # Trendyol'un farklı CDN formatlarını dene
                                    # Not: Trendyol CDN URL'leri genellikle şu formatta olur:
                                    # https://cdn.dsmcdn.com/mnresize/{width}/{height}/ty{contentId}.jpg
                                    # veya https://cdn.dsmcdn.com/images/{contentId}.jpg
                                    # Ancak bazen contentId direkt kullanılır, bazen de farklı formatlar olabilir
                                    alternative_formats = [
                                        f"https://cdn.dsmcdn.com/mnresize/1200/1200/ty{content_id}.jpg",
                                        f"https://cdn.dsmcdn.com/mnresize/800/800/ty{content_id}.jpg",
                                        f"https://cdn.dsmcdn.com/mnresize/600/600/ty{content_id}.jpg",
                                        f"https://cdn.dsmcdn.com/images/{content_id}.jpg",
                                        f"https://cdn.dsmcdn.com/ty{content_id}.jpg",
                                        f"https://cdn.dsmcdn.com/mnresize/1200/1200/ty{content_id}.webp",
                                    ]
                                    
                                    # Her formatı test et
                                    for alt_url in alternative_formats:
                                        try:
                                            test_response = requests.head(alt_url, timeout=3, allow_redirects=True, 
                                                                         headers={"User-Agent": "Mozilla/5.0"})
                                            if test_response.status_code == 200:
                                                images.append(alt_url)
                                                print(f"[Images] CDN görsel bulundu (alternatif format): {alt_url}")
                                                return images
                                        except Exception as e:
                                            print(f"[Images] Format test edilemedi {alt_url}: {e}")
                                            continue
                                    
                                    # Hiçbiri çalışmazsa, en yaygın formatı direkt ekle
                                    # Frontend'de CORS sorunu olabilir, bu yüzden proxy üzerinden servis edebiliriz
                                    primary_url = f"https://cdn.dsmcdn.com/mnresize/1200/1200/ty{content_id}.jpg"
                                    images.append(primary_url)
                                    print(f"[Images] CDN görsel URL'si oluşturuldu (doğrulanmadı): {primary_url}")
                                    print(f"[Images] Not: Eğer görsel yüklenemezse, CORS veya URL formatı sorunu olabilir")
                                    return images
                            except Exception as e:
                                print(f"[Images] CDN denemesi başarısız: {e}")
    except Exception as e:
        print(f"[Images] Siparişlerden görsel çekme hatası: {e}")
        import traceback
        traceback.print_exc()
    
    # Siparişlerden bulunamadıysa, Trendyol Public API'yi dene (barcode ile)
    # Trendyol'un public catalog API'sinden görselleri çekmeyi deneyelim
    if not images:
        try:
            # Barcode ile Trendyol public API'den görsel çek
            public_url = f"https://public.trendyol.com/discovery-web-productgw-service/api/product/{product_id}"
            response = requests.get(public_url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                # Public API'den görsel URL'lerini çıkar
                product_data = data.get("result", {})
                images_data = product_data.get("images", []) or product_data.get("imageUrls", []) or []
                for img in images_data:
                    if isinstance(img, str) and img.startswith("http") and img not in images:
                        images.append(img)
                    elif isinstance(img, dict):
                        img_url = img.get("url") or img.get("imageUrl") or img.get("src")
                        if img_url and isinstance(img_url, str) and img_url.startswith("http") and img_url not in images:
                            images.append(img_url)
                if images:
                    print(f"[Images] Public API'den {len(images)} görsel bulundu: {product_id}")
                    return images
        except Exception as e:
            print(f"[Images] Public API denemesi başarısız: {e}")
    
    # Son olarak Products API'yi dene (403 hatası olsa bile)
    api_key = os.getenv("TRENDYOL_API_KEY")
    api_secret = os.getenv("TRENDYOL_API_SECRET")
    supplier_id = os.getenv("TRENDYOL_SUPPLIER_ID")
    
    if not all([api_key, api_secret, supplier_id]):
        return images
    
    try:
        # Trendyol Products API
        url = f"https://api.trendyol.com/sapigw/suppliers/{supplier_id}/products"
        
        auth_string = f"{api_key}:{api_secret}"
        auth_bytes = auth_string.encode('ascii')
        auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
        
        headers = {
            "Authorization": f"Basic {auth_b64}",
            "Content-Type": "application/json",
            "User-Agent": "Trendyol-AI-Assistant/1.0"
        }
        
        # Ürünü bulmak için sayfalama yap
        page = 0
        page_size = 500
        
        while page < 10:  # Maksimum 10 sayfa
            params = {
                "page": page,
                "size": page_size,
                "approved": "true"
            }
            
            response = requests.get(url, headers=headers, params=params, timeout=30)
            
            if response.status_code != 200:
                print(f"[Images] Trendyol API yanıt hatası: {response.status_code}")
                if response.status_code == 401:
                    print(f"[Images] Authentication hatası - API key/secret kontrol edin")
                elif response.status_code == 403:
                    print(f"[Images] 403 Forbidden - API erişim izni yok. Supplier ID veya API key kontrol edin.")
                    print(f"[Images] Response: {response.text[:200]}")
                else:
                    print(f"[Images] Response: {response.text[:200]}")
                break
            
            data = response.json()
            items = data.get("content", []) or data.get("items", []) or []
            
            if not items:
                print(f"[Images] Sayfa {page}: Ürün bulunamadı")
                break
            
            print(f"[Images] Sayfa {page}: {len(items)} ürün bulundu")
            
            # İlk ürünün yapısını göster (debug)
            if page == 0 and len(items) > 0:
                first_item = items[0]
                print(f"[Images] İlk ürün keys: {list(first_item.keys())[:40]}")
                # Görsel ile ilgili tüm keys'leri göster
                image_keys = [k for k in first_item.keys() if 'image' in k.lower() or 'media' in k.lower() or 'photo' in k.lower()]
                print(f"[Images] Görsel ile ilgili keys: {image_keys}")
                if image_keys:
                    for key in image_keys[:5]:
                        value = first_item.get(key)
                        print(f"[Images] {key}: {type(value).__name__} - {str(value)[:200] if value else 'None'}")
            
            for item in items:
                # Ürün ID'sini kontrol et - tüm olası alanları dene
                item_product_ids = []
                
                # Tüm olası ID alanlarını topla
                for key in ["barcode", "merchantSku", "productId", "product_id", "productCode", "product_code", 
                           "sku", "stockCode", "sellerSku", "productSku", "id"]:
                    value = item.get(key)
                    if value:
                        val_str = str(value).strip()
                        if val_str and val_str.lower() not in ["merchantsku", "stockcode"]:
                            item_product_ids.append(val_str)
                
                # Eşleşme kontrolü - herhangi bir ID eşleşirse devam et
                matched = False
                for item_id in item_product_ids:
                    if str(item_id) == str(product_id):
                        matched = True
                        break
                
                if matched:
                    # Debug: İlk eşleşen ürünün tüm keys'lerini göster
                    print(f"[Images] Ürün bulundu: {product_id}")
                    print(f"[Images] Ürün keys: {list(item.keys())[:30]}")
                    
                    # Görselleri çıkar
                    images = []
                    
                    # Tüm olası görsel alanlarını kontrol et
                    image_fields = [
                        "images", "productImages", "mediaUrls", "imageUrls", 
                        "imageList", "productImageList", "mediaList",
                        "mainImage", "thumbnailImage", "image", "productImage",
                        "imageUrl", "productImageUrl", "mediaUrl"
                    ]
                    
                    for field in image_fields:
                        value = item.get(field)
                        if value:
                            if isinstance(value, str):
                                if value.startswith("http"):
                                    images.append(value)
                            elif isinstance(value, list):
                                for img in value:
                                    if isinstance(img, str) and img.startswith("http"):
                                        images.append(img)
                                    elif isinstance(img, dict):
                                        # Nested structure olabilir
                                        img_url = (
                                            img.get("url") or 
                                            img.get("imageUrl") or 
                                            img.get("image") or
                                            img.get("mediaUrl") or
                                            img.get("src")
                                        )
                                        if img_url and isinstance(img_url, str) and img_url.startswith("http"):
                                            images.append(img_url)
                    
                    # Eğer hala görsel bulunamadıysa, tüm değerleri tarayalım
                    if not images:
                        print(f"[Images] Görsel alanlarında bulunamadı, tüm değerleri tarıyorum...")
                        for key, value in item.items():
                            if isinstance(value, str) and ("http" in value.lower() or "image" in key.lower()):
                                if value.startswith("http") and any(ext in value.lower() for ext in [".jpg", ".jpeg", ".png", ".gif", ".webp"]):
                                    images.append(value)
                            elif isinstance(value, list) and len(value) > 0:
                                # Liste içindeki string'leri kontrol et
                                for v in value:
                                    if isinstance(v, str) and v.startswith("http"):
                                        images.append(v)
                    
                    # URL'leri temizle ve filtrele (duplicate'leri kaldır)
                    clean_images = []
                    seen = set()
                    for img_url in images:
                        if img_url and isinstance(img_url, str) and img_url.startswith("http"):
                            if img_url not in seen:
                                clean_images.append(img_url)
                                seen.add(img_url)
                    
                    print(f"[Images] Bulunan görsel sayısı: {len(clean_images)}")
                    if clean_images:
                        print(f"[Images] İlk görsel URL: {clean_images[0][:100]}")
                    
                    return clean_images[:10]  # Maksimum 10 görsel
            
            if len(items) < page_size:
                break
            
            page += 1
        
        return []
    
    except Exception as e:
        print(f"[Images] Trendyol API hatası: {e}")
        return []


@router.get("/{product_id}/{filename}")
async def get_image_file(
    product_id: str, 
    filename: str,
    url: str = None  # Query parameter: Trendyol CDN URL'si
):
    """
    Görsel dosyasını döner
    Trendyol CDN URL'leri için proxy görevi görür
    """
    # Eğer Trendyol CDN URL'si query parameter olarak verilmişse, proxy üzerinden servis et
    if url and url.startswith("https://"):
        import requests
        try:
            print(f"[Images] CDN proxy: {url}")
            # CDN'den görseli çek
            response = requests.get(url, timeout=15, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": "https://www.trendyol.com/",
                "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
                "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Sec-Fetch-Dest": "image",
                "Sec-Fetch-Mode": "no-cors",
                "Sec-Fetch-Site": "cross-site"
            }, allow_redirects=True, stream=True)
            
            if response.status_code == 200:
                from fastapi.responses import Response
                import sys
                
                content_type = response.headers.get("content-type", "image/jpeg")
                content_length = len(response.content)
                
                print(f"[Images] CDN proxy başarılı: {content_length} bytes, type: {content_type}", file=sys.stderr)
                
                return Response(
                    content=response.content,
                    media_type=content_type,
                    headers={
                        "Cache-Control": "public, max-age=3600",
                        "Access-Control-Allow-Origin": "*",
                        "Access-Control-Allow-Methods": "GET",
                        "Access-Control-Allow-Headers": "*",
                        "Content-Length": str(content_length)
                    }
                )
            else:
                print(f"[Images] CDN proxy hatası: {response.status_code}")
                raise HTTPException(status_code=404, detail="Görsel bulunamadı")
        except Exception as e:
            import sys
            print(f"[Images] CDN proxy hatası: {e}", file=sys.stderr)
            raise HTTPException(status_code=404, detail=f"Görsel yüklenemedi: {str(e)}")
    
    # Eğer Trendyol görseli ise (filename'den anlaşılıyorsa), contentId ile URL oluştur
    if filename.startswith("trendyol_"):
        import requests
        try:
            # contentId'yi siparişlerden bul
            content_id = None
            try:
                from routers.products import get_trendyol_orders_data
                orders = get_trendyol_orders_data()
                
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
                        # Ürün ID'sini kontrol et
                        line_product_id = None
                        for key in ["productCode", "product_code", "productId", "product_id", "sku", "barcode", 
                                   "stockCode", "sellerSku", "productSku"]:
                            value = line.get(key)
                            if value:
                                val_str = str(value).strip()
                                if val_str and val_str.lower() not in ["merchantsku", "stockcode"]:
                                    line_product_id = val_str
                                    break
                        
                        if not line_product_id:
                            if line.get("id"):
                                line_product_id = str(line.get("id"))
                            elif line.get("contentId"):
                                line_product_id = str(line.get("contentId"))
                        
                        if str(line_product_id) == str(product_id):
                            # contentId'yi al
                            content_id = line.get("contentId")
                            if content_id:
                                break
                    
                    if content_id:
                        break
            except Exception as e:
                print(f"[Images] contentId bulma hatası: {e}")
            
            # Eğer contentId bulunamadıysa, product_id'yi kullan (bazen aynı olabilir)
            if not content_id:
                content_id = product_id
                print(f"[Images] contentId bulunamadı, product_id kullanılıyor: {content_id}")
            else:
                print(f"[Images] contentId bulundu: {content_id}")
            
            image_url = f"https://cdn.dsmcdn.com/mnresize/1200/1200/ty{content_id}.jpg"
            
            print(f"[Images] CDN proxy (contentId): {image_url}")
            # CDN'den görseli çek
            response = requests.get(image_url, timeout=10, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": "https://www.trendyol.com/",
                "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
                "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7"
            }, allow_redirects=True)
            
            print(f"[Images] CDN response status: {response.status_code}")
            
            if response.status_code == 200:
                from fastapi.responses import Response
                content_type = response.headers.get("content-type", "image/jpeg")
                print(f"[Images] CDN görsel başarıyla çekildi, content-type: {content_type}, size: {len(response.content)} bytes")
                return Response(
                    content=response.content,
                    media_type=content_type,
                    headers={
                        "Cache-Control": "public, max-age=3600"
                    }
                )
            else:
                print(f"[Images] CDN yanıt hatası: {response.status_code}, response: {response.text[:200]}")
                # Alternatif formatları dene
                alternative_urls = [
                    f"https://cdn.dsmcdn.com/mnresize/800/800/ty{content_id}.jpg",
                    f"https://cdn.dsmcdn.com/images/{content_id}.jpg",
                    f"https://cdn.dsmcdn.com/ty{content_id}.jpg",
                ]
                
                for alt_url in alternative_urls:
                    try:
                        print(f"[Images] Alternatif URL deneniyor: {alt_url}")
                        alt_response = requests.get(alt_url, timeout=5, headers={
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                            "Referer": "https://www.trendyol.com/"
                        }, allow_redirects=True)
                        
                        if alt_response.status_code == 200:
                            from fastapi.responses import Response
                            print(f"[Images] Alternatif URL başarılı: {alt_url}")
                            return Response(
                                content=alt_response.content,
                                media_type=alt_response.headers.get("content-type", "image/jpeg"),
                                headers={
                                    "Cache-Control": "public, max-age=3600"
                                }
                            )
                    except Exception as alt_e:
                        print(f"[Images] Alternatif URL hatası: {alt_e}")
                        continue
                
                raise HTTPException(status_code=404, detail=f"Görsel bulunamadı (status: {response.status_code})")
        except requests.exceptions.RequestException as e:
            print(f"[Images] CDN proxy request hatası: {type(e).__name__}: {str(e)}")
            import traceback
            traceback.print_exc()
            raise HTTPException(status_code=404, detail=f"Görsel yüklenemedi: {str(e)}")
        except Exception as e:
            print(f"[Images] CDN proxy genel hatası: {type(e).__name__}: {str(e)}")
            import traceback
            traceback.print_exc()
            raise HTTPException(status_code=404, detail=f"Görsel yüklenemedi: {str(e)}")
    
    # Yerel görsel
    image_path = get_image_path(product_id, filename)
    
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Görsel bulunamadı")
    
    return FileResponse(
        path=str(image_path),
        media_type="image/jpeg" if filename.lower().endswith((".jpg", ".jpeg")) else "image/png"
    )


@router.delete("/{product_id}/{image_id}")
async def delete_product_image(
    product_id: str,
    image_id: str,
    db: Any = Depends(get_db) if _db_available else None
):
    """
    Ürün görselini siler
    """
    metadata_file = UPLOAD_DIR / product_id / ".metadata.json"
    
    if not metadata_file.exists():
        raise HTTPException(status_code=404, detail="Görsel bulunamadı")
    
    try:
        import json
        with open(metadata_file, "r", encoding="utf-8") as f:
            metadata = json.load(f)
        
        # Görseli bul
        image_to_delete = None
        for img_info in metadata.get("images", []):
            if img_info.get("id") == image_id:
                image_to_delete = img_info
                break
        
        if not image_to_delete:
            raise HTTPException(status_code=404, detail="Görsel bulunamadı")
        
        # Dosyayı sil
        image_path = get_image_path(product_id, image_to_delete["filename"])
        if image_path.exists():
            image_path.unlink()
        
        # Metadata'dan kaldır
        metadata["images"] = [img for img in metadata["images"] if img.get("id") != image_id]
        
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)
        
        return {"message": "Görsel başarıyla silindi"}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Görsel silme hatası: {str(e)}")


@router.put("/{product_id}/{image_id}/set-primary")
async def set_primary_image(
    product_id: str,
    image_id: str,
    db: Any = Depends(get_db) if _db_available else None
):
    """
    Görseli ana görsel olarak işaretler
    """
    metadata_file = UPLOAD_DIR / product_id / ".metadata.json"
    
    if not metadata_file.exists():
        raise HTTPException(status_code=404, detail="Görsel bulunamadı")
    
    try:
        import json
        with open(metadata_file, "r", encoding="utf-8") as f:
            metadata = json.load(f)
        
        # Tüm görsellerin ana görsel işaretini kaldır
        for img_info in metadata.get("images", []):
            img_info["is_primary"] = (img_info.get("id") == image_id)
        
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)
        
        return {"message": "Ana görsel güncellendi"}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ana görsel güncelleme hatası: {str(e)}")


@router.get("/")
async def get_all_products_with_images(
    include_trendyol: bool = True,
    store: Any = Depends(get_current_store) if _db_available else None,
    db: Any = Depends(get_db) if _db_available else None
):
    """
    Tüm ürünleri listeler (görseli olan ve olmayan)
    Trendyol API'den görsel bilgilerini de çeker
    """
    products_dict = {}
    
    # Önce siparişlerden tüm ürünleri al
    try:
        from routers.products import get_trendyol_orders_data
        orders = get_trendyol_orders_data()
        
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
                    # Ürün ID'sini çıkar
                    product_id = None
                    for key in ["productCode", "product_code", "productId", "product_id", "sku", "barcode", 
                               "stockCode", "sellerSku", "productSku"]:
                        value = line.get(key)
                        if value:
                            val_str = str(value).strip()
                            if val_str and val_str.lower() not in ["merchantsku", "stockcode"]:
                                product_id = val_str
                                break
                    
                    if not product_id:
                        if line.get("id"):
                            product_id = str(line.get("id"))
                        elif line.get("contentId"):
                            product_id = str(line.get("contentId"))
                    
                    if not product_id or product_id == "None" or product_id == "":
                        continue
                    
                    product_id_str = str(product_id)
                    content_id = line.get("contentId")
                    
                    # contentId varsa, CDN'den görsel URL'lerini oluştur
                    image_count = 0
                    if content_id:
                        # Trendyol CDN formatı: https://cdn.dsmcdn.com/mnresize/{width}/{height}/ty{contentId}.jpg
                        # Ana görsel için genellikle 1200x1200 veya 800x800 kullanılır
                        # Birden fazla görsel için farklı index'ler olabilir
                        cdn_base = f"https://cdn.dsmcdn.com/mnresize/1200/1200/ty{content_id}"
                        # İlk görseli kontrol et (genellikle .jpg veya .webp)
                        image_count = 1  # En azından bir görsel olduğunu varsay
                    
                    if product_id_str not in products_dict:
                        products_dict[product_id_str] = {
                            "product_id": product_id_str,
                            "product_name": (
                                line.get("productName") or 
                                line.get("product_name") or 
                                line.get("name") or 
                                line.get("productTitle") or
                                "Bilinmeyen Ürün"
                            ),
                            "image_count": image_count,
                            "has_primary": (image_count > 0),
                            "has_trendyol_images": (image_count > 0),
                            "content_id": str(content_id) if content_id else None
                        }
                    else:
                        # Mevcut ürüne contentId ve görsel bilgisini ekle
                        if content_id and products_dict[product_id_str]["image_count"] == 0:
                            products_dict[product_id_str]["image_count"] = image_count
                            products_dict[product_id_str]["has_primary"] = (image_count > 0)
                            products_dict[product_id_str]["has_trendyol_images"] = (image_count > 0)
                            products_dict[product_id_str]["content_id"] = str(content_id)
                except:
                    continue
    except Exception as e:
        print(f"[Images] Error getting products from orders: {e}")
    
    # Database'den ürünleri al
    if _db_available and db:
        try:
            products = db.query(Product).filter(Product.store_id == store.id).all()
            for product in products:
                if product.product_id not in products_dict:
                    products_dict[product.product_id] = {
                        "product_id": product.product_id,
                        "product_name": product.product_name,
                        "image_count": 0,
                        "has_primary": False,
                        "has_trendyol_images": False
                    }
        except:
            pass
    
    # Trendyol API'den ürün görsellerini kontrol et
    # Not: Products API'den 403 hatası alındığı için siparişlerden görsel bilgilerini çekiyoruz
    if include_trendyol:
        try:
            print(f"[Images] Siparişlerden görsel bilgileri kontrol ediliyor...")
            # Siparişlerden görsel bilgilerini çek
            from routers.products import get_trendyol_orders_data
            orders = get_trendyol_orders_data()
            
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
                        # Ürün ID'sini çıkar
                        product_id = None
                        for key in ["productCode", "product_code", "productId", "product_id", "sku", "barcode", 
                                   "stockCode", "sellerSku", "productSku"]:
                            value = line.get(key)
                            if value:
                                val_str = str(value).strip()
                                if val_str and val_str.lower() not in ["merchantsku", "stockcode"]:
                                    product_id = val_str
                                    break
                        
                        if not product_id:
                            if line.get("id"):
                                product_id = str(line.get("id"))
                            elif line.get("contentId"):
                                product_id = str(line.get("contentId"))
                        
                        if not product_id or product_id == "None" or product_id == "":
                            continue
                        
                        product_id_str = str(product_id)
                        
                        # Sipariş satırından görsel bilgilerini çıkar
                        image_urls = []
                        for img_key in ["imageUrl", "image_url", "productImage", "productImageUrl", 
                                       "image", "thumbnail", "thumbnailUrl", "mediaUrl"]:
                            img_value = line.get(img_key)
                            if img_value and isinstance(img_value, str) and img_value.startswith("http"):
                                image_urls.append(img_value)
                        
                        # Eğer görsel bulunduysa, ürün listesine ekle
                        if image_urls and product_id_str not in products_dict:
                            products_dict[product_id_str] = {
                                "product_id": product_id_str,
                                "product_name": line.get("productName") or line.get("product_name") or None,
                                "image_count": len(image_urls),
                                "has_primary": True,
                                "has_trendyol_images": True
                            }
                        elif image_urls and product_id_str in products_dict:
                            if products_dict[product_id_str]["image_count"] == 0:
                                products_dict[product_id_str]["image_count"] = len(image_urls)
                                products_dict[product_id_str]["has_trendyol_images"] = True
                                products_dict[product_id_str]["has_primary"] = True
                    except:
                        continue
            
            print(f"[Images] Siparişlerden {len([p for p in products_dict.values() if p.get('has_trendyol_images')])} ürün görseli bulundu")
            
            # Products API'yi de deneyelim (403 hatası olsa bile)
            try:
                trendyol_products = await get_trendyol_products_with_images()
                if trendyol_products:
                    print(f"[Images] Products API'den {len(trendyol_products)} ürün görseli bulundu")
                    for product_id, image_count in trendyol_products.items():
                        if product_id in products_dict:
                            if products_dict[product_id]["image_count"] == 0:
                                products_dict[product_id]["image_count"] = image_count
                            products_dict[product_id]["has_trendyol_images"] = (image_count > 0)
                            if image_count > 0 and not products_dict[product_id]["has_primary"]:
                                products_dict[product_id]["has_primary"] = True
                        else:
                            products_dict[product_id] = {
                                "product_id": product_id,
                                "product_name": None,
                                "image_count": image_count,
                                "has_primary": (image_count > 0),
                                "has_trendyol_images": (image_count > 0)
                            }
            except Exception as e:
                print(f"[Images] Products API denemesi başarısız (beklenen): {e}")
        except Exception as e:
            print(f"[Images] Trendyol görsel kontrolü hatası: {e}")
            import traceback
            traceback.print_exc()
    
    # Yerel görsel bilgilerini ekle
    if UPLOAD_DIR.exists():
        for product_dir in UPLOAD_DIR.iterdir():
            if product_dir.is_dir() and product_dir.name != "__pycache__":
                product_id = product_dir.name
                metadata_file = product_dir / ".metadata.json"
                
                if metadata_file.exists():
                    try:
                        import json
                        with open(metadata_file, "r", encoding="utf-8") as f:
                            metadata = json.load(f)
                        
                        image_count = len(metadata.get("images", []))
                        has_primary = any(img.get("is_primary", False) for img in metadata.get("images", []))
                        
                        if product_id in products_dict:
                            products_dict[product_id]["image_count"] += image_count
                            if has_primary:
                                products_dict[product_id]["has_primary"] = True
                        else:
                            # Ürün listede yoksa ekle
                            product_name = None
                            if _db_available and db:
                                try:
                                    product = db.query(Product).filter(Product.store_id == store.id, Product.product_id == product_id).first()
                                    if product:
                                        product_name = product.product_name
                                except:
                                    pass
                            
                            products_dict[product_id] = {
                                "product_id": product_id,
                                "product_name": product_name,
                                "image_count": image_count,
                                "has_primary": has_primary,
                                "has_trendyol_images": False
                            }
                    except:
                        continue
    
    # Listeye çevir ve sırala (görseli olanlar önce)
    products_list = list(products_dict.values())
    products_list.sort(key=lambda x: (x["image_count"] == 0, x["product_name"] or x["product_id"]))
    
    return products_list


async def get_trendyol_products_with_images() -> Dict[str, int]:
    """
    Trendyol API'den tüm ürünlerin görsel sayılarını çeker
    """
    import os
    import requests
    import base64
    
    api_key = os.getenv("TRENDYOL_API_KEY")
    api_secret = os.getenv("TRENDYOL_API_SECRET")
    supplier_id = os.getenv("TRENDYOL_SUPPLIER_ID")
    
    if not all([api_key, api_secret, supplier_id]):
        return {}
    
    products_with_images = {}
    
    try:
        url = f"https://api.trendyol.com/sapigw/suppliers/{supplier_id}/products"
        
        auth_string = f"{api_key}:{api_secret}"
        auth_bytes = auth_string.encode('ascii')
        auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
        
        headers = {
            "Authorization": f"Basic {auth_b64}",
            "Content-Type": "application/json"
        }
        
        page = 0
        page_size = 500
        total_items_processed = 0
        
        while page < 10:  # Maksimum 10 sayfa
            params = {
                "page": page,
                "size": page_size,
                "approved": "true"
            }
            
            response = requests.get(url, headers=headers, params=params, timeout=30)
            
            if response.status_code != 200:
                print(f"[Images] Trendyol API yanıt hatası: {response.status_code}")
                if response.status_code == 401:
                    print(f"[Images] Authentication hatası - API key/secret kontrol edin")
                break
            
            data = response.json()
            items = data.get("content", []) or data.get("items", []) or []
            
            if not items:
                print(f"[Images] Sayfa {page}: Ürün bulunamadı")
                break
            
            print(f"[Images] Sayfa {page}: {len(items)} ürün bulundu")
            total_items_processed += len(items)
            
            # İlk ürünün yapısını göster (debug)
            if page == 0 and len(items) > 0:
                first_item = items[0]
                print(f"[Images] İlk ürün keys: {list(first_item.keys())[:40]}")
                # Görsel ile ilgili tüm keys'leri göster
                image_keys = [k for k in first_item.keys() if 'image' in k.lower() or 'media' in k.lower() or 'photo' in k.lower()]
                print(f"[Images] Görsel ile ilgili keys: {image_keys}")
                if image_keys:
                    for key in image_keys[:5]:
                        print(f"[Images] {key}: {str(first_item.get(key))[:200]}")
            
            for item in items:
                # Ürün ID'sini al
                product_id = (
                    item.get("barcode") or 
                    item.get("merchantSku") or 
                    item.get("productId") or
                    item.get("productCode") or
                    str(item.get("id", "")) if item.get("id") else ""
                )
                
                if not product_id:
                    continue
                
                product_id_str = str(product_id)
                
                # Görselleri say - tüm olası alanları kontrol et
                images_found = []
                
                # Tüm olası görsel alanlarını kontrol et
                image_fields = [
                    "images", "productImages", "mediaUrls", "imageUrls", 
                    "imageList", "productImageList", "mediaList",
                    "mainImage", "thumbnailImage", "image", "productImage",
                    "imageUrl", "productImageUrl", "mediaUrl"
                ]
                
                for field in image_fields:
                    value = item.get(field)
                    if value:
                        if isinstance(value, str) and value.startswith("http"):
                            images_found.append(value)
                        elif isinstance(value, list):
                            for img in value:
                                if isinstance(img, str) and img.startswith("http"):
                                    images_found.append(img)
                                elif isinstance(img, dict):
                                    img_url = (
                                        img.get("url") or 
                                        img.get("imageUrl") or 
                                        img.get("image") or
                                        img.get("mediaUrl") or
                                        img.get("src")
                                    )
                                    if img_url and isinstance(img_url, str) and img_url.startswith("http"):
                                        images_found.append(img_url)
                
                # Eğer hala görsel bulunamadıysa, tüm değerleri tarayalım
                if not images_found:
                    for key, value in item.items():
                        if isinstance(value, str) and ("http" in value.lower() or "image" in key.lower()):
                            if value.startswith("http") and any(ext in value.lower() for ext in [".jpg", ".jpeg", ".png", ".gif", ".webp"]):
                                images_found.append(value)
                        elif isinstance(value, list) and len(value) > 0:
                            for v in value:
                                if isinstance(v, str) and v.startswith("http"):
                                    images_found.append(v)
                
                # Duplicate'leri kaldır
                image_count = len(set(images_found))
                
                if image_count > 0:
                    products_with_images[product_id_str] = image_count
                    if len(products_with_images) <= 5:  # İlk 5 ürünü logla
                        print(f"[Images] Ürün {product_id_str}: {image_count} görsel bulundu")
                elif page == 0 and len(products_with_images) < 3:
                    # İlk sayfada görseli olmayan ilk 3 ürünü de logla
                    print(f"[Images] Ürün {product_id_str}: Görsel bulunamadı (keys: {list(item.keys())[:20]})")
            
            if len(items) < page_size:
                break
            
            page += 1
        
        print(f"[Images] Toplam {len(products_with_images)} üründe görsel bulundu")
        return products_with_images
    
    except Exception as e:
        print(f"[Images] Trendyol API hatası: {e}")
        return {}

