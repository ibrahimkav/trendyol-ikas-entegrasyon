"""
Mağaza bazında genel ayarlar (Ayarlar → Kâr Hesaplama, Etiket & Barkod).

Daha önce bu değerler ya global ve kimlik doğrulamasız bellek-içi değişkendi
(kargo maliyeti — tüm mağazalarda ortak, yeniden başlatınca kayboluyordu), ya da
koda gömülüydü (komisyon %10, etiket indirim kodu 'TRENDYOL15', site adı).

Desen utils/thresholds.py ile aynı: DB'de satır yoksa ya da alan NULL ise varsayılan
kullanılır; get_effective_store_settings her zaman TAM şema döner. Varsayılanlar
eski davranışla aynıdır (hiç ayar girilmemiş mağazada sonuçlar değişmez).
"""
import json
import os
import re
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from database.models import StoreSettings

# --- Varsayılanlar (eski koddaki sabitlerle aynı) ---------------------------
DEFAULTS: Dict[str, Any] = {
    # financial.py: CARGO_COST_PER_PRODUCT env varsayılanı
    "cargo_cost": float(os.getenv("CARGO_COST_PER_PRODUCT", "75.0")),
    # financial.calculate_commission'ın kategori eşleşmediğinde kullandığı oran
    "default_commission_rate": 10.0,
    "category_commissions": {},
    # routers/barcode.py etiket sabitleri
    "label_discount_code": "TRENDYOL15",
    "label_discount_percent": 15,
    "label_website_url": "penaltidenim.com",
    "label_website_text": "penaltıdenim.com",
    "label_brand_text": "PENALTI DENİM",
    "label_brand_ribbon_enabled": True,
    "label_group_by_product": True,
}

CARGO_COST_MIN, CARGO_COST_MAX = 0.0, 2000.0
COMMISSION_MIN, COMMISSION_MAX = 0.0, 50.0
DISCOUNT_PERCENT_MIN, DISCOUNT_PERCENT_MAX = 0, 90
MAX_CATEGORY_COMMISSIONS = 300

_COLUMN = {"category_commissions": "category_commissions_json"}

FIELD_LABELS = {
    "cargo_cost": "Kargo maliyeti",
    "default_commission_rate": "Varsayılan komisyon",
    "category_commissions": "Kategori komisyonları",
    "label_discount_code": "İndirim kodu",
    "label_discount_percent": "İndirim yüzdesi",
    "label_website_url": "Web sitesi adresi",
    "label_website_text": "Etikette görünen site yazısı",
    "label_brand_text": "Marka şeridi yazısı",
    "label_brand_ribbon_enabled": "Marka şeridi",
    "label_group_by_product": "Aynı ürünler art arda",
}
FIELDS = list(DEFAULTS.keys())

_DISCOUNT_CODE_RE = re.compile(r"^[A-Z0-9_-]{1,30}$")
_DOMAIN_RE = re.compile(r"^(?!-)[a-z0-9-]+(\.[a-z0-9-]+)+(/[^\s]*)?$")


class SettingsValidationError(ValueError):
    """Kullanıcıya gösterilecek doğrulama hatası (alan + mesaj)."""

    def __init__(self, field: str, message: str):
        super().__init__(f"{FIELD_LABELS.get(field, field)}: {message}")
        self.field = field
        self.message = message


def _fold(text: str) -> str:
    return " ".join(str(text).replace("İ", "i").replace("I", "ı").casefold().split())


