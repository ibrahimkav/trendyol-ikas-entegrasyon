"""
QA Repository - Müşteri Soru-Cevap kalıcı veri erişim katmanı

SQLite (trendyol_data.db / qa_records tablosu) üzerinde çalışır.
Database kullanılamazsa (ghost mode: db=None) in-memory fallback devreye girer.

w3-customerqa-scope: tüm fonksiyonlar store_id alır ve filtreler/set eder.
QARecord modelinde store_id zaten vardı (nullable=False, default=1,
UniqueConstraint('store_id','qa_id')) — eksik olan bu katmanın onu
KULLANMASIYDI, şema değişikliği gerekmedi.

ÖNEMLİ MİMARİ DÜZELTME (aynı kartta bulundu): bu modül ÖNCEDEN kendi
`SessionLocal()` çağrısıyla (global, gerçek DB'ye bağlı) kendi session'ını
açıyordu — router'ların `Depends(get_db)` ile aldığı, test/ortam bazında
DEĞİŞTİRİLEBİLEN session'ı YOK SAYIYORDU. Sonuç: bu repository'yi çağıran
testler (isolation testleri dahil) geçici test DB'sine değil, YANLIŞLIKLA
GERÇEK trendyol_data.db'ye yazıyordu (canlı doğrulama sırasında yakalandı,
sızan satırlar temizlendi). Artık her fonksiyon çağıranın `db: Session`'ını
parametre olarak alıyor — utils/profitability.py'nin zaten kullandığı
aynı, doğru desen.
"""
from typing import List, Optional, Dict, Any
from datetime import datetime

from sqlalchemy.orm import Session

from database.models import QARecord

# Ghost mode fallback (db=None): store_id -> qa_id -> record.
_memory_store: Dict[int, Dict[str, Dict[str, Any]]] = {}


def _mem(store_id: int) -> Dict[str, Dict[str, Any]]:
    return _memory_store.setdefault(store_id, {})


def _check_db() -> bool:
    """Geriye dönük uyumluluk için tutuldu (router 'storage' alanında kullanıyor) —
    artık gerçek session varlığını DEĞİL, DB modülünün genel olarak yüklenip
    yüklenmediğini gösterir (bilgi amaçlı, davranışı etkilemez)."""
    try:
        from database.db import SessionLocal
        return SessionLocal is not None
    except Exception:
        return False


def _to_dict(rec: QARecord) -> Dict[str, Any]:
    """ORM objesini frontend'in beklediği dict formatına çevirir."""
    fmt = lambda dt: dt.isoformat() if isinstance(dt, datetime) else dt
    return {
        "id": rec.qa_id,
        "question": rec.question,
        "answer": rec.answer or "",
        "customer_id": rec.customer_id,
        "order_id": rec.order_id,
        "status": rec.status,
        "source": rec.source,
        "ai_confidence": rec.ai_confidence,
        "user_feedback": rec.user_feedback,
        "created_at": fmt(rec.created_at),
        "answered_at": fmt(rec.answered_at),
    }


def get_all(db: Optional[Session], store_id: int) -> List[Dict[str, Any]]:
    """Bu mağazanın tüm soru-cevaplarını en yeniden eskiye döndürür."""
    if db is not None:
        rows = (
            db.query(QARecord)
            .filter(QARecord.store_id == store_id)
            .order_by(QARecord.created_at.desc())
            .all()
        )
        return [_to_dict(r) for r in rows]
    return sorted(_mem(store_id).values(), key=lambda x: x.get("created_at", ""), reverse=True)


def get_by_qa_id(db: Optional[Session], store_id: int, qa_id: str) -> Optional[Dict[str, Any]]:
    """Bu mağazada qa_id'ye göre tek kayıt döndürür (başka mağazanın kaydını GÖRMEZ)."""
    if db is not None:
        rec = (
            db.query(QARecord)
            .filter(QARecord.store_id == store_id, QARecord.qa_id == qa_id)
            .first()
        )
        return _to_dict(rec) if rec else None
    return _mem(store_id).get(qa_id)


