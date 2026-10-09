"""
Size Advisor - Beden Tablosu Danışmanı (yerel AI, API'siz)

Müşteri sorusundaki ölçüleri anlar ("boyum 180, kilom 80"),
ürünün beden tablosuyla karşılaştırır ve uygun bedeni önerir.
"""
import re
import json
from typing import Dict, Any, List, Optional, Tuple

# ---------------- Ölçü anlama ----------------

# Her ölçü tipi için birden fazla ifade kalıbı (Türkçe varyasyonlar)
_MEASURE_PATTERNS: Dict[str, List[str]] = {
    "boy": [
        r"boy(?:um|u|una)?\s*[:=]?\s*(\d{3})",
        r"(\d{3})\s*(?:cm|santim)?\s*boy",
        r"boy\s*[:=]?\s*(\d{2,3})",
    ],
    "kilo": [
        r"kilo(?:m|mu)?\s*[:=]?\s*(\d{2,3})",
        r"(\d{2,3})\s*(?:kg|kilo)",
        r"(\d{2,3})\s*(?:kg|kiloday)\b",
    ],
    "bel": [
        r"bel(?:im|imde)?\s*[:=]?\s*(\d{2,3})",
        r"(\d{2,3})\s*(?:cm)?\s*bel",
    ],
    "gogus": [
        r"g[oö]ğ?g[uü]s(?:[uü]m|[uü]|[uü]de)?\s*[:=]?\s*(\d{2,3})",
        r"gogus(?:um)?\s*[:=]?\s*(\d{2,3})",
        r"(\d{2,3})\s*(?:cm)?\s*g[oö]ğ?g[uü]s",
    ],
    "kalca": [
        r"kal[çc](?:am|as[ıi])?\s*[:=]?\s*(\d{2,3})",
        r"(\d{2,3})\s*(?:cm)?\s*kal[çc]a",
    ],
}

# Geçerli ölçü aralıkları (yanlış eşleşmeleri elemek için)
_VALID_RANGES: Dict[str, Tuple[int, int]] = {
    "boy": (140, 225),
    "kilo": (30, 250),
    "bel": (50, 170),
    "gogus": (60, 170),
    "kalca": (60, 180),
}


def parse_measurements(text: str) -> Dict[str, int]:
    """Soru metninden ölçüleri çıkarır.
    Örnek: "boyum 180 kilom 80" -> {"boy": 180, "kilo": 80}"""
    t = str(text).lower().replace("ı", "i").replace("ğ", "g").replace("ü", "u").replace("ş", "s").replace("ö", "o").replace("ç", "c")
    found: Dict[str, int] = {}
    for measure, patterns in _MEASURE_PATTERNS.items():
        for pat in patterns:
            m = re.search(pat, t)
            if m:
                try:
                    val = int(m.group(1))
                except (ValueError, IndexError):
                    continue
                lo, hi = _VALID_RANGES[measure]
                if lo <= val <= hi:
                    found[measure] = val
                    break
    return found


def has_measurements(text: str) -> bool:
    """Soru bir ölçü sorusu mu? (beden önerisi niyeti)"""
    t = str(text).lower()
    intent_words = ["beden", "size", "hangi beden", "kaç beden", "kac beden",
                    "ölçü", "olcu", "ölçülerim", "olculerim", "uygun", "uyar mı", "uyar mi", "olur mu", "olurmu"]
    has_intent = any(w in t for w in intent_words)
    has_meas = bool(parse_measurements(text))
    return has_meas and (has_intent or len(parse_measurements(text)) >= 1)


# ---------------- Beden tablosu metni ayrıştırma ----------------

_MEASURE_LABELS = {
    "boy": ["boy", "uzunluk", "height"],
    "kilo": ["kilo", "kg", "ağırlık", "agirlik", "weight"],
    "bel": ["bel", "waist"],
    "gogus": ["gogus", "göğüs", "gögs", "gögs", "chest", "gögsüs"],
    "kalca": ["kalca", "kalça", "hip", "basen"],
}

_SIZE_TOKEN = r"(\b(?:XXS|XS|S|M|L|XL|XXL|3XL|XXXL|4XL|XXXXL|2XL)\b|\b\d{2,3}\b)"

_RANGE = r"(\d{2,3})\s*[-–/]\s*(\d{2,3})"
_SINGLE = r"(\d{2,3})"


def _norm_tr(s: str) -> str:
    return (str(s).lower()
            .replace("ı", "i").replace("ğ", "g").replace("ü", "u")
            .replace("ş", "s").replace("ö", "o").replace("ç", "c"))