def validate_value(field: str, value: Any) -> Any:
    """Tek alanı doğrular ve normalize eder. Geçersizse SettingsValidationError."""
    if field not in DEFAULTS:
        raise SettingsValidationError(field, "bilinmeyen ayar")
    if field == "cargo_cost":
        v = float(value)
        if not (CARGO_COST_MIN <= v <= CARGO_COST_MAX):
            raise SettingsValidationError(field, f"{CARGO_COST_MIN:g}–{CARGO_COST_MAX:g} ₺ arasında olmalı")
        return round(v, 2)
    if field == "default_commission_rate":
        v = float(value)
        if not (COMMISSION_MIN <= v <= COMMISSION_MAX):
            raise SettingsValidationError(field, f"%{COMMISSION_MIN:g}–%{COMMISSION_MAX:g} arasında olmalı")
        return round(v, 2)
    if field == "category_commissions":
        if not isinstance(value, dict):
            raise SettingsValidationError(field, "kategori → oran sözlüğü olmalı")
        if len(value) > MAX_CATEGORY_COMMISSIONS:
            raise SettingsValidationError(field, f"en fazla {MAX_CATEGORY_COMMISSIONS} kategori")
        cleaned: Dict[str, float] = {}
        for name, rate in value.items():
            name = " ".join(str(name).split())
            if not name or len(name) > 100:
                raise SettingsValidationError(field, "kategori adı 1–100 karakter olmalı")
            try:
                rate = float(rate)
            except (TypeError, ValueError):
                raise SettingsValidationError(field, f"'{name}' için oran sayı olmalı")
            if not (COMMISSION_MIN <= rate <= COMMISSION_MAX):
                raise SettingsValidationError(field, f"'{name}' oranı %{COMMISSION_MIN:g}–%{COMMISSION_MAX:g} arasında olmalı")
            cleaned[name] = round(rate, 2)
        return cleaned
    if field == "label_discount_code":
        v = str(value).strip().upper()
        if not _DISCOUNT_CODE_RE.match(v):
            raise SettingsValidationError(field, "1–30 karakter; sadece harf, rakam, - ve _")
        return v
    if field == "label_discount_percent":
        if isinstance(value, bool):
            raise SettingsValidationError(field, "tam sayı olmalı")
        v = float(value)
        if not v.is_integer() or not (DISCOUNT_PERCENT_MIN <= v <= DISCOUNT_PERCENT_MAX):
            raise SettingsValidationError(field, f"{DISCOUNT_PERCENT_MIN}–{DISCOUNT_PERCENT_MAX} arası tam sayı olmalı")
        return int(v)
    if field == "label_website_url":
        v = str(value).strip().lower()
        v = re.sub(r"^https?://", "", v).rstrip("/")
        if not (3 <= len(v) <= 80) or not _DOMAIN_RE.match(v):
            raise SettingsValidationError(field, "geçerli bir alan adı olmalı (ör. penaltidenim.com)")
        return v
    if field in ("label_website_text", "label_brand_text"):
        limit = 40 if field == "label_website_text" else 30
        v = " ".join(str(value).split())
        if not (1 <= len(v) <= limit):
            raise SettingsValidationError(field, f"1–{limit} karakter olmalı")
        return v
    if field in ("label_brand_ribbon_enabled", "label_group_by_product"):
        if not isinstance(value, bool):
            raise SettingsValidationError(field, "true/false olmalı")
        return value
    raise SettingsValidationError(field, "desteklenmiyor")  # pragma: no cover


def _read(row: Optional[StoreSettings], field: str) -> Any:
    if row is None:
        return None
    raw = getattr(row, _COLUMN.get(field, field))
    if field == "category_commissions" and raw is not None:
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else None
        except (TypeError, ValueError):
            return None
    return raw


def get_effective_store_settings(db: Session, store_id: int) -> Dict[str, Any]:
    """Bu mağazanın efektif ayarları + hangi alanların özelleştirildiği."""
    row = db.query(StoreSettings).filter(StoreSettings.store_id == store_id).first()
    result: Dict[str, Any] = {}
    customized: Dict[str, bool] = {}
    for field in FIELDS:
        value = _read(row, field)
        customized[field] = value is not None and not (field == "category_commissions" and value == {})
        result[field] = value if value is not None else DEFAULTS[field]
    result["is_customized"] = customized
    result["defaults"] = dict(DEFAULTS)
    return result


def update_store_settings(db: Session, store_id: int, changes: Dict[str, Any]) -> Dict[str, Any]:
    """Kısmi günceller: changes'teki alanlar doğrulanıp yazılır, value=None alan
    varsayılana döndürülür. Hepsi doğrulanmadan hiçbir şey yazılmaz."""
    validated = {field: (None if value is None else validate_value(field, value)) for field, value in changes.items()}
    row = db.query(StoreSettings).filter(StoreSettings.store_id == store_id).first()
    if row is None:
        row = StoreSettings(store_id=store_id)
        db.add(row)
    for field, value in validated.items():
        column = _COLUMN.get(field, field)
        if field == "category_commissions" and value is not None:
            value = json.dumps(value, ensure_ascii=False) if value else None
        setattr(row, column, value)
    db.commit()
    return get_effective_store_settings(db, store_id)


def commission_rate_for(settings: Dict[str, Any], category: Optional[str]) -> float:
    """Kategori için komisyon oranı (%): mağazanın kategori tablosunda (büyük/küçük harf
    duyarsız) varsa o, yoksa mağazanın varsayılan oranı."""
    if category:
        wanted = _fold(category)
        for name, rate in (settings.get("category_commissions") or {}).items():
            if _fold(name) == wanted:
                return float(rate)
    return float(settings.get("default_commission_rate", DEFAULTS["default_commission_rate"]))


def label_config(settings: Dict[str, Any]) -> Dict[str, Any]:
    """Etiket üretimine geçirilecek alt küme (routers/barcode.py)."""
    return {
        "discount_code": settings["label_discount_code"],
        "discount_percent": settings["label_discount_percent"],
        "website_url": settings["label_website_url"],
        "website_text": settings["label_website_text"],
        "brand_text": settings["label_brand_text"],
        "brand_ribbon_enabled": settings["label_brand_ribbon_enabled"],
        "group_by_product": settings["label_group_by_product"],
    }
