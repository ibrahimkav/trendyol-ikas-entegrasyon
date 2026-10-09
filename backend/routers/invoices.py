"""
ikas Fatura Router — ikas siparişlerini Excel/CSV ile içe aktarıp Trendyol E-Faturam
üzerinden faturalamak için.

1. aşama (bu dosya): dosya yükleme, sipariş listesi, fatura taslağı (KDV ayrıştırma),
   eksik fatura bilgilerini elle düzeltme, KDV ayarları.
2. aşama (henüz yok): E-Faturam (Digital Planet altyapısı) web servis bağlantısı ve
   faturanın gerçekten kesilmesi — entegrasyon bilgileri ve test hesabı bekleniyor.
"""
import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from utils.ikas_import import (
    BILLING_FIELDS,
    ImportFileError,
    build_invoice_draft,
    parse_orders,
    read_table,
)

router = APIRouter()

MAX_UPLOAD_BYTES = 10 * 1024 * 1024

# Database modülünü optional olarak yükle (ghost mode) — projedeki standart desen.
try:
    from database.db import get_db
    from database.models import IkasOrder, InvoiceSettings
    from security import get_current_store
    _db_available = True
except Exception:
    _db_available = False

    def get_db():
        raise HTTPException(status_code=503, detail="Database not available (ghost mode)")

    def get_current_store():
        raise HTTPException(status_code=503, detail="Database not available (ghost mode)")


# ---------------------------------------------------------------------------
# Yardımcılar
# ---------------------------------------------------------------------------

def _get_settings(db: Session, store_id: int) -> "InvoiceSettings":
    settings = db.query(InvoiceSettings).filter(InvoiceSettings.store_id == store_id).first()
    if settings is None:
        settings = InvoiceSettings(store_id=store_id, product_vat_rate=10.0, shipping_vat_rate=20.0)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


def _loads(text: Optional[str]) -> Dict[str, Any]:
    try:
        return json.loads(text) if text else {}
    except (TypeError, ValueError):
        return {}


def _draft_for(rec: "IkasOrder", settings: "InvoiceSettings") -> Dict[str, Any]:
    return build_invoice_draft(
        _loads(rec.data_json),
        _loads(rec.overrides_json),
        product_vat_rate=settings.product_vat_rate,
        shipping_vat_rate=settings.shipping_vat_rate,
    )


def _display_status(rec: "IkasOrder", draft: Dict[str, Any]) -> str:
    if rec.status in ("invoiced", "error"):
        return rec.status
    return "ready" if draft["ready"] else "needs_info"


def _summary(rec: "IkasOrder", draft: Dict[str, Any]) -> Dict[str, Any]:
    billing = draft["billing"]
    return {
        "order_number": rec.order_number,
        "order_date": rec.order_date,
        "customer": billing["company_name"] or billing["full_name"],
        "buyer_type": draft["buyer_type"],
        "city": billing["city"],
        "gross_total": draft["totals"]["gross"],
        "vat_total": draft["totals"]["vat"],
        "status": _display_status(rec, draft),
        "errors": draft["errors"],
        "warnings": draft["warnings"],
        "edited": bool(_loads(rec.overrides_json)),
        "invoice_number": rec.invoice_number,
        "invoice_error": rec.invoice_error,
    }


def _get_order(db: Session, store_id: int, order_number: str) -> "IkasOrder":
    rec = (
        db.query(IkasOrder)
        .filter(IkasOrder.store_id == store_id, IkasOrder.order_number == order_number)
        .first()
    )
    if rec is None:
        raise HTTPException(status_code=404, detail="Sipariş bulunamadı")
    return rec


# ---------------------------------------------------------------------------
# İçe aktarma
# ---------------------------------------------------------------------------

@router.post("/ikas/import")
async def import_ikas_orders(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    store=Depends(get_current_store),
):
    """ikas'tan dışa aktarılan sipariş dosyasını (XLSX/CSV) içe aktarır.
    Aynı sipariş tekrar yüklenirse dosya verisi yenilenir, elle yapılan düzeltmeler
    korunur; faturası kesilmiş siparişlere dokunulmaz."""
    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Dosya 10 MB'tan büyük olamaz")
    try:
        df = read_table(file.filename or "", content)
    except ImportFileError as e:
        raise HTTPException(status_code=400, detail=str(e))

    parsed = parse_orders(df)
    if "order_number" in parsed["missing_fields"]:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Dosyada sipariş numarası kolonu bulunamadı — ikas sipariş dışa aktarma dosyası mı?",
                "columns": [str(c) for c in df.columns],
            },
        )

    created = updated = skipped_invoiced = 0
    for order in parsed["orders"]:
        rec = (
            db.query(IkasOrder)
            .filter(IkasOrder.store_id == store.id, IkasOrder.order_number == order["order_number"])
            .first()
        )
        data_json = json.dumps(order, ensure_ascii=False)
        order_date = order["fields"].get("order_date")
        if rec is None:
            db.add(IkasOrder(
                store_id=store.id,
                order_number=order["order_number"],
                order_date=order_date,
                data_json=data_json,
                status="pending",
            ))
            created += 1
        elif rec.status == "invoiced":
            skipped_invoiced += 1
        else:
            rec.data_json = data_json
            rec.order_date = order_date
            updated += 1
    db.commit()

    return {
        "orders_in_file": len(parsed["orders"]),
        "rows_in_file": int(len(df)),
        "created": created,
        "updated": updated,
        "skipped_invoiced": skipped_invoiced,
        "recognized_columns": parsed["mapping"],
        "ignored_columns": parsed["ignored_columns"],
        "missing_fields": parsed["missing_fields"],
    }


