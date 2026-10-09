"""
Background Sync Service
Trendyol API'den verileri çekip database'e kaydeder
"""
import asyncio
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from database.db import get_async_session_maker
from database.models import Product, Order, OrderLine, CompetitorPrice, SyncLog
import os
import requests
import base64
from typing import List, Dict, Optional
import json


class SyncService:
    """Trendyol API'den veri senkronizasyonu.

    Wave3 per-store: `creds` verilirse O MAĞAZANIN anahtarıyla çeker ve verileri
    `store_id`'ye yazar. Verilmezse legacy davranış: env TRENDYOL_* + store_id=1
    (mevcut background sync ve eski çağrılar bozulmasın diye korunur)."""

    def __init__(self, creds=None, store_id: int = 1):
        if creds is not None:
            self.api_key = creds.api_key
            self.api_secret = creds.api_secret
            self.supplier_id = creds.supplier_id
            self.store_id = creds.store_id or store_id
        else:
            self.api_key = os.getenv("TRENDYOL_API_KEY")
            self.api_secret = os.getenv("TRENDYOL_API_SECRET")
            self.supplier_id = os.getenv("TRENDYOL_SUPPLIER_ID")
            self.store_id = store_id
    
    def _get_headers(self):
        """API headers oluştur"""
        if not all([self.api_key, self.api_secret]):
            return None
        
        auth_string = f"{self.api_key}:{self.api_secret}"
        auth_bytes = auth_string.encode('ascii')
        auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
        
        return {
            "Authorization": f"Basic {auth_b64}",
            "Content-Type": "application/json",
            "User-Agent": "Trendyol-AI-Assistant/1.0"
        }
    
    async def _log_sync(self, sync_type: str, status: str, records_synced: int = 0, error_message: str = None):
        """Senkronizasyon logu kaydet"""
        session_maker = get_async_session_maker()
        if session_maker is None:
            # Fallback: sync session kullan
            from database.db import SessionLocal
            db = SessionLocal()
            try:
                log = SyncLog(
                    store_id=self.store_id,
                    sync_type=sync_type,
                    status=status,
                    records_synced=records_synced,
                    error_message=error_message,
                    started_at=datetime.now(),
                    completed_at=datetime.now() if status != 'running' else None
                )
                db.add(log)
                db.commit()
            finally:
                db.close()
            return
        
        async with session_maker() as session:
            log = SyncLog(
                store_id=self.store_id,
                sync_type=sync_type,
                status=status,
                records_synced=records_synced,
                error_message=error_message,
                started_at=datetime.now(),
                completed_at=datetime.now() if status != 'running' else None
            )
            session.add(log)
            await session.commit()
    
    async def sync_products(self) -> int:
        """Ürünleri Trendyol API'den çekip database'e kaydet"""
        try:
            await self._log_sync('products', 'running')
            
            headers = self._get_headers()
            if not headers:
                await self._log_sync('products', 'error', error_message="API credentials missing")
                return 0
            
            # w3-hardening (2026-09-26): eski api.trendyol.com/sapigw/suppliers/{id}/products
            # ucu V1'di, 10 Ağustos 2026'da geçersiz olmuş — bu yüzden bu fonksiyon HER ZAMAN
            # 0 ürün senkronize ediyordu ("Synced 0 products" log'u boyunca yanıltıcı şekilde
            # normal görünüyordu). Gerçek V2 ucuna taşındı (gerçek çağrıyla doğrulandı,
            # totalElements>0). V2 şeması FARKLI: ürün başına `variants` listesi var, her
            # variant kendi barcode/stock/price'ına sahip — burada düzleştiriliyor.
            url = f"https://apigw.trendyol.com/integration/product/sellers/{self.supplier_id}/products/approved"
            products_synced = 0

            session_maker = get_async_session_maker()
            if session_maker is None:
                # Ghost mode: database yoksa sessizce çık
                print("[SyncService] Database not available (ghost mode), skipping sync")
                return 0
            async with session_maker() as session:
                page = 0
                page_size = 100  # bu ucun kendi sınırı (gerçek çağrıyla doğrulandı: max 100)

                while True:
                    params = {
                        "page": page,
                        "size": page_size,
                    }

                    response = requests.get(url, headers=headers, params=params, timeout=30)

                    if response.status_code != 200:
                        break

                    data = response.json()
                    products_page = data.get("content", []) or []

                    if not products_page:
                        break

                    # Her ürünün variant'larını düz bir "item" satırına çevir (V1 uyumlu alan adları)
                    flat_items = []
                    for p in products_page:
                        title = p.get("title")
                        category_name = (p.get("category") or {}).get("name")
                        for v in (p.get("variants") or []):
                            stock = v.get("stock") or {}
                            price_obj = v.get("price") or {}
                            flat_items.append({
                                "barcode": v.get("barcode"),
                                "merchantSku": v.get("stockCode") or v.get("barcode"),
                                "productId": p.get("contentId"),
                                "contentId": p.get("contentId"),
                                "title": title,
                                "categoryName": category_name,
                                "stockQuantity": stock.get("quantity", 0),
                                "salePrice": price_obj.get("salePrice"),
                                "listPrice": price_obj.get("listPrice"),
                                "images": p.get("images") or [],  # w3-image-url-store: ürün-seviyesi, varyantlar arasında paylaşılır
                            })

                    for item in flat_items:
                        try:
                            # Operatör önceliği hatası düzeltildi (bkz. inventory.py aynı fix) —
                            # ternary or-zincirinden düşük öncelikli, parantezsiz hep "" veriyordu.
                            product_id = (
                                item.get("barcode") or
                                item.get("merchantSku") or
                                item.get("productId") or
                                (str(item.get("id", "")) if item.get("id") else "")
                            )

                            if not product_id:
                                continue

                            product_id_str = str(product_id)

                            # Fiyatı al
                            price = (
                                item.get("salePrice") or
                                item.get("listPrice") or
                                item.get("price") or
                                0
                            )

                            if isinstance(price, str):
                                try:
                                    price = float(price.replace(",", "."))
                                except:
                                    price = 0.0

                            price = float(price) if price else 0.0

                            # Database'de var mı kontrol et
                            result = await session.execute(
                                select(Product).where(
                                    Product.store_id == self.store_id,
                                    Product.product_id == product_id_str,
                                )
                            )
                            existing = result.scalar_one_or_none()

                            content_id = item.get("contentId")
                            content_id_str = str(content_id) if content_id else None

                            # w3-image-url-store: contentId'den kalıpla ÜRETİLEMEZ (image-url-truth.md,
                            # Jim), API'nin döndürdüğü ham images[0].url HAM olarak saklanır. Yoksa None
                            # — uydurma URL üretilmez.
                            images = item.get("images") or []
                            image_url = images[0].get("url") if images and isinstance(images[0], dict) else None

                            if existing:
                                # Güncelle
                                existing.product_name = item.get("title") or item.get("productName") or "Bilinmeyen Ürün"
                                existing.category = item.get("categoryName") or ""
                                existing.barcode = item.get("barcode") or ""
                                existing.current_price = price
                                existing.last_price_update = datetime.now()
                                existing.updated_at = datetime.now()
                                if content_id_str:
                                    existing.content_id = content_id_str
                                if image_url:
                                    existing.image_url = image_url
                            else:
                                # Yeni ekle
                                new_product = Product(
                                    store_id=self.store_id,
                                    product_id=product_id_str,
                                    product_name=item.get("title") or item.get("productName") or "Bilinmeyen Ürün",
                                    category=item.get("categoryName") or "",
                                    barcode=item.get("barcode") or "",
                                    current_price=price,
                                    content_id=content_id_str,
                                    image_url=image_url,
                                    last_price_update=datetime.now()
                                )
                                session.add(new_product)

                            products_synced += 1
                        except Exception as e:
                            continue

                    if len(products_page) < page_size:
                        break

                    page += 1
                    if page > 10:  # Maksimum 10 sayfa
                        break
                
                await session.commit()
            
            await self._log_sync('products', 'success', records_synced=products_synced)
            print(f"[SyncService] Synced {products_synced} products")
            return products_synced
        
        except Exception as e:
            await self._log_sync('products', 'error', error_message=str(e))
            print(f"[SyncService] Error syncing products: {e}")
            return 0
    
    async def sync_orders(self, days: int = 30) -> int:
        """Siparişleri Trendyol API'den çekip database'e kaydet"""
        try:
            await self._log_sync('orders', 'running')
            
            headers = self._get_headers()
            if not headers:
                await self._log_sync('orders', 'error', error_message="API credentials missing")
                return 0
            
            # w3-hardening (2026-09-26): resmi Order Integration V2 ucuna taşındı
            # (gerçek çağrıyla doğrulandı — bkz. utils/store_trendyol.fetch_orders).
            url = f"https://apigw.trendyol.com/integration/order/sellers/{self.supplier_id}/v2/orders"
            orders_synced = 0

            session_maker = get_async_session_maker()
            if session_maker is None:
                # Ghost mode: database yoksa sessizce çık
                print("[SyncService] Database not available (ghost mode), skipping sync")
                return 0
            async with session_maker() as session:
                page = 0
                page_size = 200  # bu ucun kendi sınırı (max 200, resmi dokümanla doğrulandı)
                
                while True:
                    params = {
                        "page": page,
                        "size": page_size,
                        "orderByField": "PackageLastModifiedDate",
                        "orderByDirection": "DESC"
                    }
                    
                    response = requests.get(url, headers=headers, params=params, timeout=30)
                    
                    if response.status_code != 200:
                        break
                    
                    data = response.json()
                    orders = data.get("content", [])
                    
                    if not orders:
                        break
                    
                    for order_data in orders:
                        try:
                            order_id = order_data.get("id") or order_data.get("orderId") or order_data.get("orderNumber")
                            if not order_id:
                                continue
                            
                            order_id_str = str(order_id)
                            
                            # Tarih parse et
                            order_date_str = order_data.get("orderDate") or order_data.get("order_date")
                            order_date = None
                            if order_date_str:
                                if isinstance(order_date_str, (int, float)):
                                    # Trendyol orderDate = epoch ms (13 hane) veya epoch s
                                    try:
                                        ts = float(order_date_str)
                                        if ts > 1e12:  # milisaniye
                                            ts = ts / 1000.0
                                        order_date = datetime.fromtimestamp(ts)
                                    except:
                                        pass
                                elif isinstance(order_date_str, str):
                                    try:
                                        if order_date_str.isdigit():
                                            ts = float(order_date_str)
                                            if ts > 1e12:
                                                ts = ts / 1000.0
                                            order_date = datetime.fromtimestamp(ts)
                                        elif 'T' in order_date_str:
                                            order_date = datetime.fromisoformat(order_date_str.replace('Z', '+00:00'))
                                        else:
                                            order_date = datetime.strptime(order_date_str, "%Y-%m-%d %H:%M:%S")
                                    except:
                                        try:
                                            order_date = datetime.strptime(order_date_str.split('T')[0], "%Y-%m-%d")
                                        except:
                                            pass
                            
                            # Database'de var mı kontrol et
                            result = await session.execute(
                                select(Order).where(
                                    Order.store_id == self.store_id,
                                    Order.order_id == order_id_str,
                                )
                            )
                            existing = result.scalar_one_or_none()

                            if existing:
                                # Güncelle
                                existing.order_number = order_data.get("orderNumber") or ""
                                existing.order_date = order_date
                                existing.status = order_data.get("status") or ""
                                existing.total_amount = float(order_data.get("totalPrice", 0) or 0)
                                existing.customer_name = order_data.get("customerFirstName", "") + " " + order_data.get("customerLastName", "")
                                existing.cargo_tracking_number = order_data.get("cargoTrackingNumber") or ""
                                existing.raw_data = json.dumps(order_data)
                                existing.updated_at = datetime.now()
                            else:
                                # Yeni ekle
                                new_order = Order(
                                    store_id=self.store_id,
                                    order_id=order_id_str,
                                    order_number=order_data.get("orderNumber") or "",
                                    order_date=order_date,
                                    status=order_data.get("status") or "",
                                    total_amount=float(order_data.get("totalPrice", 0) or 0),
                                    customer_name=order_data.get("customerFirstName", "") + " " + order_data.get("customerLastName", ""),
                                    cargo_tracking_number=order_data.get("cargoTrackingNumber") or "",
                                    raw_data=json.dumps(order_data)
                                )
                                session.add(new_order)
                                await session.flush()  # order_id'yi almak için
                            
                            # Order lines'ı kaydet
                            lines = order_data.get("lines", []) or order_data.get("orderLines", []) or []
                            if isinstance(lines, dict):
                                lines = [lines]
                            
                            for line in lines:
                                try:
                                    product_id = (
                                        line.get("productId") or 
                                        line.get("product_id") or 
                                        line.get("barcode") or 
                                        str(line.get("id", "")) if line.get("id") else ""
                                    )
                                    
                                    if not product_id:
                                        continue
                                    
                                    product_id_str = str(product_id)
                                    
                                    # Unit price hesapla
                                    unit_price = (
                                        line.get("price") or 
                                        line.get("salePrice") or 
                                        line.get("unitPrice") or
                                        0
                                    )
                                    
                                    if not unit_price:
                                        amount = line.get("amount", 0)
                                        quantity = line.get("quantity", 1) or 1
                                        if amount and quantity > 0:
                                            unit_price = amount / quantity
                                    
                                    if isinstance(unit_price, str):
                                        try:
                                            unit_price = float(unit_price.replace(",", "."))
                                        except:
                                            unit_price = 0.0
                                    
                                    unit_price = float(unit_price) if unit_price else 0.0
                                    quantity = int(line.get("quantity", 1) or 1)
                                    total_price = unit_price * quantity
                                    
                                    # Order line var mı kontrol et
                                    line_result = await session.execute(
                                        select(OrderLine).where(
                                            OrderLine.store_id == self.store_id,
                                            OrderLine.order_id == order_id_str,
                                            OrderLine.product_id == product_id_str
                                        )
                                    )
                                    existing_line = line_result.scalar_one_or_none()

                                    if not existing_line:
                                        new_line = OrderLine(
                                            store_id=self.store_id,
                                            order_id=order_id_str,
                                            product_id=product_id_str,
                                            product_name=line.get("productName") or line.get("product_name") or "",
                                            quantity=quantity,
                                            unit_price=unit_price,
                                            total_price=total_price,
                                            category=line.get("categoryName") or ""
                                        )
                                        session.add(new_line)
                                except Exception as e:
                                    continue
                            
                            orders_synced += 1
                        except Exception as e:
                            continue
                    
                    if len(orders) < page_size:
                        break
                    
                    page += 1
                    if page > 20:  # Maksimum 20 sayfa (10,000 sipariş)
                        break
                
                await session.commit()

            # Wave3 data-followup: Trendyol products API çoğu hesap için boş dönebiliyor
            # (bu hesapta 0 ürün senkronize oluyor) → Product tablosu boş kalıyor → Ürün
            # Ayarları hiç ürün göstermiyor → kullanıcı maliyet/desi giremiyor → kâr
            # hesaplanamıyor. ÇÖZÜM: siparişlerde GÖRÜLEN ürünler için Product stub'ları
            # oluştur (melontik davranışı: sattığın ürüne maliyet girersin). Böylece Ürün
            # Ayarları satılan tüm ürünleri listeler.
            await self._backfill_products_from_lines()
            # w3-product-image-backend: content_id boş kalan ürünleri (stub'lar +
            # Product tablosu Trendyol Products API'den her zaman geliyor olmasa da)
            # raw sipariş verisinden geriye dönük doldur.
            await self._backfill_content_ids_from_raw_orders()

            await self._log_sync('orders', 'success', records_synced=orders_synced)
            print(f"[SyncService] Synced {orders_synced} orders")
            return orders_synced

        except Exception as e:
            await self._log_sync('orders', 'error', error_message=str(e))
            print(f"[SyncService] Error syncing orders: {e}")
            return 0

    async def _backfill_products_from_lines(self) -> int:
        """order_lines'ta görülen ama products tablosunda olmayan (store_id, product_id)
        için stub Product satırı oluşturur (default_cost=0, desi=0). Mevcut ürünlere
        DOKUNMAZ (kullanıcının girdiği maliyet/desi korunur). Bu store_id'ye scoped."""
        session_maker = get_async_session_maker()
        if session_maker is None:
            return 0
        created = 0
        try:
            async with session_maker() as session:
                # Bu store'un order_lines'ındaki distinct product'lar (son satır bilgisiyle)
                line_rows = await session.execute(
                    select(OrderLine).where(OrderLine.store_id == self.store_id)
                )
                lines = line_rows.scalars().all()
                # Mevcut product_id'ler
                prod_rows = await session.execute(
                    select(Product.product_id).where(Product.store_id == self.store_id)
                )
                existing_ids = {r[0] for r in prod_rows.all()}

                seen = set()
                for ln in lines:
                    pid = str(ln.product_id or "")
                    if not pid or pid in existing_ids or pid in seen:
                        continue
                    seen.add(pid)
                    session.add(Product(
                        store_id=self.store_id,
                        product_id=pid,
                        product_name=ln.product_name or f"Ürün {pid}",
                        category=ln.category or "",
                        barcode=pid,
                        current_price=float(ln.unit_price or 0.0),
                        default_cost=0.0,
                        desi=0.0,
                    ))
                    created += 1
                if created:
                    await session.commit()
            if created:
                print(f"[SyncService] Backfilled {created} product stubs from order lines (store_id={self.store_id})")
        except Exception as e:
            print(f"[SyncService] Backfill error (store_id={self.store_id}): {e}")
            return 0
        return created

    async def _backfill_content_ids_from_raw_orders(self) -> int:
        """content_id'si BOŞ olan Product satırları için Order.raw_data'daki ham
        sipariş satırlarından (line['barcode'] -> line['contentId']) content_id
        doldurur. Trendyol Products API senkronu content_id'yi zaten dolduruyor
        (bkz. sync_products) — bu sadece o senkrondan önce/dışında oluşmuş satırlar
        (ör. sipariş-satırından türetilmiş stub ürünler) için geriye dönük telafi.
        Mevcut content_id'ye SAHİP satırlara dokunmaz."""
        session_maker = get_async_session_maker()
        if session_maker is None:
            return 0
        updated = 0
        try:
            async with session_maker() as session:
                prod_rows = await session.execute(
                    select(Product).where(
                        Product.store_id == self.store_id,
                        Product.content_id.is_(None),
                    )
                )
                missing = {p.product_id: p for p in prod_rows.scalars().all()}
                if not missing:
                    return 0

                order_rows = await session.execute(
                    select(Order.raw_data).where(
                        Order.store_id == self.store_id,
                        Order.raw_data.isnot(None),
                    )
                )
                for (raw,) in order_rows.all():
                    if not missing:
                        break
                    if not raw:
                        continue
                    try:
                        order_data = json.loads(raw)
                    except Exception:
                        continue
                    lines = order_data.get("lines", []) or order_data.get("orderLines", []) or []
                    if isinstance(lines, dict):
                        lines = [lines]
                    for line in lines:
                        barcode = line.get("barcode")
                        content_id = line.get("contentId")
                        if not barcode or not content_id:
                            continue
                        prod = missing.pop(str(barcode), None)
                        if prod:
                            prod.content_id = str(content_id)
                            updated += 1

                if updated:
                    await session.commit()
            if updated:
                print(f"[SyncService] Backfilled content_id for {updated} products from raw orders (store_id={self.store_id})")
        except Exception as e:
            print(f"[SyncService] content_id backfill error (store_id={self.store_id}): {e}")
            return 0
        return updated

    async def sync_all(self):
        """Tüm verileri senkronize et"""
        print("[SyncService] Starting full sync...")
        products_count = await self.sync_products()
        orders_count = await self.sync_orders()
        print(f"[SyncService] Full sync complete: {products_count} products, {orders_count} orders")


