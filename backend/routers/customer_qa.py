"""
Müşteri Soru-Cevap Router
AI destekli müşteri soru-cevap yönetimi
- Kalıcı depolama: SQLite (qa_records tablosu, database/qa_repository.py)
- AI öğrenme: RAG + TF-IDF benzerlik (utils/qa_learning.py)
- Feedback döngüsü: Kabul / Düzenle / Reddet -> öğrenme havuzu
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
import requests

from database import qa_repository as qa_repo
from utils.qa_learning import QALearningEngine, generate_local_answer

router = APIRouter()

# Database modülünü optional olarak yükle (ghost mode)
try:
    from database.db import get_db
    from database.models import Store
    from security import get_current_store
    from utils.store_trendyol import resolve_trendyol_creds, try_resolve_trendyol_creds, _auth_headers, _integration_base
    _db_available = True
except Exception:
    _db_available = False
    def get_db():
        raise HTTPException(status_code=503, detail="Database not available (ghost mode)")

    def get_current_store():
        raise HTTPException(status_code=503, detail="Database not available (ghost mode)")

# w3-customerqa-scope: öğrenme motoru artık store_id ile anahtarlı (önceden TEK
# global motordu — bir mağazanın onaylı cevaplarından öğrenilen vektörler başka
# mağazanın AI önerilerine karışıyordu, qa_records'un kendisi kadar ciddi bir
# çapraz-kiracı sızıntısıydı çünkü depolamadan bağımsız, TÜRETİLMİŞ bir önbellekti).
_learning_engines: Dict[int, QALearningEngine] = {}


def _sid(store) -> int:
    """Ghost mode'da (DB yok) store None olur — tüm ghost istekleri tek (0)
    alanı paylaşır, izolasyonun zaten anlamsız olduğu tek senaryo."""
    return store.id if store else 0


def _get_learning_engine(store_id: int) -> QALearningEngine:
    return _learning_engines.setdefault(store_id, QALearningEngine())


def _sync_learning_pool(db, store_id: int) -> int:
    """Bu mağazanın onaylanmış cevap havuzunu öğrenme motoruna yükle (değişmişse)."""
    answered = qa_repo.get_answered(db, store_id)
    return _get_learning_engine(store_id).refresh_pool(answered)


class QARequest(BaseModel):
    question: str
    customer_id: Optional[str] = None
    order_id: Optional[str] = None


class AnswerRequest(BaseModel):
    answer: str


class AISuggestRequest(BaseModel):
    question: str
    qa_id: str
    product_code: Optional[str] = None  # Beden önerisi için ürün kodu (opsiyonel)


class FeedbackRequest(BaseModel):
    """AI önerisi feedback'i (öğrenme döngüsü)"""
    feedback: str  # accepted / edited / rejected
    final_answer: Optional[str] = None  # edited durumunda satıcının düzenlediği cevap


class TemplatesUpdateRequest(BaseModel):
    """Kategori cevap şablonları güncelleme"""
    templates: Dict[str, str]


def get_trendyol_questions(db, creds=None, store_id: int = 0) -> List[Dict[str, Any]]:
    """
    Bu mağazanın Trendyol müşteri sorularını çeker (Wave3 kalıbı: per-store, env DEĞİL).
    w3-hardening (2026-09-26): eski kod 6 TAHMİNİ path deniyordu (hiçbiri resmi doküman
    adıyla eşleşmiyordu) ve ölü eski gateway'i (api.trendyol.com/sapigw) kullanıyordu —
    muhtemelen ilk günden beri hep boş dönüyordu. Gerçek resmi uca taşındı:
    developers.trendyol.com/v2.0/docs/getting-customer-questions →
    GET /integration/qna/sellers/{sellerId}/questions/filter?status=WAITING_FOR_ANSWER
    (2026-09-26'da gerçek çağrıyla doğrulandı: 200, totalElements alanı var).
    NOT: creds=None → [] (henüz dönüştürülmemiş çağıranlar için güvenli köprü)."""
    if creds is None:
        return []
    try:
        url = f"{_integration_base()}/qna/sellers/{creds.supplier_id}/questions/filter"
        headers = _auth_headers(creds)
        response = requests.get(url, headers=headers, params={"status": "WAITING_FOR_ANSWER"}, timeout=30)

        if response.status_code != 200:
            print(f"[Trendyol Questions API] status={response.status_code}: {response.text[:200]}")
            return []

        data = response.json()
        questions = data.get("content", [])
        if not questions:
            return []

        formatted_questions = []
        for q in questions:
            question_id = q.get("id") or q.get("questionId") or q.get("supplierQuestionId") or f"trendyol_{q.get('orderNumber', '')}_{datetime.now().timestamp()}"

            # Eğer bu soru zaten (bu mağazada) veritabanında yoksa ekle
            existing = qa_repo.get_by_qa_id(db, store_id, str(question_id)) is not None
            if not existing:
                formatted_questions.append({
                    "id": question_id,
                    "question": q.get("question") or q.get("questionText") or q.get("message") or q.get("text", ""),
                    "answer": q.get("answer") or q.get("answerText") or "",
                    "customer_id": q.get("customerId") or q.get("customer_id") or "",
                    "order_id": q.get("orderNumber") or q.get("order_id") or q.get("orderNumber", ""),
                    "status": "answered" if (q.get("answer") or q.get("answerText")) else "pending",
                    "created_at": q.get("creationDate") or q.get("createdDate") or q.get("created_at") or datetime.now().isoformat(),
                    "answered_at": q.get("answeredDate") or q.get("answered_at") or None,
                    "source": "trendyol"
                })

        return formatted_questions
    except Exception as e:
        print(f"[Trendyol Questions API] Exception: {str(e)}")
        return []