# ---------------------------------------------------------------------------
# Sipariş listesi / detay / düzeltme
# ---------------------------------------------------------------------------

@router.get("/ikas/orders")
async def list_ikas_orders(
    status: str = Query("all", pattern="^(all|ready|needs_info|invoiced|error)$"),
    q: Optional[str] = None,
    db: Session = Depends(get_db),
    store=Depends(get_current_store),
):
    settings = _get_settings(db, store.id)
    records = (
        db.query(IkasOrder)
        .filter(IkasOrder.store_id == store.id)
        .order_by(IkasOrder.imported_at.desc(), IkasOrder.id.desc())
        .all()
    )
    items: List[Dict[str, Any]] = []
    counts = {"all": 0, "ready": 0, "needs_info": 0, "invoiced": 0, "error": 0}
    needle = (q or "").strip().lower()
    for rec in records:
        item = _summary(rec, _draft_for(rec, settings))
        if needle and needle not in f"{item['order_number']} {item['customer']}".lower():
            continue
        counts["all"] += 1
        counts[item["status"]] += 1
        if status == "all" or item["status"] == status:
            items.append(item)
    return {"items": items, "counts": counts}


@router.get("/ikas/orders/{order_number}")
async def get_ikas_order(
    order_number: str,
    db: Session = Depends(get_db),
    store=Depends(get_current_store),
):
    settings = _get_settings(db, store.id)
    rec = _get_order(db, store.id, order_number)
    draft = _draft_for(rec, settings)
    data = _loads(rec.data_json)
    return {
        **_summary(rec, draft),
        "draft": draft,
        "overrides": _loads(rec.overrides_json),
        "source_fields": data.get("fields", {}),
        "raw_rows": data.get("raw_rows", []),
    }


class BillingOverride(BaseModel):
    """Elle düzeltilen fatura alanları. Gönderilmeyen alan değişmez; boş string
    ('') gönderilirse o alanın düzeltmesi kaldırılır (dosyadaki değere dönülür)."""
    full_name: Optional[str] = None
    company_name: Optional[str] = None
    identity_number: Optional[str] = None
    tax_number: Optional[str] = None
    tax_office: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    district: Optional[str] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None


@router.patch("/ikas/orders/{order_number}")
async def update_ikas_order(
    order_number: str,
    body: BillingOverride,
    db: Session = Depends(get_db),
    store=Depends(get_current_store),
):
    rec = _get_order(db, store.id, order_number)
    if rec.status == "invoiced":
        raise HTTPException(status_code=409, detail="Faturası kesilmiş sipariş düzenlenemez")
    overrides = _loads(rec.overrides_json)
    for key, value in body.model_dump(exclude_unset=True).items():
        if key not in BILLING_FIELDS or value is None:
            continue
        value = value.strip()
        if value:
            overrides[key] = value
        else:
            overrides.pop(key, None)
    rec.overrides_json = json.dumps(overrides, ensure_ascii=False) if overrides else None
    db.commit()
    settings = _get_settings(db, store.id)
    return _summary(rec, _draft_for(rec, settings))


@router.delete("/ikas/orders/{order_number}")
async def delete_ikas_order(
    order_number: str,
    db: Session = Depends(get_db),
    store=Depends(get_current_store),
):
    rec = _get_order(db, store.id, order_number)
    if rec.status == "invoiced":
        raise HTTPException(status_code=409, detail="Faturası kesilmiş sipariş silinemez")
    db.delete(rec)
    db.commit()
    return {"deleted": order_number}


# ---------------------------------------------------------------------------
# Ayarlar
# ---------------------------------------------------------------------------

class InvoiceSettingsBody(BaseModel):
    product_vat_rate: float = Field(..., ge=0, le=100)
    shipping_vat_rate: float = Field(..., ge=0, le=100)


@router.get("/settings")
async def get_invoice_settings(
    db: Session = Depends(get_db),
    store=Depends(get_current_store),
):
    s = _get_settings(db, store.id)
    return {
        "product_vat_rate": s.product_vat_rate,
        "shipping_vat_rate": s.shipping_vat_rate,
        "efaturam_connected": False,  # 2. aşama: E-Faturam web servis bağlantısı
    }


@router.put("/settings")
async def update_invoice_settings(
    body: InvoiceSettingsBody,
    db: Session = Depends(get_db),
    store=Depends(get_current_store),
):
    s = _get_settings(db, store.id)
    s.product_vat_rate = body.product_vat_rate
    s.shipping_vat_rate = body.shipping_vat_rate
    db.commit()
    return {
        "product_vat_rate": s.product_vat_rate,
        "shipping_vat_rate": s.shipping_vat_rate,
        "efaturam_connected": False,
    }
