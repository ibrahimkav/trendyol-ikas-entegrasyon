"""
QA Learning Engine - Geçmiş cevaplardan öğrenen AI destek motoru

Yaklaşım: RAG (Retrieval-Augmented Generation)
- Onaylanmış geçmiş soru-cevaplar TF-IDF ile vektörleştirilir
- Yeni soru geldiğinde en benzer geçmiş sorular bulunur
- Bu soruların kullanıcı tarafından onaylanmış cevapları
  öneri üretiminde context olarak kullanılır

Bu modül model eğitimi yapmaz ve DIŞ API KULLANMAZ; tamamen yereldir.
Kategori şablonları kullanıcı tarafından düzenlenebilir (qa_templates.json).
"""
import json
import os
from typing import List, Dict, Any, Optional

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    SKLEARN_OK = True
except ImportError:
    SKLEARN_OK = False

# Basit Türkçe stopwords (SKLEARN yoksa fallback için)
_TR_STOPWORDS = {
    "bir", "bu", "ve", "ile", "için", "mi", "mı", "ne", "nedir", "var",
    "yok", "de", "da", "ben", "sen", "o", "biz", "siz", "the", "a", "is",
}

SIMILARITY_THRESHOLD = 0.30  # char_wb benzerliği Türkçe metinde yüksek baseline üretir; eşik 0.30 gürültüyü süzer


