"""
Wave 3 — Per-store Trendyol istemci fabrikası + kimlik çözümleyici.

AMAÇ: Bugüne kadar ~20 router `get_trendyol_orders_data()`'ın kopyalanmış bir
sürümünü içeriyordu; hepsi TEK sabit env anahtarını (TRENDYOL_API_KEY/SECRET/
SUPPLIER_ID) okuyordu → çok-kiracılıkla uyumsuz. Bu modül merkezî çözümleyicidir:
`get_current_store`'dan gelen mağazanın `store_credentials` kaydındaki Fernet-şifreli
Trendyol anahtarını çözer ve o mağaza adına Trendyol API'yi çağırır.

Kullanım (router'da):
    from utils.store_trendyol import resolve_trendyol_creds, fetch_orders
    creds = resolve_trendyol_creds(db, store)          # kimlik yoksa 409 fırlatır
    orders = fetch_orders(creds)

DEV NOTU: gerçek Trendyol çağrısı GERÇEK mağaza anahtarı ister; dev'de demo store'un
anahtarı yok. Çözümleme/izolasyon mantığı enjekte kimlikle test edilebilir; uçtan uca
canlı veri kullanıcının Ayarlar'dan gerçek anahtar girmesini gerektirir.
"""
import base64
import os
from typing import Dict, List, Optional

import requests
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from database.models import Store, StoreCredential
from security import decrypt_secret


# ---------------------------------------------------------------------------
# Kimlik çözümleyici
# ---------------------------------------------------------------------------
class TrendyolCreds:
    """Bir mağazanın çözülmüş Trendyol kimlik bilgileri (düz metin — sadece bellek içi)."""
    __slots__ = ("api_key", "api_secret", "supplier_id", "store_id")

    def __init__(self, api_key: str, api_secret: str, supplier_id: str, store_id: int):
        self.api_key = api_key
        self.api_secret = api_secret
        self.supplier_id = supplier_id
        self.store_id = store_id


def resolve_trendyol_creds(db: Session, store: Store) -> TrendyolCreds:
    """store_credentials'tan bu mağazanın Trendyol kimliğini çözer. Bağlı değilse 409."""
    cred = (
        db.query(StoreCredential)
        .filter(
            StoreCredential.store_id == store.id,
            StoreCredential.platform == "trendyol",
        )
        .first()
    )
    if not cred or not cred.is_connected:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Mağaza Trendyol'a bağlı değil — Ayarlar → Trendyol API bilgilerini girin",
        )
    if not cred.supplier_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Trendyol satıcı (supplier) ID eksik — Ayarlar'dan tamamlayın",
        )
    try:
        api_key = decrypt_secret(cred.api_key_encrypted)
        api_secret = decrypt_secret(cred.api_secret_encrypted)
    except Exception:
        # Şifre çözme başarısız (anahtar rotasyonu / bozuk kayıt) — net hata
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Trendyol kimlik bilgileri çözülemedi — Ayarlar'dan yeniden girin",
        )
    return TrendyolCreds(api_key, api_secret, cred.supplier_id, store.id)


def try_resolve_trendyol_creds(db: Session, store: Store) -> Optional[TrendyolCreds]:
    """resolve_trendyol_creds gibi ama kimlik yoksa 409 yerine None döner
    (canlı-API opsiyonel olan, lokal-DB'ye düşebilen endpoint'ler için)."""
    try:
        return resolve_trendyol_creds(db, store)
    except HTTPException:
        return None


# ---------------------------------------------------------------------------
# Trendyol API çağrıları (per-store — creds parametreli, env DEĞİL)
# ---------------------------------------------------------------------------
def _sapigw_base() -> str:
    return os.getenv("TRENDYOL_SAPIGW_BASE", "https://api.trendyol.com/sapigw").rstrip("/")


def _auth_headers(creds: TrendyolCreds) -> Dict[str, str]:
    auth_b64 = base64.b64encode(f"{creds.api_key}:{creds.api_secret}".encode("ascii")).decode("ascii")
    return {
        "Authorization": f"Basic {auth_b64}",
        "Content-Type": "application/json",
        # Trendyol User-Agent zorunlu (sellerId - app) — Jim capability-map
        "User-Agent": f"{creds.supplier_id} - SelfIntegration",
    }