def upsert(db: Optional[Session], store_id: int, qa_id: str, question: str, answer: str = "",
           customer_id: Optional[str] = None, order_id: Optional[str] = None, status: str = "pending",
           source: str = "manual", created_at: Optional[str] = None,
           answered_at: Optional[str] = None) -> Dict[str, Any]:
    """Bu mağazada kayıt yoksa ekler, varsa soru/cevap alanlarını güncelleyerek döndürür."""
    created_dt = _parse_dt(created_at) or datetime.now()
    answered_dt = _parse_dt(answered_at)

    if db is not None:
        rec = (
            db.query(QARecord)
            .filter(QARecord.store_id == store_id, QARecord.qa_id == qa_id)
            .first()
        )
        if rec is None:
            rec = QARecord(store_id=store_id, qa_id=qa_id, question=question)
            db.add(rec)
        rec.question = question
        rec.answer = answer or ""
        rec.customer_id = customer_id
        rec.order_id = order_id
        rec.status = status
        rec.source = source
        rec.created_at = created_dt
        rec.answered_at = answered_dt
        db.commit()
        return _to_dict(rec)

    d = {
        "id": qa_id, "question": question, "answer": answer or "",
        "customer_id": customer_id, "order_id": order_id, "status": status,
        "source": source, "ai_confidence": None, "user_feedback": None,
        "created_at": created_at or datetime.now().isoformat(), "answered_at": answered_at,
    }
    _mem(store_id)[qa_id] = d
    return d


def create_manual(db: Optional[Session], store_id: int, question: str,
                  customer_id: Optional[str] = None, order_id: Optional[str] = None) -> Dict[str, Any]:
    """Bu mağaza için yeni manuel soru oluşturur."""
    qa_id = f"qa_{datetime.now().timestamp()}"
    return upsert(db, store_id, qa_id, question, "", customer_id, order_id, status="pending", source="manual")


def submit_answer(db: Optional[Session], store_id: int, qa_id: str, answer: str,
                   feedback: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Bu mağazadaki soruya cevap gönderir; öğrenme döngüsü için feedback kaydeder."""
    if db is not None:
        rec = (
            db.query(QARecord)
            .filter(QARecord.store_id == store_id, QARecord.qa_id == qa_id)
            .first()
        )
        if rec is None:
            return None
        rec.answer = answer
        rec.status = "answered"
        rec.answered_at = datetime.now()
        if feedback:
            rec.user_feedback = feedback
        db.commit()
        return _to_dict(rec)

    d = _mem(store_id).get(qa_id)
    if not d:
        return None
    d["answer"] = answer
    d["status"] = "answered"
    d["answered_at"] = datetime.now().isoformat()
    if feedback:
        d["user_feedback"] = feedback
    return d


def set_ai_meta(db: Optional[Session], store_id: int, qa_id: str, confidence: float) -> None:
    """Bu mağazadaki kaydın AI öneri güven skorunu kaydeder."""
    if db is not None:
        rec = (
            db.query(QARecord)
            .filter(QARecord.store_id == store_id, QARecord.qa_id == qa_id)
            .first()
        )
        if rec:
            rec.ai_confidence = confidence
            db.commit()
    elif qa_id in _mem(store_id):
        _mem(store_id)[qa_id]["ai_confidence"] = confidence


def get_answered(db: Optional[Session], store_id: int) -> List[Dict[str, Any]]:
    """Bu mağazanın onaylanmış cevaplara sahip kayıtları (AI öğrenme havuzu)."""
    return [qa for qa in get_all(db, store_id) if qa.get("status") == "answered" and qa.get("answer")]


def get_stats(db: Optional[Session], store_id: int) -> Dict[str, Any]:
    """Bu mağazanın öğrenme istatistikleri."""
    all_qa = get_all(db, store_id)
    answered = [qa for qa in all_qa if qa.get("status") == "answered"]
    feedbacks = [qa.get("user_feedback") for qa in answered if qa.get("user_feedback")]
    confidences = [qa.get("ai_confidence") for qa in all_qa if qa.get("ai_confidence")]
    return {
        "total_count": len(all_qa),
        "answered_count": len(answered),
        "pending_count": len(all_qa) - len(answered),
        "learning_pool_size": len(answered),
        "accepted_count": len([f for f in feedbacks if f == "accepted"]),
        "edited_count": len([f for f in feedbacks if f == "edited"]),
        "rejected_count": len([f for f in feedbacks if f == "rejected"]),
        "avg_confidence": round(sum(confidences) / len(confidences), 2) if confidences else 0.0,
    }


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    """ISO tarih string'ini datetime'a çevirir; başarısızsa None döner."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