class QALearningEngine:
    """Geçmiş Q&A havuzu üzerinden anlamsal benzerlik sağlar."""

    def __init__(self):
        self._entries: List[Dict[str, Any]] = []   # [{"qa": {...}, "text": "..."}]
        self._vectorizer = None
        self._matrix = None
        self._last_pool_size = 0

    # ---------------- Havuz yönetimi ----------------

    def refresh_pool(self, answered_qa: List[Dict[str, Any]]) -> int:
        """Öğrenme havuzunu (onaylanmış cevaplar) yeniden vektörleştirir.
        Havuz değişmemişse çalışmaz (performans)."""
        if len(answered_qa) == self._last_pool_size and self._matrix is not None:
            return len(self._entries)

        self._entries = []
        for qa in answered_qa:
            text = self._normalize(qa.get("question", ""))
            if text:
                self._entries.append({"qa": qa, "text": text})

        self._matrix = None
        self._last_pool_size = len(answered_qa)

        if self._entries and SKLEARN_OK:
            try:
                self._vectorizer = TfidfVectorizer(
                    analyzer="char_wb",          # Türkçe için karakter bazlı en iyi sonuç
                    ngram_range=(2, 4),
                    lowercase=True,
                )
                self._matrix = self._vectorizer.fit_transform(
                    [e["text"] for e in self._entries]
                )
            except Exception:
                self._vectorizer = None
                self._matrix = None

        return len(self._entries)

    # ---------------- Benzerlik ----------------

    def find_similar(self, question: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Soruya en benzer geçmiş Q&A'ları benzerlik skoruna göre döndürür.
        Skor: 0-1 arası. Skoru eşik altında olanlar dahil edilmez."""
        q_text = self._normalize(question)
        if not q_text or not self._entries:
            return []

        if self._vectorizer is not None and self._matrix is not None:
            try:
                q_vec = self._vectorizer.transform([q_text])
                sims = cosine_similarity(q_vec, self._matrix)[0]
                scored = sorted(
                    zip(sims, self._entries), key=lambda x: x[0], reverse=True
                )
                return [
                    {
                        "question": e["qa"].get("question", ""),
                        "answer": e["qa"].get("answer", ""),
                        "similarity": round(float(score), 3),
                        "user_feedback": e["qa"].get("user_feedback"),
                    }
                    for score, e in scored[:top_k]
                    if score >= SIMILARITY_THRESHOLD
                ]
            except Exception:
                pass  # fallback'e düş

        # Fallback: kelime bazlı skorlama (sklearn yoksa)
        return self._keyword_fallback(q_text, top_k)

    def _keyword_fallback(self, q_text: str, top_k: int) -> List[Dict[str, Any]]:
        q_words = set(q_text.split())
        results = []
        for e in self._entries:
            e_words = set(e["text"].split())
            if not e_words:
                continue
            overlap = len(q_words & e_words) / max(len(q_words), 1)
            if overlap >= SIMILARITY_THRESHOLD:
                results.append({
                    "question": e["qa"].get("question", ""),
                    "answer": e["qa"].get("answer", ""),
                    "similarity": round(overlap, 3),
                    "similarity_method": "keyword",
                })
        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:top_k]

    # ---------------- Context üretimi ----------------

    def build_context(self, question: str, max_examples: int = 5) -> tuple:
        """Groq prompt'u için context metni ve benzer soru listesi üretir.
        Returns: (context_text, similar_list)"""
        similar = self.find_similar(question, top_k=max_examples)
        if not similar:
            return "", []

        lines = []
        for i, s in enumerate(similar, 1):
            lines.append(f"Örnek {i}:")
            lines.append(f"Benzer soru: {s['question']}")
            lines.append(f"Verilen cevap: {s['answer']}")
            lines.append(f"Benzerlik: %{int(s['similarity'] * 100)}")
            lines.append("")
        return "\n".join(lines), similar

    @staticmethod
    def _normalize(text: str) -> str:
        """Metni normalize eder (küçük harf + çoklu boşluk temizliği)."""
        return " ".join(str(text).lower().split())


# ================= YEREL CEVAP ÜRETİCİ (API'siz AI) =================
# Dış API çağrısı YOK. Tamamen öğrenme havuzu + kural tabanlı şablonlar.

CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    "kargo": ["kargo", "teslimat", "ne zaman gelir", "kaç günde", "kac gunde",
              "gönderi", "gonderi", "takip", "kargom", "ulaşır", "ulasir",
              "adres", "kurye", "gönderildi", "gonderildi"],
    "iade": ["iade", "geri gönder", "geri gonder", "iptal", "değişim",
             "degisim", "değiştir", "degistir", "beğenmedim", "begenmedim",
             "kusurlu", "hasarlı", "hasarli", "yanlış ürün", "yanlis urun"],
    "ödeme": ["ödeme", "odeme", "taksit", "kapıda", "kapida", "kart",
              "havale", "eft", "para iadesi", "geri ödeme", "geri odeme",
              "refund", "ücret", "ucret", "fiyat", "komisyon"],
    "ürün": ["ürün", "urun", "beden", "renk", "stok", "malzeme", "garanti",
             "orijinal", "orijinallik", "model", "ölçü", "olcu", "boyut",
             "uyumlu mu"],
    "kampanya": ["indirim", "kampanya", "kupon", "hediye", "sepet",
                 "fırsat", "firsat"],
}

DEFAULT_CATEGORY_TEMPLATES: Dict[str, str] = {
    "kargo": ("Merhaba, kargo süresiyle ilgili bilgilendirme yapayım: "
              "Siparişleriniz onaylandıktan sonra 1-3 iş günü içinde kargoya teslim edilir "
              "ve kargo takip numarası SMS ile iletilir. Başka bir konuda yardımcı olabilir miyim?"),
    "iade": ("Merhaba, iade talebinizle ilgili yardımcı olayım: "
             "Ürünü teslim aldıktan sonra 14 gün içinde koşulsuz iade edebilirsiniz. "
             "İade sürecini başlatmak için siparişinizin detay sayfasını kullanabilirsiniz. "
             "Anlayışınız için teşekkür ederim."),
    "ödeme": ("Merhaba, ödeme ile ilgili bilgilendirme: "
              "Tüm kredi/banka kartları ve Trendyol Cüzdan ile ödeme yapabilirsiniz. "
              "Ödeme ve ücretlendirme konusunda ek sorunuz olursa yardımcı olmaktan memnuniyet duyarım."),
    "ürün": ("Merhaba, ürünle ilgili sorunuz için teşekkürler: "
             "Ürün sayfasındaki açıklama ve ölçüler detaylıdır; stok durumunu ürün sayfasından "
             "görebilirsiniz. Size en doğru bilgiyi vermek için ek detay paylaşabilir misiniz?"),
    "kampanya": ("Merhaba, kampanyalarımızla ilgili bilgi: "
                 "Güncel indirim ve kuponları Trendyol uygulamasındaki 'Kampanyalar' sekmesinden "
                 "takip edebilirsiniz. İyi alışverişler dilerim!"),
}

GENERIC_TEMPLATE = ("Merhaba, sorunuz için teşekkür ederim. "
                    "Talebinizi inceleyip en kısa sürede detaylı bilgi vereceğim. "
                    "Yardımcı olabileceğim başka bir konu varsa bilmekten memnuniyet duyarım.")

TEMPLATES_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "qa_templates.json")


def load_category_templates() -> Dict[str, str]:
    """Kategori şablonlarını dosyadan yükler; yoksa varsayılanları kullanır."""
    path = os.path.abspath(TEMPLATES_FILE)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                merged = dict(DEFAULT_CATEGORY_TEMPLATES)
                merged.update({k: str(v) for k, v in data.items() if k in DEFAULT_CATEGORY_TEMPLATES})
                return merged
        except Exception:
            pass
    return dict(DEFAULT_CATEGORY_TEMPLATES)


def save_category_templates(templates: Dict[str, str]) -> Dict[str, str]:
    """Kategori şablonlarını dosyaya kaydeder ve bellekteki havuzu günceller."""
    global CATEGORY_TEMPLATES
    to_save = {
        cat: str(templates.get(cat, DEFAULT_CATEGORY_TEMPLATES[cat])).strip()
        for cat in DEFAULT_CATEGORY_TEMPLATES
    }
    path = os.path.abspath(TEMPLATES_FILE)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(to_save, f, ensure_ascii=False, indent=2)
    CATEGORY_TEMPLATES = to_save
    return CATEGORY_TEMPLATES


CATEGORY_TEMPLATES: Dict[str, str] = load_category_templates()


def detect_category(question: str) -> Optional[str]:
    """Soruyu kategorize eder (yerel kural tabanlı)."""
    q = str(question).lower()
    best_cat, best_hits = None, 0
    for cat, keywords in CATEGORY_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw in q)
        if hits > best_hits:
            best_cat, best_hits = cat, hits
    return best_cat


def generate_local_answer(question: str, similar: List[Dict[str, Any]]) -> Dict[str, Any]:
    """YEREL AI cevabı üretir — dış API YOK.

    Öğrenme kademeleri:
    1. Güçlü benzerlik (>= 0.55): onaylı geçmiş cevap aynen önerilir
    2. Orta benzerlik (>= 0.30): onaylı cevap + kategori şablonu ile tamamlama
    3. Benzerlik yok: kategori şablonu veya genel şablon
    """
    category = detect_category(question)

    if similar:
        best = similar[0]
        sim = best.get("similarity", 0.0)
        learned = best.get("answer", "").strip()

        if sim >= 0.55 and learned:
            # 1) Güçlü eşleşme: öğrenilmiş cevabı öner
            return {
                "suggested_answer": learned,
                "confidence": round(min(0.95, 0.65 + sim * 0.3), 2),
                "reasoning": (
                    f"Yerel öğrenme motoru: geçmişte %{int(sim * 100)} benzer soruya "
                    f"verdiğiniz cevaptan öğrendi (kaynak: onaylı cevap havuzu)."
                ),
                "answer_source": "learned",
                "category": category,
                "similar_questions": similar[:3],
            }
        elif sim >= 0.30 and learned:
            # 2) Orta eşleşme: öğrenilmiş cevap + kategori şablonu
            template = CATEGORY_TEMPLATES.get(category, GENERIC_TEMPLATE)
            merged = f"{learned}\n\n{template}" if category else learned
            return {
                "suggested_answer": merged,
                "confidence": round(min(0.85, 0.45 + sim * 0.3), 2),
                "reasoning": (
                    f"Yerel öğrenme motoru: %{int(sim * 100)} benzer geçmiş cevap "
                    f"{'kategori şablonu ile desteklendi' if category else 'kullanıldı'}."
                ),
                "answer_source": "learned+template",
                "category": category,
                "similar_questions": similar[:3],
            }

    # 3) Benzerlik yok: kategori şablonu veya genel cevap
    if category:
        return {
            "suggested_answer": CATEGORY_TEMPLATES[category],
            "confidence": 0.55,
            "reasoning": f"Yerel öğrenme motoru: '{category}' kategorisi tespit edildi, hazır şablon önerildi. Havuzda benzer onaylı cevap yok.",
            "answer_source": "template",
            "category": category,
            "similar_questions": [],
        }
    return {
        "suggested_answer": GENERIC_TEMPLATE,
        "confidence": 0.4,
        "reasoning": "Yerel öğrenme motoru: havuzda benzer onaylı cevap yok, genel şablon önerildi.",
        "answer_source": "generic",
        "category": None,
        "similar_questions": [],
    }
