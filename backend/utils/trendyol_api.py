"""
Trendyol API Helper
Trendyol Supplier API entegrasyonu için yardımcı fonksiyonlar.

Resmi dokümantasyon: https://developers.trendyol.com/

Sipariş paketleri — iki yüzey:
- **Klasik (sayfa)**: Bu repoda çoğu yerde `TRENDYOL_SAPIGW_BASE` + `/suppliers/{id}/orders?page=&size=`
  kullanılır. Trendyol duyurusu: **15 Mayıs 2026** itibarıyla getShipmentPackages tarafında
  toplam **en fazla 10.000 kayıt** ve sıkı rate limit; aşımda **429**. Ayrıntılar:
  https://developers.trendyol.com/v3.0/docs/6-service-limitations (International)
  https://developers.trendyol.com/v2.0/docs/1-service-limitations (TR EN)

- **Stream (cursor)**: `getShipmentPackagesStream` — tam tarama, periyodik senkron, export için.
  Host: `GET {TRENDYOL_INTEGRATION_ORDER_BASE}/sellers/{sellerId}/orders/stream`
  Zorunlu header: **storeFrontCode** (`TRENDYOL_STOREFRONT_CODE`, varsayılan TR).
  Yanıtta `hasMore`, `nextCursor`, `size`, `content`; `totalElements` / `totalPages` / `page` yok.
  Son **3 ay** veri; tarih filtresi kullanılmazsa aralık otomatik **son 2 hafta**.
  Tarih filtresi kullanılırsa pencere en fazla **14 gün**. İstekler arası öneri: **≥ 5 sn**.
  Dokümantasyon: https://developers.trendyol.com/v3.0/docs/get-shipment-packages-stream

Stream istemcisi: `fetch_shipment_packages_stream_once`, `iter_shipment_packages_stream`.
"""
import os
import time
import requests
import hmac
import hashlib
import base64
from typing import Optional, Dict, Any, List, Iterator


def _sapigw_base() -> str:
    return os.getenv("TRENDYOL_SAPIGW_BASE", "https://api.trendyol.com/sapigw").rstrip("/")


def _integration_order_base() -> str:
    """Integration Order API tabanı (stream ve resmi paket uçları için)."""
    return os.getenv(
        "TRENDYOL_INTEGRATION_ORDER_BASE",
        "https://apigw.trendyol.com/integration/order",
    ).rstrip("/")


def _storefront_code() -> str:
    """getShipmentPackagesStream için zorunlu header; TR pazarı için genelde TR."""
    return (os.getenv("TRENDYOL_STOREFRONT_CODE") or "TR").strip()


def get_trendyol_credentials() -> Optional[Dict[str, str]]:
    """Trendyol API bilgilerini environment'tan alır"""
    api_key = os.getenv("TRENDYOL_API_KEY")
    api_secret = os.getenv("TRENDYOL_API_SECRET")
    supplier_id = os.getenv("TRENDYOL_SUPPLIER_ID")
    
    if not all([api_key, api_secret, supplier_id]):
        return None
    
    return {
        "api_key": api_key,
        "api_secret": api_secret,
        "supplier_id": supplier_id
    }


def generate_trendyol_signature(api_secret: str, method: str, path: str, body: str = "") -> str:
    """
    Trendyol API için signature oluşturur
    """
    message = f"{method}{path}{body}"
    signature = hmac.new(
        api_secret.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).digest()
    return base64.b64encode(signature).decode('utf-8')