def _extract_value_pairs(chunk: str, measure: str) -> Optional[Tuple[int, int]]:
    """'bel 71-76' veya 'bel:76' gibi parçadan (min, max) döndürür.
    w3-sizeadvisor-case: `label` zaten _norm_tr() ile normalize ediliyordu ama
    `chunk` (girdi metni) HİÇ normalize edilmiyordu — "bel" deseni "Bel"/"BEL"
    ile hiç eşleşmiyordu (düz re.IGNORECASE de yetmez: "Göğüs" gibi büyük+Türkçe
    harfli girdilerde asıl sorun harf BÜYÜKLÜĞÜ değil aksan farkı, o yüzden
    chunk'ı da AYNI _norm_tr() ile normalize etmek gerekiyor, sadece IGNORECASE
    eklemek değil)."""
    norm_chunk = _norm_tr(chunk)
    labels = [_norm_tr(l) for l in _MEASURE_LABELS[measure]]
    for label in labels:
        # etiket + aralık
        m = re.search(re.escape(label) + r"\s*[:=]?\s*" + _RANGE, norm_chunk)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            return (min(a, b), max(a, b))
        # etiket + tek değer
        m = re.search(re.escape(label) + r"\s*[:=]?\s*" + _SINGLE, norm_chunk)
        if m:
            v = int(m.group(1))
            lo, hi = _VALID_RANGES.get(measure, (0, 999))
            if lo <= v <= hi:
                return (v, v)
    return None


def parse_chart_text(text: str) -> List[Dict[str, Any]]:
    """Yapıştırılan beden tablosu metnini satır listesine çevirir.
    Örnek girdi:
        'S: Bel 71-76, Göğüs 83-88, Boy 165-170, Kilo 50-60
         M: Bel 76-81, Göğüs 88-93, Boy 170-175, Kilo 60-70'
    Her satır bir beden olmalı."""
    rows: List[Dict[str, Any]] = []
    # Satırlara böl (/ veya ; veya yeni satır ayırıcı olabilir)
    lines = re.split(r"[\n;]+", str(text))
    for line in lines:
        line = line.strip()
        if not line:
            continue
        size_match = re.search(_SIZE_TOKEN, line, re.IGNORECASE)
        if not size_match:
            continue
        size = size_match.group(1).upper()
        row: Dict[str, Any] = {"size": size}
        for measure in _MEASURE_LABELS:
            pair = _extract_value_pairs(line, measure)
            if pair:
                row[f"{measure}_min"], row[f"{measure}_max"] = pair
        # En az bir ölçü varsa satırı kabul et
        if len(row) > 1:
            rows.append(row)
    return rows


def validate_sizes(sizes: List[Dict[str, Any]]) -> Tuple[bool, str]:
    """JSON ile gelen beden satırlarını doğrular."""
    if not sizes or not isinstance(sizes, list):
        return False, "sizes boş olamaz"
    for i, row in enumerate(sizes):
        if not row.get("size"):
            return False, f"{i}. satırda 'size' alanı yok"
    return True, "ok"


# ---------------- Beden önerisi ----------------

_MEASURE_WEIGHTS = {"bel": 4, "gogus": 3, "kalca": 3, "kilo": 3, "boy": 2}
_TOLERANCE = 2  # cm/kg toleransı (sınırda ölçüler için)


def _matches_range(value: int, lo: Any, hi: Any, tol: int = 0) -> Optional[float]:
    """Değer aralığa uyuyor mu? -> (1.0 tam, 0.5 tolerans dahili, None uyumsuz)"""
    if lo is None or hi is None:
        return None
    try:
        lo, hi = int(float(lo)), int(float(hi))
    except (ValueError, TypeError):
        return None
    if lo <= value <= hi:
        return 1.0
    if tol and (lo - tol) <= value <= (hi + tol):
        return 0.5
    return None


def recommend_size(sizes: List[Dict[str, Any]], measurements: Dict[str, int]) -> Dict[str, Any]:
    """Ölçülere en uygun bedeni puanlayarak bulur."""
    best_row, best_score = None, 0.0
    details_best: Dict[str, str] = {}

    for row in sizes:
        score = 0.0
        details: Dict[str, str] = {}
        for measure, value in measurements.items():
            match = _matches_range(value, row.get(f"{measure}_min"),
                                   row.get(f"{measure}_max"), tol=_TOLERANCE)
            if match is None:
                continue
            weight = _MEASURE_WEIGHTS.get(measure, 2)
            score += weight * match
            details[measure] = "tam" if match == 1.0 else "sinirda"
        if score > best_score:
            best_score, best_row, details_best = score, row, details

    return {
        "best": best_row,
        "score": best_score,
        "max_possible": sum(_MEASURE_WEIGHTS.get(m, 2) for m in measurements),
        "details": details_best,
        "all_rows": sizes,
    }


