"""
Ürün Yönetimi Router
Ürün listesi, detayları ve performans analizi
"""
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from collections import defaultdict
import os
import io
import csv
import requests
import base64

from sqlalchemy.orm import Session
from database.db import get_db
from database.models import Product, Store, ProductChangeHistory
from security import get_current_store
from utils.store_trendyol import resolve_trendyol_creds, fetch_orders, fetch_products
from utils.image_cdn import trendyol_thumbnail_url
from utils.change_history import record_change
from utils.numeric_validation import numeric_field_error, COST_MAX, DESI_MAX

router = APIRouter()


# ---------------------------------------------------------------------------
# Wave2b — Ürün Ayarları (maliyet + desi) — store_id-scoped, lokal DB.
# NOT: bu endpoint'ler literal "/settings" yolunu kullandığı için AŞAĞIDAKİ
# GET /{product_id} (canlı Trendyol API) rotasından ÖNCE tanımlanmalı — aksi halde
# FastAPI "/settings"i product_id="settings" olarak yakalar. Bilinçli sıralama.
# ---------------------------------------------------------------------------
class ProductSettingsUpdate(BaseModel):
    default_cost: float
    desi: float = 0.0

    @field_validator("default_cost")
    @classmethod
    def _cost_valid(cls, v):
        err = numeric_field_error(v, "maliyet", COST_MAX)
        if err:
            raise ValueError(err)
        return v

    @field_validator("desi")
    @classmethod
    def _desi_valid(cls, v):
        err = numeric_field_error(v, "desi", DESI_MAX)
        if err:
            raise ValueError(err)
        return v