def fetch_orders(creds: TrendyolCreds, max_pages: int = 100, size: int = 200) -> List[Dict]:
    """Bu mağazanın Trendyol siparişlerini çeker (sayfalı). Eski kopyalanmış
    get_trendyol_orders_data()'ın per-store karşılığı — env yerine creds kullanır.
    w3-hardening: eski api.trendyol.com/sapigw yerine resmi Order Integration V2
    ucu (developers.trendyol.com/v3.0/docs/2-get-shipment-packages, 2026-09-26'da
    gerçek çağrıyla doğrulandı) — v1 15 Ekim 2026'da kaldırılıyor, eski sapigw'in
    zaten bilinmeyen bir kaldırılma tarihi var."""
    url = f"{_integration_base()}/order/sellers/{creds.supplier_id}/v2/orders"
    headers = _auth_headers(creds)
    all_orders: List[Dict] = []
    page = 0
    try:
        while True:
            resp = requests.get(url, headers=headers, params={"page": page, "size": size}, timeout=30)
            if resp.status_code != 200:
                break
            try:
                data = resp.json()
            except Exception:
                break
            orders = data.get("content", [])
            if not orders:
                break
            all_orders.extend(orders)
            if len(orders) < size:
                break
            page += 1
            if page > max_pages:
                break
    except Exception:
        return all_orders
    return all_orders


def fetch_common_label(creds: TrendyolCreds, cargo_tracking_number: str) -> "tuple[Optional[str], Optional[str]]":
    """Bu mağazanın kargo etiketini Trendyol'un resmi 'Ortak Etiket' (Common Label)
    servisinden çeker — developers.trendyol.com/reference/getcommonlabel /
    createcommonlabel (2026-09-23'te doğrulandı; eski `/suppliers/{id}/shipment-packages/
    {id}/label` ucu artık Cloudflare bot-korumasıyla 403 veriyor, bu servis onun yerini alır).

    ÖNEMLİ: paket id DEĞİL, siparişin `cargoTrackingNumber` alanı kullanılır (path parametresi).
    Akış: önce GET dene (etiket zaten oluşturulmuş olabilir); 400/404 ise POST ile talep et
    (yalnızca ZPL formatı destekleniyor), sonra tekrar GET dene.

    Returns:
        (zpl_text, None) — başarılı, zpl_text ham ZPL komut string'i (örn. "^XA...^XZ")
        (None, error_message) — başarısız; error_message Trendyol'un döndürdüğü GERÇEK sebep
        (örn. "Bu servisi kullanmak için yetkiniz bulunmamaktadır..." — COMMON_LABEL_NOT_ALLOWED
        gibi hesap-izni sorunları dahil), ya da erişilemedi/bilinmeyen hata için genel bir mesaj.
    """
    base = _integration_base()
    url = f"{base}/sellers/{creds.supplier_id}/common-label/{cargo_tracking_number}"
    headers = _auth_headers(creds)

    def _parse_label(resp) -> Optional[str]:
        try:
            data = resp.json()
        except Exception:
            return None
        items = data.get("data") if isinstance(data, dict) else None
        if isinstance(items, list) and items:
            return items[0].get("label")
        return None

    def _parse_error(resp) -> Optional[str]:
        try:
            data = resp.json()
        except Exception:
            return None
        errs = (data or {}).get("error", {}).get("errors") if isinstance(data, dict) else None
        if isinstance(errs, list) and errs:
            return errs[0].get("title") or errs[0].get("type")
        return None

    try:
        resp = requests.get(url, headers=headers, timeout=30)
        if resp.status_code == 200:
            label = _parse_label(resp)
            if label:
                return label, None

        # Henüz oluşturulmamış olabilir — oluşturmayı dene (sadece ZPL destekleniyor).
        if resp.status_code in (400, 404):
            create_resp = requests.post(url, headers=headers, json={"format": "ZPL"}, timeout=30)
            if create_resp.status_code == 400:
                # Hesap-izni gibi kalıcı bir red — tekrar GET denemenin anlamı yok, gerçek sebebi döndür.
                err = _parse_error(create_resp)
                if err:
                    return None, err
            get_resp = requests.get(url, headers=headers, timeout=30)
            if get_resp.status_code == 200:
                label = _parse_label(get_resp)
                if label:
                    return label, None
            err = _parse_error(get_resp)
            return None, err or f"Trendyol API {get_resp.status_code} döndü"

        err = _parse_error(resp)
        return None, err or f"Trendyol API {resp.status_code} döndü"
    except Exception as e:
        return None, f"Trendyol API'ye erişilemedi: {e}"