@router.get("/")
async def get_qa_history(
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Session = Depends(get_db) if _db_available else None
):
    """
    Tüm soru-cevap geçmişini döner. w3-hardening: Trendyol tarafı per-store credential.
    w3-customerqa-scope: kalıcı depolama artık store_id ile filtreleniyor.
    """
    store_id = _sid(store)
    creds = resolve_trendyol_creds(db, store) if (_db_available and store) else None
    # Trendyol API'den soruları çek
    trendyol_questions = get_trendyol_questions(db, creds, store_id)

    # Yeni soruları kalıcı veritabanına ekle (duplicate kontrolü repository içinde)
    for q in trendyol_questions:
        qa_repo.upsert(
            db,
            store_id,
            qa_id=str(q.get("id")),
            question=q.get("question", ""),
            answer=q.get("answer", ""),
            customer_id=q.get("customer_id"),
            order_id=q.get("order_id"),
            status=q.get("status", "pending"),
            source="trendyol",
            created_at=q.get("created_at"),
            answered_at=q.get("answered_at"),
        )

    # Öğrenme havuzunu güncelle (yeni onaylı cevap varsa vektörler tazelenir)
    _sync_learning_pool(db, store_id)

    sorted_qa = qa_repo.get_all(db, store_id)

    return {
        "qa_list": sorted_qa,
        "total_count": len(sorted_qa),
        "pending_count": len([qa for qa in sorted_qa if qa.get("status") == "pending"]),
        "trendyol_synced": len(trendyol_questions),
        "learning_pool_size": len([qa for qa in sorted_qa if qa.get("status") == "answered"]),
        "storage": "sqlite" if qa_repo._check_db() else "memory"
    }


@router.post("/")
async def create_question(
    qa_request: QARequest,
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Session = Depends(get_db) if _db_available else None,
):
    """
    Yeni bir soru oluşturur.
    """
    qa = qa_repo.create_manual(
        db,
        _sid(store),
        question=qa_request.question,
        customer_id=qa_request.customer_id,
        order_id=qa_request.order_id,
    )

    return {
        "success": True,
        "qa_id": qa["id"],
        "message": "Soru başarıyla eklendi"
    }


@router.post("/ai-suggest")
async def get_ai_suggestion(
    request: AISuggestRequest,
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Session = Depends(get_db) if _db_available else None,
):
    """
    AI destekli cevap önerisi döner.
    TAMAMEN YEREL: dış API çağrısı yok. Geçmiş onaylanmış soru-cevaplardan
    öğrenir (RAG + TF-IDF benzerlik) ve kategori şablonlarıyla tamamlar.
    """
    store_id = _sid(store)
    try:
        # Öğrenme havuzunu tazele (değişmişse)
        _sync_learning_pool(db, store_id)

        # 1) ÖNCE beden/ölçü sorusu mu kontrol et (boy/kilo/bel/göğüs/kalça)
        size_result = _try_size_advice(db, store_id, request.question, request.product_code, request.qa_id)
        if size_result is not None:
            return size_result

        # 2) Değilse benzerlik analizi: havuzdan en benzer onaylı cevaplar
        similar_questions = _get_learning_engine(store_id).find_similar(request.question, top_k=5)

        # Yerel AI ile cevap üret
        suggestion = generate_local_answer(request.question, similar_questions)

        # Güven skorunu kayda işle (öğrenme istatistikleri için)
        qa_repo.set_ai_meta(db, store_id, request.qa_id, suggestion.get("confidence", 0.5))

        return suggestion
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"AI önerisi alınamadı: {str(e)}"
        )