@router.get("/settings")
async def get_product_settings(
    store: Store = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    """Ürün Ayarları sayfası: store'un TÜM ürünlerinin maliyet+desi'si (satış yapmasa
    da — kullanıcı satıştan önce de maliyet girebilmeli). Product tablosu boşsa []."""
    products = db.query(Product).filter(Product.store_id == store.id).all()
    return {
        "products": [
            {
                "product_id": p.product_id,
                "product_name": p.product_name,
                "barcode": p.barcode,
                "category": p.category,
                "default_cost": p.default_cost,
                "desi": p.desi,
                "thumbnail_url": trendyol_thumbnail_url(p.image_url),
            }
            for p in products
        ]
    }


@router.put("/settings/{product_id}")
async def update_product_settings(
    product_id: str,
    body: ProductSettingsUpdate,
    store: Store = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    """Bir ürünün maliyet+desi'sini günceller. Kâr hesapları (compute_profitability)
    Product.default_cost okuduğu için maliyet girilince Dashboard/Kâr Marjı otomatik doğrulur."""
    product = db.query(Product).filter(Product.store_id == store.id, Product.product_id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Ürün bulunamadı")
    record_change(db, store.id, product.product_id, "default_cost", product.default_cost, body.default_cost, "single")
    record_change(db, store.id, product.product_id, "desi", product.desi, body.desi, "single")
    product.default_cost = body.default_cost
    product.desi = body.desi
    db.commit()
    db.refresh(product)
    return {
        "product_id": product.product_id,
        "product_name": product.product_name,
        "default_cost": product.default_cost,
        "desi": product.desi,
    }


# ---------------------------------------------------------------------------
# w3-grouped-settings-api — Ürün Ayarları'nı content_id (Trendyol ürün kimliği)
# başına GRUPLAR: beden varyantları (aynı content_id, farklı barcode/product_id)
# tek satırda toplanır. Sözleşme god tarafından tanımlandı, Oscar paralel bağlanıyor
# — değiştirmeden önce god'a danış. Mevcut /settings ve /settings/{product_id}
# AYNEN kalır (geriye dönük uyumluluk).
# ---------------------------------------------------------------------------
def _compute_grouped_products(db: Session, store_id: int) -> List[Dict[str, Any]]:
    """content_id başına tek kayıt üretir (paylaşılan: JSON endpoint + CSV template
    aynı gruplamayı kullanır, mantık tek yerde). content_id NULL olan ürünler
    kaybolmasın diye kendi tek-varyantlı grubu olarak döner."""
    products = db.query(Product).filter(Product.store_id == store_id).all()

    groups: Dict[str, List[Product]] = {}
    for p in products:
        # content_id yoksa ürünün kendi product_id'siyle ayrıştırılmış tekil grup —
        # gerçek bir content_id ile asla çakışmaz (Trendyol contentId'leri sayısaldır,
        # bu anahtar sabit bir string önekiyle başlıyor).
        key = p.content_id if p.content_id else f"__no_content_id__{p.product_id}"
        groups.setdefault(key, []).append(p)

    result = []
    for variants in groups.values():
        first = variants[0]
        costs = {v.default_cost for v in variants}
        desis = {v.desi for v in variants}
        prices = [v.current_price for v in variants if v.current_price is not None]
        result.append({
            "content_id": first.content_id,
            "product_name": first.product_name,
            "category": first.category,
            "thumbnail_url": trendyol_thumbnail_url(first.image_url),
            "variant_count": len(variants),
            "variant_product_ids": [v.product_id for v in variants],
            "price_min": min(prices) if prices else None,
            "price_max": max(prices) if prices else None,
            "default_cost": first.default_cost,
            "desi": first.desi,
            "cost_mixed": len(costs) > 1,
            "desi_mixed": len(desis) > 1,
        })

    result.sort(key=lambda r: (r["product_name"] or ""))
    return result


@router.get("/settings/grouped")
async def get_product_settings_grouped(
    store: Store = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    """content_id başına tek kayıt döner. content_id NULL olan ürünler kaybolmasın
    diye kendi tek-varyantlı grubu olarak döner (content_id=null, variant_count=1)."""
    result = _compute_grouped_products(db, store.id)
    return {"products": result, "count": len(result)}


class GroupSettingsUpdate(BaseModel):
    default_cost: float
    desi: float = 0.0

    @field_validator("default_cost")
    @classmethod
    def _cost_valid(cls, v):
        err = numeric_field_error(v, "maliyet", COST_MAX)
        if err:
            raise ValueError(err)
        return v

    @field_validator("desi")
    @classmethod
    def _desi_valid(cls, v):
        err = numeric_field_error(v, "desi", DESI_MAX)
        if err:
            raise ValueError(err)
        return v


@router.put("/settings/group/{content_id}")
async def update_product_settings_group(
    content_id: str,
    body: GroupSettingsUpdate,
    store: Store = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    """Aynı content_id'ye sahip TÜM beden varyantlarına tek seferde maliyet+desi
    yazar. content_id=null grupları için bu uç KULLANILMAZ — onlar tek varyant
    olduğu için mevcut PUT /settings/{product_id} kullanılır."""
    products = db.query(Product).filter(
        Product.store_id == store.id,
        Product.content_id == content_id,
    ).all()
    if not products:
        raise HTTPException(status_code=404, detail="Bu content_id'ye sahip ürün bulunamadı")

    for p in products:
        record_change(db, store.id, p.product_id, "default_cost", p.default_cost, body.default_cost, "group")
        record_change(db, store.id, p.product_id, "desi", p.desi, body.desi, "group")
        p.default_cost = body.default_cost
        p.desi = body.desi
    db.commit()

    return {"updated_count": len(products), "content_id": content_id}


# ---------------------------------------------------------------------------
# w3-bulk-cost-entry — CSV indir/doldur/yükle akışı. Format: hive/docs/bulk-cost-csv.md.
# Trendyol'a HİÇBİR yazma çağrısı yok — sadece yerel Product.default_cost/desi.
# ---------------------------------------------------------------------------
def _fmt_tr_number(value: Optional[float]) -> str:
    """175.5 -> '175,50' (Türkçe Excel ondalık gösterimi)."""
    if value is None:
        return ""
    return f"{value:.2f}".replace(".", ",")


def _parse_tr_number(raw: Optional[str]) -> Optional[float]:
    """Türkçe/İngilizce ondalık+binlik ayraç varyasyonlarını tolere eder.
    Boş/None -> None (alan GÜNCELLENMEYECEK demektir, çağıran bunu ayırt eder).
    Ayrıştırılamazsa ValueError fırlatır (çağıran INVALID_NUMBER'a çevirir)."""
    if raw is None:
        return None
    s = raw.strip().strip('"').strip("'")
    if not s:
        return None
    if "," in s and "." in s:
        # Sondaki ayraç ondalık kabul edilir: "1.500,50" veya "1,500.50"
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    return float(s)  # geçersizse ValueError yükselir


def _decode_csv_bytes(raw: bytes) -> str:
    """Önce utf-8-sig (BOM'lu/BOM'suz UTF-8) dener, olmazsa windows-1254
    (Türkçe Excel'in klasik ANSI kod sayfası) dener."""
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("windows-1254")


def _sniff_delimiter(text: str) -> str:
    """';' veya ',' ayraçlarını otomatik algılar (Türkçe Excel varsayılanı ';'dir,
    ama kullanıcı başka bir locale'de kaydetmiş olabilir)."""
    sample = text[:2048]
    try:
        return csv.Sniffer().sniff(sample, delimiters=";,").delimiter
    except csv.Error:
        first_line = sample.splitlines()[0] if sample else ""
        return ";" if first_line.count(";") >= first_line.count(",") else ","


@router.get("/settings/template.csv")
async def download_settings_template_csv(
    store: Store = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    """Mevcut ürün-gruplarını (bkz. /settings/grouped) doldurulabilir CSV şablonu
    olarak indirir. Format: hive/docs/bulk-cost-csv.md — UTF-8-BOM, ';' ayraç,
    virgül ondalık (Türkçe Excel varsayılanı)."""
    groups = _compute_grouped_products(db, store.id)

    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow([
        "content_id", "product_id", "urun_adi", "kategori", "bedenler",
        "varyant_sayisi", "mevcut_maliyet", "mevcut_desi", "yeni_maliyet", "yeni_desi",
    ])
    for g in groups:
        representative_id = g["variant_product_ids"][0] if g["variant_product_ids"] else ""
        writer.writerow([
            g["content_id"] or "",
            representative_id,
            g["product_name"] or "",
            g["category"] or "",
            ",".join(g["variant_product_ids"]),
            g["variant_count"],
            _fmt_tr_number(g["default_cost"]),
            _fmt_tr_number(g["desi"]),
            "",
            "",
        ])

    csv_bytes = output.getvalue().encode("utf-8-sig")
    return StreamingResponse(
        iter([csv_bytes]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=urun_ayarlari_sablonu.csv"},
    )


@router.post("/settings/bulk")
async def bulk_update_product_settings(
    file: UploadFile = File(...),
    dry_run: bool = Query(True),
    store: Store = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    """CSV yükleyip toplu maliyet+desi günceller. Format: hive/docs/bulk-cost-csv.md.
    dry_run=true (varsayılan): HİÇBİR ŞEY YAZILMAZ, sadece özet döner.
    dry_run=false: hatasız satırlar yazılır (satır-bazlı — hatalı satırlar yazılmadan
    diğerleri uygulanır, hepsi-ya-da-hiçbiri değil). Trendyol'a hiçbir çağrı yapılmaz."""
    raw = await file.read()
    try:
        text = _decode_csv_bytes(raw)
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=400,
            detail="Dosya encoding'i çözülemedi (UTF-8 veya Windows-1254 bekleniyor)",
        )

    delimiter = _sniff_delimiter(text)
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)

    all_products = db.query(Product).filter(Product.store_id == store.id).all()
    by_content_id: Dict[str, List[Product]] = {}
    by_product_id: Dict[str, Product] = {}
    for p in all_products:
        by_product_id[p.product_id] = p
        if p.content_id:
            by_content_id.setdefault(p.content_id, []).append(p)

    errors: List[Dict[str, Any]] = []
    to_apply: List[Dict[str, Any]] = []
    skipped = 0

    for row_num, row in enumerate(reader, start=2):  # satır 1 başlık
        content_id = (row.get("content_id") or "").strip()
        product_id = (row.get("product_id") or "").strip()

        if not content_id and not product_id:
            errors.append({
                "row": row_num, "content_id": content_id, "product_id": product_id,
                "error_code": "MISSING_KEY", "detail": "content_id ve product_id ikisi de boş",
            })
            continue

        try:
            new_cost = _parse_tr_number(row.get("yeni_maliyet"))
            new_desi = _parse_tr_number(row.get("yeni_desi"))
        except ValueError:
            errors.append({
                "row": row_num, "content_id": content_id, "product_id": product_id,
                "error_code": "INVALID_NUMBER",
                "detail": f"sayı ayrıştırılamadı: yeni_maliyet={row.get('yeni_maliyet')!r} yeni_desi={row.get('yeni_desi')!r}",
            })
            continue

        if new_cost is None and new_desi is None:
            skipped += 1
            continue

        cost_err = numeric_field_error(new_cost, "maliyet", COST_MAX)
        desi_err = numeric_field_error(new_desi, "desi", DESI_MAX)
        if cost_err or desi_err:
            is_negative = (new_cost is not None and new_cost < 0) or (new_desi is not None and new_desi < 0)
            errors.append({
                "row": row_num, "content_id": content_id, "product_id": product_id,
                "error_code": "NEGATIVE_VALUE" if is_negative else "OUT_OF_RANGE",
                "detail": cost_err or desi_err,
            })
            continue

        if content_id:
            variants = by_content_id.get(content_id)
        else:
            single = by_product_id.get(product_id)
            variants = [single] if single else None

        if not variants:
            errors.append({
                "row": row_num, "content_id": content_id, "product_id": product_id,
                "error_code": "UNKNOWN_KEY", "detail": "bu mağazada eşleşen ürün yok",
            })
            continue

        to_apply.append({
            "variants": variants,
            "new_cost": new_cost,
            "new_desi": new_desi,
            "content_id": content_id or None,
            "product_id": product_id or variants[0].product_id,
            "product_name": variants[0].product_name,
        })

    if dry_run:
        preview = [{
            "content_id": item["content_id"],
            "product_id": item["product_id"],
            "product_name": item["product_name"],
            "old_cost": item["variants"][0].default_cost,
            "new_cost": item["new_cost"] if item["new_cost"] is not None else item["variants"][0].default_cost,
            "old_desi": item["variants"][0].desi,
            "new_desi": item["new_desi"] if item["new_desi"] is not None else item["variants"][0].desi,
            "variant_count": len(item["variants"]),
        } for item in to_apply]
        return {
            "will_update": len(to_apply),
            "skipped": skipped,
            "errors": errors,
            "error_count": len(errors),
            "preview": preview,
        }

    updated_variants = 0
    for item in to_apply:
        for v in item["variants"]:
            if item["new_cost"] is not None:
                record_change(db, store.id, v.product_id, "default_cost", v.default_cost, item["new_cost"], "bulk_csv")
                v.default_cost = item["new_cost"]
            if item["new_desi"] is not None:
                record_change(db, store.id, v.product_id, "desi", v.desi, item["new_desi"], "bulk_csv")
                v.desi = item["new_desi"]
            updated_variants += 1
    db.commit()

    return {
        "updated_groups": len(to_apply),
        "updated_variants": updated_variants,
        "skipped": skipped,
        "errors": errors,
        "error_count": len(errors),
    }


# ---------------------------------------------------------------------------
# w3-write-audit-trail — maliyet/desi/fiyat değişim geçmişi (300 TL vakasının
# dersi). SADECE OKUMA: "şu zaman aralığındaki şu kaynaktan gelen değişiklikler"
# sorgulanabilsin diye. Otomatik geri alma YOK (kapsam dışı) — ama eski_deger
# alanı geri almayı MÜMKÜN kılacak bilgiyi taşıyor.
# ---------------------------------------------------------------------------
@router.get("/change-history")
async def get_product_change_history(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    source: Optional[str] = None,
    product_id: Optional[str] = None,
    limit: int = Query(500, le=2000),
    store: Store = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    """Bu mağazanın maliyet/desi/fiyat değişim geçmişi, en yeniden eskiye.
    Varsayılan aralık: son 30 gün (start_date/end_date verilmezse)."""
    from utils.profitability import resolve_date_range

    start, end = resolve_date_range(start_date, end_date, default_days=30)
    query = db.query(ProductChangeHistory).filter(
        ProductChangeHistory.store_id == store.id,
        ProductChangeHistory.changed_at >= start,
        ProductChangeHistory.changed_at <= end,
    )
    if source:
        query = query.filter(ProductChangeHistory.source == source)
    if product_id:
        query = query.filter(ProductChangeHistory.product_id == product_id)

    rows = query.order_by(ProductChangeHistory.changed_at.desc()).limit(limit).all()
    return {
        "period": {"start_date": start.strftime("%Y-%m-%d"), "end_date": end.strftime("%Y-%m-%d")},
        "changes": [
            {
                "product_id": r.product_id,
                "field": r.field,
                "old_value": r.old_value,
                "new_value": r.new_value,
                "source": r.source,
                "changed_at": r.changed_at.isoformat() if r.changed_at else None,
            }
            for r in rows
        ],
        "count": len(rows),
    }


class ProductPerformance(BaseModel):
    """Ürün performans modeli"""
    product_id: str
    product_name: str
    total_sales: int
    total_revenue: float
    average_price: float
    orders_count: int
    first_sale_date: str
    last_sale_date: str
    sales_trend: str  # "increasing", "decreasing", "stable"
    category: Optional[str] = None
    barcode: Optional[str] = None


def get_trendyol_orders_data(creds=None) -> List[Dict]:
    """Bu mağazanın Trendyol siparişlerini çeker (Wave3: per-store, env DEĞİL).
    creds = utils.store_trendyol.resolve_trendyol_creds(db, store) ile çözülür.
    NOT: creds=None → [] (henüz dönüştürülmemiş çağıranlar için güvenli köprü;
    o router'lar dönüştürülünce gerçek per-store creds geçecek)."""
    if creds is None:
        return []
    return fetch_orders(creds)


def get_trendyol_products_data(creds=None) -> Dict[str, Dict]:
    """Bu mağazanın Trendyol ürün+stok bilgilerini çeker (Wave3: per-store).
    creds ile fetch_products çağırır, sonra product_id-keyed dict'e dönüştürür.
    creds=None → {} (güvenli köprü, yukarıdaki nota bak)."""
    products = {}
    if creds is None:
        return products

    try:
        items_all = fetch_products(creds)
        for item in items_all:
            try:
                # Ürün ID'sini al - tüm olası alanları kontrol et
                product_id = None

                # Önce en yaygın alan adlarını dene
                for key in ["barcode", "merchantSku", "productId", "product_id", "sku", "stockCode"]:
                    value = item.get(key)
                    if value:
                        val_str = str(value).strip()
                        if val_str and val_str.lower() not in ["merchantsku", "stockcode"]:
                            product_id = val_str
                            break

                if not product_id and item.get("id"):
                    product_id = str(item.get("id"))

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
            except Exception:
                continue

    except Exception as e:
        print(f"[Products] Products API hatası: {str(e)}")
        return {}

    return products


@router.get("/")
async def get_all_products(
    limit: Optional[int] = None,
    sort_by: str = "revenue",
    store: Store = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    """
    Tüm ürünleri listeler ve performans bilgilerini döner (Wave3: per-store).

    Args:
        limit: Maksimum ürün sayısı (None = tümü)
        sort_by: Sıralama kriteri ("revenue", "sales", "recent")
    """
    creds = resolve_trendyol_creds(db, store)
    orders = get_trendyol_orders_data(creds)
    
    if not orders:
        return {
            "products": [],
            "total_products": 0,
            "message": "Sipariş verisi bulunamadı"
        }
    
    # Ürün performans verilerini topla
    product_data = defaultdict(lambda: {
        "product_name": "",
        "total_sales": 0,
        "total_revenue": 0.0,
        "orders": [],
        "first_sale_date": None,
        "last_sale_date": None,
        "category": "",
        "barcode": ""
    })
    
    today = datetime.now()
    
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
                    if isinstance(order_date_str, str):
                        if 'T' in order_date_str:
                            date_str_clean = order_date_str.replace('Z', '+00:00')
                            order_date = datetime.fromisoformat(date_str_clean)
                            if order_date.tzinfo:
                                order_date = order_date.replace(tzinfo=None)
                        else:
                            try:
                                order_date = datetime.strptime(order_date_str, "%Y-%m-%d %H:%M:%S")
                            except:
                                order_date = datetime.strptime(order_date_str.split('T')[0], "%Y-%m-%d")
                    elif isinstance(order_date_str, (int, float)):
                        _ts = float(order_date_str)
                        if _ts > 1e12:
                            _ts = _ts / 1000
                        order_date = datetime.fromtimestamp(_ts)
                        if order_date.tzinfo:
                            order_date = order_date.replace(tzinfo=None)
                except:
                    pass
            
            # Tarih parse edilemezse, bugün olarak kabul et
            if not order_date:
                order_date = today
        except:
            order_date = today
        
        # Ürün satırlarını al
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
                product_name = (
                    line.get("productName") or 
                    line.get("product_name") or 
                    line.get("name") or 
                    line.get("productTitle") or
                    "Bilinmeyen Ürün"
                )
                
                quantity = line.get("quantity", 1) or line.get("qty", 1) or 1
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
                revenue = price * quantity
                
                # Ürün bilgilerini güncelle
                if not product_data[product_id_str]["product_name"]:
                    product_data[product_id_str]["product_name"] = product_name
                    product_data[product_id_str]["category"] = line.get("categoryName") or line.get("category_name") or ""
                    product_data[product_id_str]["barcode"] = line.get("barcode") or line.get("sku") or ""
                
                product_data[product_id_str]["total_sales"] += quantity
                product_data[product_id_str]["total_revenue"] += revenue
                product_data[product_id_str]["orders"].append({
                    "order_date": order_date,
                    "quantity": quantity,
                    "price": price,
                    "revenue": revenue
                })
                
                # İlk ve son satış tarihlerini güncelle
                if not product_data[product_id_str]["first_sale_date"] or order_date < product_data[product_id_str]["first_sale_date"]:
                    product_data[product_id_str]["first_sale_date"] = order_date
                
                if not product_data[product_id_str]["last_sale_date"] or order_date > product_data[product_id_str]["last_sale_date"]:
                    product_data[product_id_str]["last_sale_date"] = order_date
            except:
                continue
    
    # Ürün performans verilerini formatla
    products = []
    for product_id, data in product_data.items():
        orders_list = data["orders"]
        orders_count = len(orders_list)
        average_price = data["total_revenue"] / data["total_sales"] if data["total_sales"] > 0 else 0.0
        
        # Trend analizi (son 30 gün vs önceki 30 gün)
        sales_trend = "stable"
        if len(orders_list) >= 2:
            recent_30_days = [o for o in orders_list if (today - o["order_date"]).days <= 30]
            previous_30_days = [o for o in orders_list if 30 < (today - o["order_date"]).days <= 60]
            
            recent_sales = sum(o["quantity"] for o in recent_30_days)
            previous_sales = sum(o["quantity"] for o in previous_30_days)
            
            if previous_sales > 0:
                change_percent = ((recent_sales - previous_sales) / previous_sales) * 100
                if change_percent > 10:
                    sales_trend = "increasing"
                elif change_percent < -10:
                    sales_trend = "decreasing"
        
        products.append({
            "product_id": product_id,
            "product_name": data["product_name"],
            "total_sales": data["total_sales"],
            "total_revenue": round(data["total_revenue"], 2),
            "average_price": round(average_price, 2),
            "orders_count": orders_count,
            "first_sale_date": data["first_sale_date"].strftime("%Y-%m-%d") if data["first_sale_date"] else None,
            "last_sale_date": data["last_sale_date"].strftime("%Y-%m-%d") if data["last_sale_date"] else None,
            "sales_trend": sales_trend,
            "category": data["category"],
            "barcode": data["barcode"]
        })
    
    # Sıralama
    if sort_by == "revenue":
        products.sort(key=lambda x: x["total_revenue"], reverse=True)
    elif sort_by == "sales":
        products.sort(key=lambda x: x["total_sales"], reverse=True)
    elif sort_by == "recent":
        products.sort(key=lambda x: x["last_sale_date"] or "", reverse=True)
    
    # Limit uygula
    if limit:
        products = products[:limit]
    
    # Debug bilgisi
    print(f"[Products] Toplam sipariş: {len(orders)}, Bulunan ürün: {len(products)}")
    if len(products) == 0 and len(orders) > 0:
        print(f"[Products] UYARI: {len(orders)} sipariş var ama hiç ürün bulunamadı.")
        if orders:
            first_order = orders[0]
            print(f"[Products] İlk sipariş keys: {list(first_order.keys())[:20]}")
    
    return {
        "products": products,
        "total_products": len(products),
        "total_revenue": round(sum(p["total_revenue"] for p in products), 2),
        "total_sales": sum(p["total_sales"] for p in products)
    }


@router.get("/{product_id}")
async def get_product_detail(
    product_id: str,
    store: Store = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    """
    Belirli bir ürünün detaylı bilgilerini döner (Wave3: per-store).
    """
    creds = resolve_trendyol_creds(db, store)
    orders = get_trendyol_orders_data(creds)
    trendyol_products = get_trendyol_products_data(creds)
    
    # Ürün bilgilerini topla
    product_info = None
    order_history = []
    daily_sales = defaultdict(int)
    monthly_sales = defaultdict(int)
    
    today = datetime.now()
    
    # Önce Trendyol Products API'den ürün bilgisini kontrol et
    product_id_str = str(product_id)
    if product_id_str in trendyol_products:
        api_product = trendyol_products[product_id_str]
        product_info = {
            "product_id": product_id_str,
            "product_name": api_product.get("product_name", "Bilinmeyen Ürün"),
            "category": api_product.get("category", ""),
            "barcode": api_product.get("barcode", "")
        }
    
    # Sipariş verilerinde ürünü ara
    if orders:
        for order in orders:
            try:
                order_date_str = order.get("orderDate") or order.get("order_date")
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
            except:
                continue
            
            # Ürün satırlarını al (inventory ile aynı mantık)
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
                        "barcode": order.get("barcode") or order.get("sku") or "",
                        "price": order.get("price", 0) or order.get("salePrice", 0) or order.get("unitPrice", 0)
                    }]
            
            for line in lines:
                try:
                    # Ürün ID'sini çıkar (get_all_products ile aynı mantık)
                    line_product_id = None
                    
                    # Önce en yaygın alan adlarını dene (productCode öncelikli)
                    for key in ["productCode", "product_code", "productId", "product_id", "sku", "barcode", 
                               "stockCode", "sellerSku", "productSku", "itemId", "item_id"]:
                        value = line.get(key)
                        if value:
                            val_str = str(value).strip()
                            # merchantSku veya stockCode'nun değeri "merchantSku" string'i ise atla
                            if val_str and val_str.lower() not in ["merchantsku", "stockcode"]:
                                line_product_id = val_str
                                break
                    
                    # merchantSku'yu sadece gerçek bir değer varsa kullan
                    if not line_product_id:
                        merchant_sku = line.get("merchantSku")
                        if merchant_sku:
                            val_str = str(merchant_sku).strip()
                            if val_str and val_str.lower() != "merchantsku":
                                line_product_id = val_str
                    
                    # Hala bulunamadıysa, id alanlarını dene
                    if not line_product_id:
                        if line.get("id"):
                            line_product_id = str(line.get("id"))
                        elif line.get("lineItemId"):
                            line_product_id = str(line.get("lineItemId"))
                        elif line.get("contentId"):
                            line_product_id = str(line.get("contentId"))
                    
                    # Hala yoksa, tüm değerleri kontrol et
                    if not line_product_id and isinstance(line, dict):
                        for key, value in line.items():
                            if key.lower() in ["productcode", "productid", "barcode", "sku", "stockcode"] and value:
                                val_str = str(value).strip()
                                if val_str and val_str.lower() not in ["merchantsku", "stockcode"]:
                                    line_product_id = val_str
                                    break
                    
                    if not line_product_id or line_product_id == "None" or line_product_id == "":
                        continue
                    
                    if str(line_product_id) != str(product_id):
                        continue
                    
                    # Ürün bilgilerini kaydet
                    if not product_info:
                        product_info = {
                            "product_id": product_id,
                            "product_name": (
                                line.get("productName") or 
                                line.get("product_name") or 
                                line.get("name") or 
                                "Bilinmeyen Ürün"
                            ),
                            "category": line.get("categoryName") or line.get("category_name") or "",
                            "barcode": line.get("barcode") or line.get("sku") or ""
                        }
                    
                    quantity = line.get("quantity", 1) or line.get("qty", 1) or 1
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
                    revenue = price * quantity
                    
                    # Sipariş geçmişine ekle
                    order_history.append({
                        "order_id": order.get("orderNumber") or order.get("id", ""),
                        "order_date": order_date.strftime("%Y-%m-%d %H:%M:%S"),
                        "quantity": quantity,
                        "price": round(price, 2),
                        "revenue": round(revenue, 2)
                    })
                    
                    # Günlük ve aylık satışları topla
                    day_key = order_date.strftime("%Y-%m-%d")
                    month_key = order_date.strftime("%Y-%m")
                    daily_sales[day_key] += quantity
                    monthly_sales[month_key] += quantity
                except:
                    continue
    
    # Eğer ürün bulunamadıysa, Trendyol Products API'den tekrar kontrol et
    if not product_info:
        # Tüm olası ID formatlarını dene
        for key in trendyol_products.keys():
            if str(key) == product_id_str or key == product_id_str:
                api_product = trendyol_products[key]
                product_info = {
                    "product_id": product_id_str,
                    "product_name": api_product.get("product_name", "Bilinmeyen Ürün"),
                    "category": api_product.get("category", ""),
                    "barcode": api_product.get("barcode", "")
                }
                break
    
    if not product_info:
        raise HTTPException(status_code=404, detail="Ürün bulunamadı")
    
    # İstatistikleri hesapla
    total_sales = sum(o["quantity"] for o in order_history)
    total_revenue = sum(o["revenue"] for o in order_history)
    average_price = total_revenue / total_sales if total_sales > 0 else 0.0
    
    # Son 30 günlük satış trendi
    recent_30_days = [o for o in order_history if (today - datetime.strptime(o["order_date"].split()[0], "%Y-%m-%d")).days <= 30]
    previous_30_days = [o for o in order_history if 30 < (today - datetime.strptime(o["order_date"].split()[0], "%Y-%m-%d")).days <= 60]
    
    recent_sales = sum(o["quantity"] for o in recent_30_days)
    previous_sales = sum(o["quantity"] for o in previous_30_days)
    
    sales_trend = "stable"
    trend_percent = 0.0
    if previous_sales > 0:
        trend_percent = ((recent_sales - previous_sales) / previous_sales) * 100
        if trend_percent > 10:
            sales_trend = "increasing"
        elif trend_percent < -10:
            sales_trend = "decreasing"
    
    # Günlük satış verilerini formatla (son 30 gün)
    daily_sales_list = []
    for i in range(29, -1, -1):
        day_date = today - timedelta(days=i)
        day_key = day_date.strftime("%Y-%m-%d")
        daily_sales_list.append({
            "date": day_key,
            "sales": daily_sales.get(day_key, 0)
        })
    
    return {
        "product": product_info,
        "statistics": {
            "total_sales": total_sales,
            "total_revenue": round(total_revenue, 2),
            "average_price": round(average_price, 2),
            "orders_count": len(order_history),
            "first_sale_date": order_history[-1]["order_date"] if order_history else None,
            "last_sale_date": order_history[0]["order_date"] if order_history else None,
            "sales_trend": sales_trend,
            "trend_percent": round(trend_percent, 1)
        },
        "order_history": order_history[:50],  # Son 50 sipariş
        "daily_sales": daily_sales_list,
        "monthly_sales": [
            {"month": month, "sales": sales} 
            for month, sales in sorted(monthly_sales.items(), reverse=True)[:12]
        ]
    }