def fetch_products(creds: TrendyolCreds, max_pages: int = 100, size: int = 200) -> List[Dict]:
    """Bu mağazanın Trendyol ürünlerini çeker (sayfalı).
    w3-hardening (2026-09-26): eski api.trendyol.com/sapigw/suppliers/{id}/products
    ucu V1'di ve 10 Ağustos 2026'da GEÇERSİZ olmuş — bu yüzden bu hesap için HER ZAMAN
    boş dönüyordu (önceki turlarda 'Trendyol Products API bu hesap için boş dönüyor,
    harici gerçek' diye yanlış teşhis edildi — aslında endpoint ölüydü, hesapta 53
    gerçek ürün var). Gerçek V2 ucuna taşındı: developers.trendyol.com/v2.0/docs/
    product-v2-api-endpoint, GET .../product/sellers/{id}/products/approved
    (2026-09-26'da gerçek çağrıyla doğrulandı, totalElements=53).

    V2 şeması V1'den FARKLI: ürün başına `variants` listesi var, her variant kendi
    barcode/stock/price'ına sahip (bir üründe birden fazla beden/renk olabilir).
    Mevcut tüketiciler (örn. inventory.py) V1'in DÜZ şemasını (barcode/stockQuantity/
    salePrice doğrudan item üzerinde) bekliyor — geriye dönük uyumluluk için burada
    her variant'ı ayrı bir düz "ürün" satırına çeviriyoruz, tüketici kodu DEĞİŞMEDİ."""
    url = f"{_integration_base()}/product/sellers/{creds.supplier_id}/products/approved"
    headers = _auth_headers(creds)
    # Bu ucun kendi boyut sınırı VAR (100), orders'ınkinden (200) farklı — gerçek çağrıyla
    # doğrulandı (INVALID_SIZE hatası, "Boyut 100 değerini aşamaz").
    page_size = min(size, 100)
    flat_items: List[Dict] = []
    page = 0
    try:
        while True:
            resp = requests.get(url, headers=headers, params={"page": page, "size": page_size}, timeout=30)
            if resp.status_code != 200:
                break
            try:
                data = resp.json()
            except Exception:
                break
            products = data.get("content", [])
            if not products:
                break
            for p in products:
                title = p.get("title")
                category_name = (p.get("category") or {}).get("name")
                for v in (p.get("variants") or []):
                    stock = v.get("stock") or {}
                    price = v.get("price") or {}
                    flat_items.append({
                        "barcode": v.get("barcode"),
                        "merchantSku": v.get("stockCode") or v.get("barcode"),
                        "productId": p.get("contentId"),
                        "productName": title,
                        "categoryName": category_name,
                        "stockQuantity": stock.get("quantity", 0),
                        "salePrice": price.get("salePrice"),
                        "listPrice": price.get("listPrice"),
                    })
            if len(products) < page_size:
                break
            page += 1
            if page > max_pages:
                break
    except Exception:
        return flat_items
    return flat_items


# ---------------------------------------------------------------------------
# Wave 3 FAZ 3 — Settlements (Hakediş) — gerçek komisyon/kesinti tutarları
# Jim capability-map: GET /integration/finance/che/sellers/{sellerId}/settlements
# Zorunlu: transactionType, startDate, endDate (ms epoch, aralık MAKS 15 gün).
# ---------------------------------------------------------------------------
import time as _time
from datetime import datetime as _dt, timedelta as _td


def _integration_base() -> str:
    return os.getenv("TRENDYOL_INTEGRATION_BASE", "https://apigw.trendyol.com/integration").rstrip("/")