_MEASURE_LABEL_TR = {"boy": "Boy", "kilo": "Kilo", "bel": "Bel", "gogus": "Göğüs", "kalca": "Kalça"}


def _fmt_range(row: Dict[str, Any], measure: str) -> Optional[str]:
    lo, hi = row.get(f"{measure}_min"), row.get(f"{measure}_max")
    if lo is None or hi is None:
        return None
    return f"{int(lo)}-{int(hi)}" if lo != hi else f"{int(lo)}"


def generate_size_answer(question: str, chart: Dict[str, Any],
                         measurements: Dict[str, int]) -> Dict[str, Any]:
    """Beden önerisi cevabını üretir (müşteriye gönderilecek metin)."""
    sizes = chart.get("sizes", [])
    rec = recommend_size(sizes, measurements)
    best, score = rec["best"], rec["score"]
    notes = (chart.get("notes") or "").strip()
    product_name = chart.get("product_name") or ""

    meas_text = ", ".join(
        f"{_MEASURE_LABEL_TR[m]}: {v}{' cm' if m != 'kilo' else ' kg'}"
        for m, v in measurements.items()
    )

    if best is None or score <= 0:
        # Tabloda uygun beden yok
        return {
            "suggested_answer": (
                f"Merhaba, verdiğiniz ölçüler ({meas_text}) için bu ürünün beden tablosunda "
                "tam uyumlu bir beden bulunamadı. Beden seçiminde size yardımcı olabilmem için "
                "bel ve göğüs ölçülerinizi cm cinsinden paylaşabilir misiniz?"
            ),
            "confidence": 0.5,
            "reasoning": "Yerel beden danışmanı: ölçüler tablodaki hiçbir bedene uymadı.",
            "answer_source": "size_chart_no_match",
            "category": "beden",
            "measurements": measurements,
            "recommended_size": None,
            "similar_questions": [],
        }

    size_name = best["size"]
    # Önerilen bedenin ölçü özetini oluştur
    size_details = []
    for m in measurements:
        rng = _fmt_range(best, m)
        if rng:
            unit = " kg" if m == "kilo" else " cm"
            size_details.append(f"{_MEASURE_LABEL_TR[m]} {rng}{unit}")
    size_details_text = ", ".join(size_details) if size_details else "tablo değerlerine uygun"

    # Sınırda ölçü varsa üst beden önerisi ekle
    borderline = [m for m, d in rec["details"].items() if d == "sinirda"]
    next_size_text = ""
    if borderline:
        # Bir üst bedeni bul (sıradaki satır)
        idx = next((i for i, r in enumerate(sizes) if r.get("size") == size_name), None)
        if idx is not None and idx + 1 < len(sizes):
            up = sizes[idx + 1]
            next_size_text = (f" Ölçüleriniz sınırda olduğu için dilerseniz daha rahat bir kullanım "
                              f"isteyerek **{up.get('size')}** bedenini de tercih edebilirsiniz.")

    answer = (
        f"Merhaba, ölçülerinize ({meas_text}) göre bu ürün için önerim: "
        f"**{size_name} beden**.\n\n"
        f"{size_name} bedeni {size_details_text} aralığına denk geliyor "
        f"ve ölçülerinizle uyumlu.{next_size_text}"
    )
    if notes:
        answer += f"\n\nEk bilgi: {notes}"
    answer += "\n\nİyi günler dilerim, başka sorunuz olursa yardımcı olmaktan memnuniyet duyarım!"

    # Güven: kaç ölçünün eşleştiğine göre
    confidence = round(min(0.95, 0.6 + (score / max(rec["max_possible"], 1)) * 0.35), 2)

    return {
        "suggested_answer": answer,
        "confidence": confidence,
        "reasoning": (
            f"Yerel beden danışmanı: müşteri ölçüleri ({meas_text}) ürünün beden tablosundaki "
            f"{len(sizes)} bedenle karşılaştırıldı; en yüksek puan {size_name} bedenine ait."
        ),
        "answer_source": "size_chart",
        "category": "beden",
        "measurements": measurements,
        "recommended_size": size_name,
        "recommended_row": best,
        "similar_questions": [],
    }