def _get_connected_trendyol_creds() -> List:
    """store_credentials'taki Trendyol'a bağlı her mağaza için çözülmüş creds listesi.
    (Wave3 per-store sync — background/manuel senkron her mağazayı kendi anahtarıyla çeker.)"""
    from database.db import SessionLocal
    from database.models import StoreCredential, Store
    from utils.store_trendyol import resolve_trendyol_creds

    out = []
    db = SessionLocal()
    try:
        rows = (
            db.query(StoreCredential)
            .filter(StoreCredential.platform == "trendyol", StoreCredential.is_connected == True)  # noqa: E712
            .all()
        )
        for cr in rows:
            store = db.query(Store).filter(Store.id == cr.store_id).first()
            if not store:
                continue
            try:
                out.append(resolve_trendyol_creds(db, store))
            except Exception:
                continue
    finally:
        db.close()
    return out


async def sync_all_stores():
    """Tüm mağazaları senkronize et (Wave3 per-store).
    - Trendyol'a bağlı HER mağaza kendi anahtarıyla senkronize edilir → verileri o store_id'ye yazılır.
    - LEGACY KORUMA: store_id=1'in kendi credential'ı yoksa ama env TRENDYOL_* varsa, eski
      env-tabanlı yolla store_id=1 yine senkronize edilir (mevcut davranış bozulmaz)."""
    connected = _get_connected_trendyol_creds()
    connected_ids = {c.store_id for c in connected}

    # Legacy fallback (store_id=1 kendi credential'ı yoksa ama env varsa)
    if 1 not in connected_ids and os.getenv("TRENDYOL_API_KEY") and os.getenv("TRENDYOL_SUPPLIER_ID"):
        try:
            await SyncService(store_id=1).sync_all()
        except Exception as e:
            print(f"[SyncAllStores] legacy store_id=1 env sync error: {e}")

    # Per-store: bağlı her mağaza kendi anahtarıyla
    for creds in connected:
        try:
            await SyncService(creds=creds, store_id=creds.store_id).sync_all()
        except Exception as e:
            print(f"[SyncAllStores] store_id={creds.store_id} sync error: {e}")


# Background task için
async def background_sync_task(interval_minutes: int = 5):
    """Arka planda periyodik senkronizasyon (varsayılan: 5 dakika) — TÜM mağazalar per-store."""
    try:
        # İlk senkronizasyonu hemen yap
        print(f"[BackgroundSync] Starting background sync (interval: {interval_minutes} minutes)")

        while True:
            try:
                print(f"[BackgroundSync] Running scheduled per-store sync...")
                await sync_all_stores()
                print(f"[BackgroundSync] Sync completed. Next sync in {interval_minutes} minutes.")
            except Exception as e:
                # Ghost mode: hataları sessizce yakala
                print(f"[BackgroundSync] Warning (ghost mode): {e}")
            
            # Belirtilen süre kadar bekle
            await asyncio.sleep(interval_minutes * 60)
    except Exception as e:
        # Ghost mode: task başlatılamazsa sessizce çık
        print(f"[BackgroundSync] Background sync disabled (ghost mode): {e}")
        # Sonsuz döngü yerine sessizce bekle
        while True:
            await asyncio.sleep(interval_minutes * 60)