def fetch_settlements(creds: TrendyolCreds, start: _dt, end: _dt,
                      transaction_type: str = "Commission", max_windows: int = 12) -> List[Dict]:
    """Bu mağazanın settlement hareketlerini çeker. Trendyol 15-günlük pencere zorunlu
    kıldığı için [start, end] aralığını ≤14 günlük dilimlere böler, her dilimi sayfalar.
    transaction_type: 'Commission' → CommissionNegative+CommissionPositive taranır.
    Gerçek anahtar yoksa/erişilemezse boş liste döner (hata fırlatmaz)."""
    base = _integration_base()
    url = f"{base}/finance/che/sellers/{creds.supplier_id}/settlements"
    headers = _auth_headers(creds)

    # 'Commission' kısayolu → iki gerçek enum
    if transaction_type == "Commission":
        types = ["CommissionNegative", "CommissionPositive"]
    else:
        types = [transaction_type]

    all_txns: List[Dict] = []
    window_start = start
    windows = 0
    try:
        while window_start < end and windows < max_windows:
            window_end = min(window_start + _td(days=14), end)
            start_ms = int(window_start.timestamp() * 1000)
            end_ms = int(window_end.timestamp() * 1000)
            for ttype in types:
                page = 0
                while True:
                    params = {
                        "transactionType": ttype,
                        "startDate": start_ms,
                        "endDate": end_ms,
                        "page": page,
                        "size": 500,
                    }
                    resp = requests.get(url, headers=headers, params=params, timeout=30)
                    if resp.status_code != 200:
                        break
                    try:
                        data = resp.json()
                    except Exception:
                        break
                    content = data.get("content", []) or []
                    if not content:
                        break
                    all_txns.extend(content)
                    total_pages = data.get("totalPages")
                    if total_pages is not None:
                        if page >= total_pages - 1:
                            break
                    elif len(content) < 500:
                        break
                    page += 1
                    if page > 50:
                        break
            window_start = window_end + _td(seconds=1)
            windows += 1
    except Exception:
        return all_txns
    return all_txns


# ---------------------------------------------------------------------------
# Wave 3 (actual_cargo) — OtherFinancials — gerçek kargo/kesinti kalemleri
# Jim capability-map: GET /integration/finance/che/sellers/{sellerId}/otherfinancials
# Aynı FinancialTransaction şeması + 15-gün pencere. Kargo faturası kalemleri
# burada 'kesinti faturaları' (DeductionInvoices vb.) altında gelir.
# DÜŞÜK GÜVEN: kargo kalem transactionType enum'u dokümanda net değil; bu yüzden
# aday tip listesi env ile override edilebilir (TRENDYOL_CARGO_TXN_TYPES). Yanlış
# tip → sadece boş sonuç (non-200/boş graceful), crash yok.
# ---------------------------------------------------------------------------
def cargo_transaction_types() -> List[str]:
    """Kargo kesintisi olarak taranacak OtherFinancials transactionType adayları.
    Env `TRENDYOL_CARGO_TXN_TYPES` (virgülle) ile override edilebilir. Varsayılan
    muhafazakâr: DeductionInvoices (kargo faturası kesintisi burada gelir — Jim, düşük güven)."""
    raw = os.getenv("TRENDYOL_CARGO_TXN_TYPES", "DeductionInvoices")
    return [t.strip() for t in raw.split(",") if t.strip()]


def fetch_otherfinancials(creds: TrendyolCreds, start: _dt, end: _dt,
                          transaction_types: Optional[List[str]] = None,
                          max_windows: int = 12) -> List[Dict]:
    """Bu mağazanın OtherFinancials hareketlerini çeker (settlements ile aynı
    pencereleme/sayfalama). transaction_types verilmezse cargo_transaction_types()
    kullanılır. Erişilemezse boş liste döner (hata fırlatmaz)."""
    base = _integration_base()
    url = f"{base}/finance/che/sellers/{creds.supplier_id}/otherfinancials"
    headers = _auth_headers(creds)
    types = transaction_types if transaction_types is not None else cargo_transaction_types()

    all_txns: List[Dict] = []
    window_start = start
    windows = 0
    try:
        while window_start < end and windows < max_windows:
            window_end = min(window_start + _td(days=14), end)
            start_ms = int(window_start.timestamp() * 1000)
            end_ms = int(window_end.timestamp() * 1000)
            for ttype in types:
                page = 0
                while True:
                    params = {
                        "transactionType": ttype,
                        "startDate": start_ms,
                        "endDate": end_ms,
                        "page": page,
                        "size": 500,
                    }
                    resp = requests.get(url, headers=headers, params=params, timeout=30)
                    if resp.status_code != 200:
                        break
                    try:
                        data = resp.json()
                    except Exception:
                        break
                    content = data.get("content", []) or []
                    if not content:
                        break
                    all_txns.extend(content)
                    total_pages = data.get("totalPages")
                    if total_pages is not None:
                        if page >= total_pages - 1:
                            break
                    elif len(content) < 500:
                        break
                    page += 1
                    if page > 50:
                        break
            window_start = window_end + _td(seconds=1)
            windows += 1
    except Exception:
        return all_txns
    return all_txns