def make_trendyol_request(
    method: str,
    endpoint: str,
    params: Optional[Dict] = None,
    data: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Trendyol API'ye istek yapar
    
    Args:
        method: HTTP method (GET, POST, PUT, DELETE)
        endpoint: Supplier'a göre yol eki (örn: /orders, /orders/{orderNumber})
        params: Query parametreleri
        data: Request body (POST/PUT için)
    
    Returns:
        API yanıtı
    """
    credentials = get_trendyol_credentials()
    
    if not credentials:
        return {
            "error": "Trendyol API bilgileri bulunamadı. .env dosyasını kontrol edin.",
            "success": False
        }
    
    # Tek bir /suppliers segmenti: base .../sapigw + /suppliers/{supplierId}/...
    path = f"/suppliers/{credentials['supplier_id']}{endpoint}"
    url = f"{_sapigw_base()}{path}"
    
    # Body'yi string'e çevir
    body_str = ""
    if data:
        import json
        body_str = json.dumps(data, separators=(',', ':'))
    
    # İmza üretilir (bazı uç noktalar için ileride header'a eklenebilir)
    _ = generate_trendyol_signature(
        credentials['api_secret'],
        method,
        path,
        body_str
    )

    # Headers
    auth_string = f"{credentials['api_key']}:{credentials['api_secret']}"
    auth_bytes = auth_string.encode('ascii')
    auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
    
    headers = {
        "Authorization": f"Basic {auth_b64}",
        "Content-Type": "application/json",
        "User-Agent": "Trendyol-AI-Assistant/1.0"
    }
    
    try:
        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            params=params,
            json=data if data else None,
            timeout=30
        )
        
        return {
            "success": response.status_code < 400,
            "status_code": response.status_code,
            "data": response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text,
            "headers": dict(response.headers)
        }
    
    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Trendyol API'ye bağlanılamadı"
        }


def test_trendyol_connection() -> Dict[str, Any]:
    """
    Trendyol API bağlantısını test eder
    """
    # Basit bir test endpoint'i - siparişleri listele
    result = make_trendyol_request(
        method="GET",
        endpoint="/orders",
        params={"page": 0, "size": 1}  # Sadece 1 sipariş çek, test için
    )
    
    return result


def get_trendyol_orders(page: int = 0, size: int = 50) -> Dict[str, Any]:
    """
    Trendyol'dan siparişleri çeker
    """
    return make_trendyol_request(
        method="GET",
        endpoint="/orders",
        params={"page": page, "size": size}
    )


def _trendyol_basic_headers(credentials: Dict[str, str]) -> Dict[str, str]:
    auth_string = f"{credentials['api_key']}:{credentials['api_secret']}"
    auth_b64 = base64.b64encode(auth_string.encode("ascii")).decode("ascii")
    return {
        "Authorization": f"Basic {auth_b64}",
        "Content-Type": "application/json",
        "User-Agent": "Trendyol-AI-Assistant/1.0",
    }


def get_trendyol_shipment_label(package_id: str) -> Optional[bytes]:
    """
    Trendyol'dan kargo etiketini (shipping label) çeker.

    Dokümantasyondaki paket kimliği: shipmentPackageId (sipariş paketi id).
    Önce shipment-packages/{packageId}/label uç noktası denenir; gerekirse
    orders/{orderNumber} ile çözümleme için make_trendyol_request kullanılır.

    Args:
        package_id: shipmentPackageId veya (yalnızca fallback) orderNumber

    Returns:
        Kargo etiketi (bytes) veya None
    """
    credentials = get_trendyol_credentials()

    if not credentials:
        return None

    supplier_id = credentials["supplier_id"]
    base = _sapigw_base()
    headers = _trendyol_basic_headers(credentials)

    try:
        label_url = f"{base}/suppliers/{supplier_id}/shipment-packages/{package_id}/label"
        response = requests.get(label_url, headers=headers, timeout=30)
        if response.status_code == 200 and response.content:
            return response.content

        # Bazı hesaplarda sipariş numarası ile detay üzerinden paket id'si gerekir
        order_response = make_trendyol_request(
            method="GET",
            endpoint=f"/orders/{package_id}",
        )
        if order_response.get("success"):
            data = order_response.get("data")
            pkg_id = None
            if isinstance(data, dict):
                pkg_id = data.get("shipmentPackageId") or data.get("id")
            if pkg_id and str(pkg_id) != str(package_id):
                retry_url = f"{base}/suppliers/{supplier_id}/shipment-packages/{pkg_id}/label"
                retry = requests.get(retry_url, headers=headers, timeout=30)
                if retry.status_code == 200 and retry.content:
                    return retry.content

        alt_url = f"{base}/suppliers/{supplier_id}/orders/{package_id}/shipment-label"
        alt = requests.get(alt_url, headers=headers, timeout=30)
        if alt.status_code == 200 and alt.content:
            return alt.content

        return None

    except Exception as e:
        print(f"Kargo etiketi çekme hatası: {str(e)}")
        return None


def fetch_shipment_packages_stream_once(
    *,
    cursor: Optional[str] = None,
    size: int = 50,
    last_modified_start_ms: Optional[int] = None,
    last_modified_end_ms: Optional[int] = None,
    timeout: int = 90,
) -> Dict[str, Any]:
    """
    Tek bir getShipmentPackagesStream isteği (cursor sayfası).

    cursor: Önceki yanıttaki nextCursor; ilk istekte None.
    Tarihler: Epoch milisaniye (Trendyol örnekleriyle uyumlu); API farklı format isterse env ile uyarlanır.
    """
    credentials = get_trendyol_credentials()
    if not credentials:
        return {
            "success": False,
            "error": "Trendyol API bilgileri bulunamadı",
            "status_code": None,
            "data": None,
        }

    seller_id = credentials["supplier_id"]
    url = f"{_integration_order_base()}/sellers/{seller_id}/orders/stream"
    headers = _trendyol_basic_headers(credentials)
    headers["storeFrontCode"] = _storefront_code()

    params: Dict[str, Any] = {"size": max(1, min(size, 200))}
    if cursor:
        params["nextCursor"] = cursor
    if last_modified_start_ms is not None:
        params["lastModifiedStartDate"] = last_modified_start_ms
    if last_modified_end_ms is not None:
        params["lastModifiedEndDate"] = last_modified_end_ms

    try:
        response = requests.get(url, headers=headers, params=params, timeout=timeout)
        ct = response.headers.get("content-type", "")
        body: Any
        if "application/json" in ct:
            try:
                body = response.json()
            except Exception:
                body = response.text
        else:
            body = response.text

        return {
            "success": response.status_code == 200,
            "status_code": response.status_code,
            "data": body,
            "headers": dict(response.headers),
        }
    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "error": str(e),
            "status_code": None,
            "data": None,
        }


def iter_shipment_packages_stream(
    *,
    batch_size: int = 50,
    last_modified_start_ms: Optional[int] = None,
    last_modified_end_ms: Optional[int] = None,
    min_interval_seconds: float = 5.0,
    max_batches: Optional[int] = None,
    max_429_retries: int = 3,
) -> Iterator[List[Dict[str, Any]]]:
    """
    Cursor ile tüm paket sayfalarını sırayla üretir (content listeleri).

    Trendyol önerisi: istekler arasında en az ~5 saniye (rate limit / 429 riski).
    """
    cursor: Optional[str] = None
    batches = 0

    while True:
        if max_batches is not None and batches >= max_batches:
            break

        attempt = 0
        while True:
            result = fetch_shipment_packages_stream_once(
                cursor=cursor,
                size=batch_size,
                last_modified_start_ms=last_modified_start_ms,
                last_modified_end_ms=last_modified_end_ms,
            )
            status = result.get("status_code")
            if status == 429 and attempt < max_429_retries:
                attempt += 1
                hdrs = result.get("headers") or {}
                ra = hdrs.get("Retry-After") or hdrs.get("retry-after")
                try:
                    wait_s = min(120.0, float(ra))
                except (TypeError, ValueError):
                    wait_s = 60.0
                time.sleep(wait_s)
                continue
            break

        if not result.get("success"):
            break

        data = result.get("data")
        if not isinstance(data, dict):
            break

        content = data.get("content") or []
        if isinstance(content, list):
            yield content

        batches += 1

        if not data.get("hasMore"):
            break

        next_c = data.get("nextCursor")
        if not next_c or not isinstance(next_c, str):
            break

        cursor = next_c
        if min_interval_seconds > 0:
            time.sleep(min_interval_seconds)