def _try_size_advice(db, store_id: int, question: str, product_code: Optional[str], qa_id: str) -> Optional[Dict[str, Any]]:
    """Soru ölçü içeriyorsa beden tablosuna göre öneri üretir.
    Tablo yoksa None döner (normal akış devam eder).
    NOT (w3-sizechart-guard kapsamı DIŞI, ayrıca bilinen/raporlanmış): bu fonksiyonun
    çağırdığı _find_product_code_by_order HÂLÂ store_id'siz sorguluyor (OrderLine) —
    w3-hardening-verify'da flag edilmişti, o AYRI bir tablo/karar, bu karta dahil
    değildi (SADECE SizeChart erişim noktaları kapsandı)."""
    from utils.size_advisor import parse_measurements, generate_size_answer

    measurements = parse_measurements(question)
    if not measurements:
        return None

    # Ürün kodunu bul: önce istekten, yoksa sorunun bağlı olduğu siparişten
    code = product_code
    if not code and qa_id:
        qa = qa_repo.get_by_qa_id(db, store_id, qa_id)
        order_id = qa.get("order_id") if qa else None
        if order_id:
            code = _find_product_code_by_order(str(order_id))

    if not code:
        return None

    chart = _get_size_chart(db, store_id, code)
    if not chart:
        return None

    suggestion = generate_size_answer(question, chart, measurements)
    qa_repo.set_ai_meta(db, store_id, qa_id, suggestion.get("confidence", 0.5))
    return suggestion


def _find_product_code_by_order(order_id: str) -> Optional[str]:
    """Sipariş numarasından ilk ürünün kodunu bulur."""
    try:
        from database.db import SessionLocal
        from database.models import OrderLine
        if SessionLocal is None:
            return None
        s: SessionLocal = SessionLocal()
        try:
            line = s.query(OrderLine).filter(OrderLine.order_id == order_id).first()
            return line.product_id if line else None
        finally:
            s.close()
    except Exception:
        return None


def _get_size_chart(db, store_id: int, product_code: str) -> Optional[Dict[str, Any]]:
    """Bu mağazanın ürününe ait beden tablosunu getirir (w3-sizechart-guard:
    artık store_id filtreli + çağıranın db session'ını kullanıyor, kendi
    SessionLocal()'ını AÇMIYOR)."""
    if db is None:
        return None
    try:
        from database.models import SizeChart
        import json as _json
        rec = (
            db.query(SizeChart)
            .filter(SizeChart.store_id == store_id, SizeChart.product_code == product_code)
            .first()
        )
        if not rec:
            return None
        return {
            "product_code": rec.product_code,
            "product_name": rec.product_name,
            "notes": rec.notes,
            "sizes": _json.loads(rec.sizes_json) if rec.sizes_json else [],
        }
    except Exception:
        return None


@router.post("/{qa_id}/answer")
async def submit_answer(
    qa_id: str,
    answer_request: AnswerRequest,
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Session = Depends(get_db) if _db_available else None,
):
    """
    Bir soruya cevap gönderir.
    Cevap öğrenme havuzuna eklenir (AI bundan sonra öğrenir).
    """
    store_id = _sid(store)
    if qa_repo.get_by_qa_id(db, store_id, qa_id) is None:
        raise HTTPException(status_code=404, detail="Soru bulunamadı")

    qa = qa_repo.submit_answer(db, store_id, qa_id, answer_request.answer)
    if not qa:
        raise HTTPException(status_code=404, detail="Soru bulunamadı")

    if qa.get("status") == "answered" and qa.get("user_feedback") is None:
        # Manuel cevap = satıcı tarafından yazılmış kabul edilir
        qa_repo.submit_answer(db, store_id, qa_id, answer_request.answer, feedback="edited")
        qa = qa_repo.get_by_qa_id(db, store_id, qa_id)

    # Öğrenme havuzunu hemen tazele (yeni cevap anında öğrenilsin)
    _sync_learning_pool(db, store_id)

    return {
        "success": True,
        "message": "Cevap gönderildi ve AI öğrenme havuzuna eklendi",
        "qa": qa
    }


