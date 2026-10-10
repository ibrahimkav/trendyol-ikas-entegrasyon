"""
Ayarlar: mağaza yönetimi + platform API kimlik bilgisi bağlama (store-connect).

Wave 1 kapsamı: sadece şekil-doğrulama + şifreli saklama. GERÇEK Trendyol/Hepsiburada
API doğrulaması (kimlik bilgilerinin gerçekten çalıştığını test etme) burada YAPILMAZ —
insan gerçek key'leri entegrasyon sırasında verdiğinde eklenecek (Wave 2+).
"""
import asyncio
import json
from datetime import datetime
from typing import Any, Dict, Optional

import requests
from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from database.db import get_db
from database.models import Product, Store, StoreCredential, StoreThreshold, User
from security import decrypt_secret, encrypt_secret, get_current_store, get_current_user, mask_secret
from utils.thresholds import (
    LOW_STOCK_FLOOR_MAX,
    LOW_STOCK_FLOOR_MIN,
    LOW_STOCK_SALES_RATIO_MAX,
    LOW_STOCK_SALES_RATIO_MIN,
    MARGIN_WARNING_THRESHOLD_MAX,
    MARGIN_WARNING_THRESHOLD_MIN,
    get_effective_thresholds,
)
from utils.store_settings import (
    FIELDS as STORE_SETTING_FIELDS,
    SettingsValidationError,
    get_effective_store_settings,
    update_store_settings,
)

router = APIRouter()

ALLOWED_PLATFORMS = {"trendyol", "hepsiburada"}


class CreateStoreBody(BaseModel):
    store_name: str

    @field_validator("store_name")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Mağaza adı boş olamaz")
        return v


