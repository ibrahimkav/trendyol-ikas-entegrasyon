"""
Ayarlar: mağaza yönetimi + platform API kimlik bilgisi bağlama (store-connect).

Wave 1 kapsamı: sadece şekil-doğrulama + şifreli saklama. GERÇEK Trendyol/Hepsiburada
API doğrulaması (kimlik bilgilerinin gerçekten çalıştığını test etme) burada YAPILMAZ —
insan gerçek key'leri entegrasyon sırasında verdiğinde eklenecek (Wave 2+).
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from database.db import get_db
from database.models import Store, StoreCredential, StoreThreshold, User
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


def _credential_public(cred: StoreCredential) -> dict:
    try:
        key_preview = mask_secret(decrypt_secret(cred.api_key_encrypted))
    except Exception:
        key_preview = "****"  # şifre çözme başarısız olsa bile endpoint çökmesin
    return {
        "platform": cred.platform,
        "supplier_id": cred.supplier_id,
        "api_key_preview": key_preview,
        "is_connected": cred.is_connected,
        "connected_at": cred.connected_at.isoformat() if cred.connected_at else None,
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