@router.post("/{qa_id}/feedback")
async def submit_feedback(
    qa_id: str,
    feedback_request: FeedbackRequest,
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Session = Depends(get_db) if _db_available else None,
):
    """
    AI önerisi için feedback kaydeder (öğrenme döngüsünün kalbi).
    - accepted: AI önerisi olduğu gibi kullanıldı -> havuza eklenir
    - edited: Satıcı düzenledi -> düzenlenen cevap havuza eklenir
    - rejected: Öneri reddedildi -> havuza eklenmez, olumsuz sinyal kaydedilir
    """
    store_id = _sid(store)
    qa = qa_repo.get_by_qa_id(db, store_id, qa_id)
    if not qa:
        raise HTTPException(status_code=404, detail="Soru bulunamadı")

    if feedback_request.feedback not in ("accepted", "edited", "rejected"):
        raise HTTPException(status_code=400, detail="feedback accepted/edited/rejected olmalı")

    if feedback_request.feedback == "rejected":
        # Olumsuz feedback: cevap havuza eklenmez
        qa_repo.submit_answer(db, store_id, qa_id, qa.get("answer", ""), feedback="rejected")
        _sync_learning_pool(db, store_id)
        return {
            "success": True,
            "message": "Öneri reddedildi, AI öğrenme havuzuna eklenmedi",
            "qa": qa_repo.get_by_qa_id(db, store_id, qa_id)
        }

    # accepted/edited: cevabı feedback ile kaydet -> havuza girer
    answer = feedback_request.final_answer if feedback_request.final_answer else qa.get("answer", "")
    qa_repo.submit_answer(db, store_id, qa_id, answer, feedback=feedback_request.feedback)
    _sync_learning_pool(db, store_id)

    return {
        "success": True,
        "message": f"Cevap öğrenme havuzuna eklendi (feedback: {feedback_request.feedback})",
        "qa": qa_repo.get_by_qa_id(db, store_id, qa_id),
        "learning_pool_size": len(qa_repo.get_answered(db, store_id))
    }


@router.get("/stats/learning")
async def get_learning_stats(
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Session = Depends(get_db) if _db_available else None,
):
    """
    Bu mağazanın AI öğrenme istatistikleri.
    """
    stats = qa_repo.get_stats(db, _sid(store))
    feedbacks_total = stats["accepted_count"] + stats["edited_count"] + stats["rejected_count"]
    stats["acceptance_rate"] = (
        round((stats["accepted_count"] + stats["edited_count"]) / feedbacks_total * 100, 1)
        if feedbacks_total else 0.0
    )
    stats["storage"] = "sqlite" if qa_repo._check_db() else "memory"
    return stats


@router.get("/templates")
async def get_answer_templates():
    """Kategori cevap şablonlarını döner (düzenlenebilir)."""
    from utils.qa_learning import (
        CATEGORY_TEMPLATES, DEFAULT_CATEGORY_TEMPLATES, CATEGORY_KEYWORDS, GENERIC_TEMPLATE,
    )
    return {
        "templates": CATEGORY_TEMPLATES,
        "defaults": DEFAULT_CATEGORY_TEMPLATES,
        "generic_template": GENERIC_TEMPLATE,
        "categories": list(CATEGORY_KEYWORDS.keys()),
    }


@router.put("/templates")
async def update_answer_templates(request: TemplatesUpdateRequest):
    """Kategori cevap şablonlarını günceller."""
    from utils.qa_learning import save_category_templates, CATEGORY_KEYWORDS
    valid = set(CATEGORY_KEYWORDS.keys())
    filtered = {
        k: v.strip() for k, v in request.templates.items()
        if k in valid and v and v.strip()
    }
    if not filtered:
        raise HTTPException(status_code=400, detail="En az bir geçerli şablon gerekli")
    updated = save_category_templates(filtered)
    return {"success": True, "templates": updated, "message": "Şablonlar kaydedildi"}


@router.get("/{qa_id}")
async def get_qa_detail(
    qa_id: str,
    store: Store = Depends(get_current_store) if _db_available else None,
    db: Session = Depends(get_db) if _db_available else None,
):
    """
    Belirli bir soru-cevabın (bu mağazadaki) detayını döner.
    """
    qa = qa_repo.get_by_qa_id(db, _sid(store), qa_id)
    if qa:
        return qa

    raise HTTPException(status_code=404, detail="Soru bulunamadı")