class ConnectCredentialsBody(BaseModel):
    platform: str
    supplier_id: Optional[str] = None
    api_key: str
    api_secret: str

    @field_validator("platform")
    @classmethod
    def _valid_platform(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in ALLOWED_PLATFORMS:
            raise ValueError(f"platform şunlardan biri olmalı: {', '.join(sorted(ALLOWED_PLATFORMS))}")
        return v

    @field_validator("api_key", "api_secret")
    @classmethod
    def _non_empty_secret(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 4:
            raise ValueError("Değer çok kısa görünüyor")
        return v


def _get_owned_store(db: Session, store_id: int, user: User) -> Store:
    store = db.query(Store).filter(Store.id == store_id, Store.user_id == user.id).first()
    if not store:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mağaza bulunamadı")
    return store


def _cred_extra(cred: StoreCredential) -> Dict[str, Any]:
    try:
        data = json.loads(cred.extra_json) if cred.extra_json else {}
        return data if isinstance(data, dict) else {}
    except (TypeError, ValueError):
        return {}


def _credential_public(cred: StoreCredential) -> dict:
    try:
        key_preview = mask_secret(decrypt_secret(cred.api_key_encrypted))
    except Exception:
        key_preview = "****"  # şifre çözme başarısız olsa bile endpoint çökmesin
    extra = _cred_extra(cred)
    return {
        "platform": cred.platform,
        "supplier_id": cred.supplier_id,
        "api_key_preview": key_preview,
        "is_connected": cred.is_connected,
        "connected_at": cred.connected_at.isoformat() if cred.connected_at else None,
        # Son bağlantı testi (POST .../credentials/trendyol/test): ok | auth_failed | error | None
        "last_test": extra.get("last_test"),
    }


@router.get("/stores")
async def list_stores(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    stores = db.query(Store).filter(Store.user_id == user.id).all()
    return [{"id": s.id, "store_name": s.store_name, "is_active": s.is_active} for s in stores]


@router.post("/stores", status_code=status.HTTP_201_CREATED)
async def create_store(body: CreateStoreBody, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    store = Store(user_id=user.id, store_name=body.store_name, is_active=True)
    db.add(store)
    db.commit()
    db.refresh(store)
    return {"id": store.id, "store_name": store.store_name, "is_active": store.is_active}


@router.patch("/stores/{store_id}")
async def rename_store(
    store_id: int, body: CreateStoreBody, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Mağaza adını değiştirir (Ayarlar → Hesap & Mağaza)."""
    store = _get_owned_store(db, store_id, user)
    if len(body.store_name) > 60:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Mağaza adı en fazla 60 karakter olabilir")
    store.store_name = body.store_name
    db.commit()
    return {"id": store.id, "store_name": store.store_name, "is_active": store.is_active}


@router.get("/stores/{store_id}/credentials")
async def list_credentials(store_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    store = _get_owned_store(db, store_id, user)
    creds = db.query(StoreCredential).filter(StoreCredential.store_id == store.id).all()
    return [_credential_public(c) for c in creds]


@router.post("/stores/{store_id}/credentials")
async def connect_credentials(
    store_id: int,
    body: ConnectCredentialsBody,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Bir platform için API kimlik bilgilerini kaydeder/günceller (upsert). Secret'lar
    şifrelenmiş saklanır, yanıt olarak ASLA ham değer dönülmez — sadece maskelenmiş önizleme."""
    store = _get_owned_store(db, store_id, user)

    if body.platform == "trendyol" and not (body.supplier_id and body.supplier_id.strip()):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Trendyol için supplier_id zorunlu")

    existing = (
        db.query(StoreCredential)
        .filter(StoreCredential.store_id == store.id, StoreCredential.platform == body.platform)
        .first()
    )
    if existing:
        existing.supplier_id = body.supplier_id
        existing.api_key_encrypted = encrypt_secret(body.api_key)
        existing.api_secret_encrypted = encrypt_secret(body.api_secret)
        existing.is_connected = True
        extra = _cred_extra(existing)
        extra.pop("last_test", None)  # yeni anahtarlar henüz test edilmedi
        existing.extra_json = json.dumps(extra, ensure_ascii=False) if extra else None
        db.commit()
        db.refresh(existing)
        return _credential_public(existing)

    cred = StoreCredential(
        store_id=store.id,
        platform=body.platform,
        supplier_id=body.supplier_id,
        api_key_encrypted=encrypt_secret(body.api_key),
        api_secret_encrypted=encrypt_secret(body.api_secret),
        is_connected=True,
    )
    db.add(cred)
    db.commit()
    db.refresh(cred)
    return _credential_public(cred)


@router.delete("/stores/{store_id}/credentials/{platform}")
async def disconnect_credentials(
    store_id: int, platform: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    store = _get_owned_store(db, store_id, user)
    cred = (
        db.query(StoreCredential)
        .filter(StoreCredential.store_id == store.id, StoreCredential.platform == platform)
        .first()
    )
    if not cred:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bağlantı bulunamadı")
    db.delete(cred)
    db.commit()
    return {"message": "Bağlantı kaldırıldı"}


def _probe_trendyol(supplier_id: str, api_key: str, api_secret: str) -> Dict[str, Any]:
    """Trendyol'a TEK hafif istek atıp anahtarları doğrular (sipariş listesi, size=1).
    Ağ çağrısı bloklayıcı olduğu için asyncio.to_thread ile çağrılır."""
    from utils.store_trendyol import TrendyolCreds, _auth_headers, _integration_base

    creds = TrendyolCreds(api_key, api_secret, supplier_id, 0)
    url = f"{_integration_base()}/order/sellers/{supplier_id}/v2/orders"
    try:
        resp = requests.get(url, headers=_auth_headers(creds), params={"page": 0, "size": 1}, timeout=15)
    except requests.RequestException as e:
        return {"status": "error", "message": f"Trendyol'a ulaşılamadı: {e.__class__.__name__}"}
    if resp.status_code == 200:
        return {"status": "ok", "message": "Bağlantı başarılı — Trendyol anahtarları çalışıyor."}
    if resp.status_code in (401, 403):
        return {
            "status": "auth_failed",
            "message": "Trendyol anahtarları reddetti (HTTP %d) — API Key, API Secret ve Satıcı ID'yi kontrol edin." % resp.status_code,
        }
    if resp.status_code == 429:
        return {"status": "error", "message": "Trendyol istek sınırı aşıldı (429) — birkaç dakika sonra tekrar deneyin."}
    return {"status": "error", "message": f"Trendyol beklenmeyen yanıt verdi (HTTP {resp.status_code})."}


@router.post("/stores/{store_id}/credentials/trendyol/test")
async def test_trendyol_credentials(
    store_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Kayıtlı Trendyol anahtarlarını gerçek bir API çağrısıyla test eder ve sonucu
    saklar (Ayarlar'daki 'Bağlı' rozeti artık anahtarın gerçekten çalıştığını gösterir)."""
    store = _get_owned_store(db, store_id, user)
    cred = (
        db.query(StoreCredential)
        .filter(StoreCredential.store_id == store.id, StoreCredential.platform == "trendyol")
        .first()
    )
    if not cred:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Önce Trendyol anahtarlarını kaydedin")
    if not cred.supplier_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Satıcı ID eksik")
    try:
        api_key = decrypt_secret(cred.api_key_encrypted)
        api_secret = decrypt_secret(cred.api_secret_encrypted)
    except Exception:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Kayıtlı anahtarlar çözülemedi — yeniden girin")

    result = await asyncio.to_thread(_probe_trendyol, cred.supplier_id, api_key, api_secret)
    result["tested_at"] = datetime.utcnow().isoformat() + "Z"
    extra = _cred_extra(cred)
    extra["last_test"] = result
    cred.extra_json = json.dumps(extra, ensure_ascii=False)
    db.commit()
    return result


# ---------------------------------------------------------------------------
# Mağaza ayarları — Kâr Hesaplama + Etiket & Barkod (utils/store_settings.py)
# ---------------------------------------------------------------------------
@router.get("/store-settings")
async def get_store_settings(store: Store = Depends(get_current_store), db: Session = Depends(get_db)):
    return get_effective_store_settings(db, store.id)


@router.put("/store-settings")
async def put_store_settings(
    body: Dict[str, Any] = Body(...),
    store: Store = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    """Kısmi günceller. Gönderilmeyen alan değişmez; null gönderilen alan varsayılana döner.
    Hata mesajı tek bir metin olarak döner (frontend toast'ında doğrudan gösterilebilir)."""
    unknown = sorted(set(body) - set(STORE_SETTING_FIELDS))
    if unknown:
        raise HTTPException(status_code=422, detail=f"Bilinmeyen ayar: {', '.join(unknown)}")
    try:
        return update_store_settings(db, store.id, body)
    except SettingsValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="Geçersiz değer — sayı alanlarına sayı girin")


@router.delete("/store-settings/{field}")
async def reset_store_setting(field: str, store: Store = Depends(get_current_store), db: Session = Depends(get_db)):
    if field not in STORE_SETTING_FIELDS:
        raise HTTPException(status_code=400, detail="Geçersiz ayar alanı")
    return update_store_settings(db, store.id, {field: None})


@router.get("/store-settings/commission-categories")
async def list_commission_categories(store: Store = Depends(get_current_store), db: Session = Depends(get_db)):
    """Bu mağazanın ürünlerindeki Trendyol kategori adları (komisyon tablosu için)."""
    from sqlalchemy import func

    rows = (
        db.query(Product.category, func.count(Product.id))
        .filter(Product.store_id == store.id, Product.category.isnot(None), Product.category != "")
        .group_by(Product.category)
        .order_by(func.count(Product.id).desc())
        .all()
    )
    return [{"category": c, "product_count": n} for c, n in rows]


# ---------------------------------------------------------------------------
# w3-configurable-thresholds — mağaza bazında ayarlanabilir uyarı eşikleri.
# Spec: hive/docs/thresholds-spec.md. Kalıcı: store_thresholds tablosu (bellekte
# DEĞİL — automation.py'nin önceki hatası tekrarlanmadı). NULL alan = varsayılan.
# ---------------------------------------------------------------------------
class ThresholdsUpdate(BaseModel):
    margin_warning_threshold: Optional[float] = None
    low_stock_floor: Optional[int] = None
    low_stock_sales_ratio: Optional[float] = None

    @field_validator("margin_warning_threshold")
    @classmethod
    def _margin_range(cls, v):
        if v is not None and not (MARGIN_WARNING_THRESHOLD_MIN <= v <= MARGIN_WARNING_THRESHOLD_MAX):
            raise ValueError(
                f"margin_warning_threshold {MARGIN_WARNING_THRESHOLD_MIN}-{MARGIN_WARNING_THRESHOLD_MAX} arasında olmalı"
            )
        return v

    @field_validator("low_stock_floor")
    @classmethod
    def _floor_range(cls, v):
        if v is not None and not (LOW_STOCK_FLOOR_MIN <= v <= LOW_STOCK_FLOOR_MAX):
            raise ValueError(f"low_stock_floor {LOW_STOCK_FLOOR_MIN}-{LOW_STOCK_FLOOR_MAX} arasında olmalı")
        return v

    @field_validator("low_stock_sales_ratio")
    @classmethod
    def _ratio_range(cls, v):
        if v is not None and not (LOW_STOCK_SALES_RATIO_MIN <= v <= LOW_STOCK_SALES_RATIO_MAX):
            raise ValueError(
                f"low_stock_sales_ratio {LOW_STOCK_SALES_RATIO_MIN}-{LOW_STOCK_SALES_RATIO_MAX} arasında olmalı"
            )
        return v


@router.get("/thresholds")
async def get_thresholds(store: Store = Depends(get_current_store), db: Session = Depends(get_db)):
    """Bu mağazanın EFEKTİF eşik değerlerini döner (hiç ayarlanmamışsa varsayılanlar)."""
    return get_effective_thresholds(db, store.id)


@router.put("/thresholds")
async def update_thresholds(
    body: ThresholdsUpdate,
    store: Store = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    """Kısmi günceller — body'de gönderilmeyen (None) alan DOKUNULMADAN kalır
    (mevcut özelleştirme varsa korunur, yoksa varsayılan olarak kalmaya devam eder)."""
    row = db.query(StoreThreshold).filter(StoreThreshold.store_id == store.id).first()
    if not row:
        row = StoreThreshold(store_id=store.id)
        db.add(row)

    if body.margin_warning_threshold is not None:
        row.margin_warning_threshold = body.margin_warning_threshold
    if body.low_stock_floor is not None:
        row.low_stock_floor = body.low_stock_floor
    if body.low_stock_sales_ratio is not None:
        row.low_stock_sales_ratio = body.low_stock_sales_ratio

    db.commit()
    return get_effective_thresholds(db, store.id)


_RESETTABLE_THRESHOLD_FIELDS = {"margin_warning_threshold", "low_stock_floor", "low_stock_sales_ratio"}


@router.delete("/thresholds/{field}")
async def reset_threshold(
    field: str,
    store: Store = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    """Bir alanı özelleştirmeden çıkarıp varsayılana döndürür (NULL'a çeker).
    Oscar'ın bulgusu: PUT'ta null='dokunma' anlamına geldiği için gerçek bir
    'özelleştirmeyi kaldır' yolu yoktu — bu onu sağlıyor."""
    if field not in _RESETTABLE_THRESHOLD_FIELDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Geçersiz alan. Şunlardan biri olmalı: {', '.join(sorted(_RESETTABLE_THRESHOLD_FIELDS))}",
        )

    row = db.query(StoreThreshold).filter(StoreThreshold.store_id == store.id).first()
    if row:
        setattr(row, field, None)
        db.commit()

    return get_effective_thresholds(db, store.id)
