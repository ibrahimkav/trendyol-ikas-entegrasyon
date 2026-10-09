"""
Beden Tablosu Router
Ürün beden tablolarının CRUD işlemleri + metinden tablo ayrıştırma

w3-sizechart-guard: bu router'ın 4 CRUD endpoint'i AUTH'SUZ ve store_id'siz
sorguluyordu (kendi SessionLocal() çağrısıyla, DI/get_db bypass edilerek) —
herhangi biri kimlik doğrulaması olmadan TÜM mağazaların beden tablolarını
görebiliyor, BAŞKA mağazanın kaydının üzerine yazabiliyor/silebiliyordu.
SizeChart modelinde store_id ZATEN VARDI (nullable=False, default=1) — eksik
olan bu router'ın onu kullanmasıydı, şema değişikliği gerekmedi (tablo 0
satırdı, veri taşıma da gerekmedi).
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
import json

from utils.size_advisor import parse_chart_text, validate_sizes

router = APIRouter()

# Database modülünü optional olarak yükle (ghost mode) — projedeki standart desen.
try:
    from database.db import get_db
    from database.models import SizeChart, Store
    from security import get_current_store, get_current_user
    _db_available = True
except Exception:
    _db_available = False
    def get_db():
        raise HTTPException(status_code=503, detail="Database not available (ghost mode)")

    def get_current_store():
        raise HTTPException(status_code=503, detail="Database not available (ghost mode)")

    def get_current_user():
        raise HTTPException(status_code=503, detail="Database not available (ghost mode)")


class SizeRow(BaseModel):
    """Tek bir beden satırı (tüm ölçüler opsiyonel)"""
    size: str
    bel_min: Optional[float] = None
    bel_max: Optional[float] = None
    gogus_min: Optional[float] = None
    gogus_max: Optional[float] = None
    kalca_min: Optional[float] = None
    kalca_max: Optional[float] = None
    boy_min: Optional[float] = None
    boy_max: Optional[float] = None
    kilo_min: Optional[float] = None
    kilo_max: Optional[float] = None


class SizeChartRequest(BaseModel):
    product_name: Optional[str] = None
    image_url: Optional[str] = None
    notes: Optional[str] = None
    sizes: List[SizeRow]


class ChartTextRequest(BaseModel):
    """Yapıştırılan düz metin tablo -> JSON'a çevirir"""
    text: str


def _chart_to_dict(rec: SizeChart) -> Dict[str, Any]:
    try:
        sizes = json.loads(rec.sizes_json)
    except (ValueError, TypeError):
        sizes = []
    return {
        "product_code": rec.product_code,
        "product_name": rec.product_name,
        "image_url": rec.image_url,
        "notes": rec.notes,
        "sizes": sizes,
        "size_count": len(sizes),
        "created_at": rec.created_at.isoformat() if rec.created_at else None,
        "updated_at": rec.updated_at.isoformat() if rec.updated_at else None,
    }


@router.get("/")
async def list_charts(
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Session = Depends(get_db) if _db_available else None,
):
    """Bu mağazanın tüm beden tablolarını listeler."""
    rows = (
        db.query(SizeChart)
        .filter(SizeChart.store_id == store.id)
        .order_by(SizeChart.updated_at.desc())
        .all()
    )
    return {"charts": [_chart_to_dict(r) for r in rows], "total_count": len(rows)}


@router.get("/{product_code}")
async def get_chart(
    product_code: str,
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Session = Depends(get_db) if _db_available else None,
):
    """Bu mağazada belirli ürünün beden tablosunu döndürür."""
    rec = (
        db.query(SizeChart)
        .filter(SizeChart.store_id == store.id, SizeChart.product_code == product_code)
        .first()
    )
    if not rec:
        raise HTTPException(status_code=404, detail="Bu ürün için beden tablosu bulunamadı")
    return _chart_to_dict(rec)


@router.post("/parse-text")
async def parse_text_chart(
    req: ChartTextRequest,
    user=Depends(get_current_user) if _db_available else None,
):
    """Yapıştırılan düz metin beden tablosunu JSON satırlarına çevirir.
    Kaydetmez, sadece önizleme döner (sonra POST /{product_code} ile kaydedilir).
    NOT: hiçbir DB okuma/yazma yapmıyor (saf metin ayrıştırma) — store-scoping
    kavramı buraya uygulanmaz, ama tamamen açık/anonim bir utility endpoint
    olmasın diye en azından giriş yapmış kullanıcı zorunlu tutuldu."""
    rows = parse_chart_text(req.text)
    if not rows:
        raise HTTPException(
            status_code=400,
            detail=("Tablo ayrıştırılamadı. Örnek format:\n"
                    "S: Bel 71-76, Göğüs 83-88, Boy 165-170, Kilo 50-60\n"
                    "M: Bel 76-81, Göğüs 88-93, Boy 170-175, Kilo 60-70")
        )
    return {"success": True, "sizes": rows, "size_count": len(rows)}


@router.post("/{product_code}")
async def upsert_chart(
    product_code: str,
    req: SizeChartRequest,
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Session = Depends(get_db) if _db_available else None,
):
    """Bu mağaza için ürün beden tablosu ekler/günceller."""
    ok, msg = validate_sizes([r.dict() for r in req.sizes])
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    rec = (
        db.query(SizeChart)
        .filter(SizeChart.store_id == store.id, SizeChart.product_code == product_code)
        .first()
    )
    if rec is None:
        rec = SizeChart(store_id=store.id, product_code=product_code)
        db.add(rec)
    rec.product_name = req.product_name
    rec.image_url = req.image_url
    rec.notes = req.notes
    rec.sizes_json = json.dumps([r.dict() for r in req.sizes], ensure_ascii=False)
    db.commit()
    return {"success": True, "message": "Beden tablosu kaydedildi", "chart": _chart_to_dict(rec)}


@router.delete("/{product_code}")
async def delete_chart(
    product_code: str,
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Session = Depends(get_db) if _db_available else None,
):
    """Bu mağazanın ürününe ait beden tablosunu siler."""
    deleted = (
        db.query(SizeChart)
        .filter(SizeChart.store_id == store.id, SizeChart.product_code == product_code)
        .delete()
    )
    db.commit()
    if not deleted:
        raise HTTPException(status_code=404, detail="Beden tablosu bulunamadı")
    return {"success": True, "message": "Beden tablosu silindi"}
