"""
ikas sipariş dışa aktarma dosyası (Excel/CSV) → fatura taslağı.

ikas Start paketinde API erişimi olmadığı için siparişler ikas panelinden
(Siparişler → Dışa Aktar) indirilen dosyayla gelir. Dosyanın kolon adları
ikas'ın diline/sürümüne göre değişebileceğinden kolonlar SABİT isimle değil,
normalize edilmiş takma ad (alias) listeleriyle eşleştirilir. Tanınmayan
kolonlar yükleme sonucunda raporlanır — gerçek bir ikas dosyası geldiğinde
eksik takma adlar FIELD_ALIASES'e eklenir.

Dosya hem "satır başına bir ürün" (sipariş bilgileri her satırda tekrarlanır)
hem "satır başına bir sipariş" biçimini destekler: satırlar sipariş numarasına
göre gruplanır, sipariş seviyesi alanlar ilk dolu değerden alınır.

Tutarların KDV DAHİL olduğu varsayılır (ikas'ta satış fiyatları KDV dahildir).
"""
from __future__ import annotations

import csv
import io
import re
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

# ---------------------------------------------------------------------------
# Kolon eşleştirme
# ---------------------------------------------------------------------------

_TR_FOLD = str.maketrans({
    "İ": "i", "I": "i", "ı": "i", "Ş": "s", "ş": "s", "Ğ": "g", "ğ": "g",
    "Ü": "u", "ü": "u", "Ö": "o", "ö": "o", "Ç": "c", "ç": "c",
})


def normalize_header(name: Any) -> str:
    """'Sipariş No.' → 'siparis no', 'E-Posta' → 'e posta' (Türkçe harf katlamalı)."""
    text = str(name or "").translate(_TR_FOLD).lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return text.strip()


# Kanonik alan → takma adlar (normalize edilmiş biçimde yazılır).
FIELD_ALIASES: Dict[str, List[str]] = {
    # Sipariş
    "order_number": ["siparis no", "siparis numarasi", "siparis kodu", "siparis id", "order number",
                     "order no", "order id", "order"],
    "order_date": ["siparis tarihi", "tarih", "olusturulma tarihi", "order date", "created at", "date"],
    "order_status": ["siparis durumu", "durum", "order status", "status"],
    "payment_method": ["odeme yontemi", "odeme tipi", "odeme sekli", "payment method"],
    "currency": ["para birimi", "currency"],
    "order_total": ["siparis toplami", "siparis tutari", "genel toplam", "toplam tutar", "odenen tutar",
                    "order total", "grand total", "total price", "total"],
    "shipping_fee": ["kargo ucreti", "kargo bedeli", "kargo tutari", "teslimat ucreti", "kargo",
                     "shipping", "shipping price", "shipping fee", "shipping total"],
    "discount": ["indirim", "indirim tutari", "toplam indirim", "kupon indirimi", "discount",
                 "discount total", "total discount"],
    # Müşteri / fatura
    "first_name": ["ad", "adi", "fatura adi", "musteri adi", "billing first name", "first name",
                   "customer first name"],
    "last_name": ["soyad", "soyadi", "fatura soyadi", "musteri soyadi", "billing last name", "last name",
                  "customer last name"],
    "full_name": ["ad soyad", "adi soyadi", "musteri", "musteri ad soyad", "musteri adi soyadi",
                  "fatura ad soyad", "fatura adi soyadi", "alici", "alici adi", "customer", "customer name",
                  "billing name", "name"],
    "email": ["e posta", "eposta", "email", "e mail", "musteri e posta", "musteri email", "customer email"],
    "phone": ["telefon", "telefon numarasi", "cep telefonu", "gsm", "musteri telefon", "musteri telefonu",
              "fatura telefon", "fatura telefonu", "phone", "billing phone", "customer phone"],
    "identity_number": ["tc kimlik no", "tc kimlik numarasi", "tc kimlik", "tckn", "tc no", "tc",
                        "fatura tc kimlik no", "kimlik no", "identity number"],
    "tax_number": ["vergi no", "vergi numarasi", "vkn", "vergi kimlik no", "vergi kimlik numarasi",
                   "fatura vergi no", "fatura vergi numarasi", "tax number", "tax id"],
    "tax_office": ["vergi dairesi", "fatura vergi dairesi", "tax office"],
    "company_name": ["firma adi", "sirket adi", "firma", "sirket", "unvan", "fatura firma adi",
                     "fatura unvani", "company", "company name", "billing company"],
    "address": ["fatura adresi", "fatura adres", "fatura adresi 1", "adres", "adres satiri 1",
                "billing address", "billing address 1", "address", "address line 1"],
    "address2": ["fatura adresi 2", "adres satiri 2", "billing address 2", "address line 2"],
    "district": ["fatura ilce", "fatura ilcesi", "ilce", "billing district", "district"],
    "city": ["fatura il", "fatura sehir", "fatura sehri", "il", "sehir", "billing city", "city", "province"],
    "postal_code": ["fatura posta kodu", "posta kodu", "billing zip", "postal code", "zip"],
    "country": ["fatura ulke", "ulke", "billing country", "country"],
    # Teslimat adresi (fatura adresi yoksa yedek)
    "shipping_address": ["teslimat adresi", "kargo adresi", "gonderim adresi", "shipping address",
                         "shipping address 1"],
    "shipping_district": ["teslimat ilce", "teslimat ilcesi", "kargo ilce", "shipping district"],
    "shipping_city": ["teslimat il", "teslimat sehir", "kargo il", "kargo sehir", "shipping city"],
    # Ürün satırı
    "product_name": ["urun adi", "urun", "urun ismi", "urun basligi", "product name", "product",
                     "item name", "title"],
    "variant": ["varyant", "varyant adi", "secenek", "variant", "variant name"],
    "sku": ["sku", "stok kodu", "urun kodu"],
    "barcode": ["barkod", "barcode"],
    "quantity": ["adet", "miktar", "quantity", "qty"],
    "unit_price": ["birim fiyat", "birim fiyati", "urun fiyati", "fiyat", "satis fiyati", "unit price",
                   "price"],
    "line_total": ["urun toplam", "urun toplami", "urun toplam fiyat", "satir toplami", "toplam fiyat",
                   "line total", "item total"],
    "line_discount": ["urun indirimi", "satir indirimi", "line discount", "item discount"],
    "line_vat_rate": ["kdv orani", "vergi orani", "kdv", "kdv yuzdesi", "tax rate", "vat rate"],
}

ORDER_FIELDS = {
    "order_date", "order_status", "payment_method", "currency", "order_total", "shipping_fee", "discount",
    "first_name", "last_name", "full_name", "email", "phone", "identity_number", "tax_number",
    "tax_office", "company_name", "address", "address2", "district", "city", "postal_code", "country",
    "shipping_address", "shipping_district", "shipping_city",
}
LINE_FIELDS = {"product_name", "variant", "sku", "barcode", "quantity", "unit_price", "line_total",
               "line_discount", "line_vat_rate"}

# Bu alanlar bulunamazsa içe aktarma anlamsız / fatura kesilemez
REQUIRED_FIELDS = ["order_number", "product_name"]

_ALIAS_LOOKUP: Dict[str, str] = {}
for _field, _aliases in FIELD_ALIASES.items():
    for _alias in _aliases:
        _ALIAS_LOOKUP.setdefault(_alias, _field)


def match_columns(columns: List[Any]) -> Tuple[Dict[str, str], List[str]]:
    """Dosya kolonlarını kanonik alanlara eşler. Döner: ({alan: kolon}, [tanınmayan kolonlar]).
    Aynı alana birden çok kolon eşleşirse İLKİ kullanılır, diğerleri tanınmayan sayılır."""
    mapping: Dict[str, str] = {}
    ignored: List[str] = []
    for col in columns:
        field = _ALIAS_LOOKUP.get(normalize_header(col))
        if field and field not in mapping:
            mapping[field] = col
        else:
            ignored.append(str(col))
    # "Müşteri Adı" tek başına (soyad kolonu yoksa) tam addır
    if "first_name" in mapping and "last_name" not in mapping and "full_name" not in mapping:
        mapping["full_name"] = mapping.pop("first_name")
    return mapping, ignored


# ---------------------------------------------------------------------------
# Değer temizleme
# ---------------------------------------------------------------------------

def clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    text = str(value).strip()
    return "" if text.lower() in ("nan", "none", "null") else text


def clean_id(value: Any) -> str:
    """TC/VKN/telefon/sipariş no: Excel'in sayıya çevirdiği '12345678901.0' → '12345678901'."""
    text = clean_text(value)
    if re.fullmatch(r"\d+\.0+", text):
        text = text.split(".")[0]
    return text


def parse_amount(value: Any) -> Optional[float]:
    """'1.234,56 ₺' / '1234.56' / '1,234.56' / 1234.5 / '%10' → float. Boşsa None."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return None if pd.isna(value) else float(value)
    text = clean_text(value)
    if not text:
        return None
    text = re.sub(r"[^\d,.\-]", "", text)
    if not text or text in ("-", ".", ","):
        return None
    if "," in text and "." in text:
        # Sondaki ayraç ondalıktır: '1.234,56' (TR) veya '1,234.56' (EN)
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(",", ".") if text.count(",") == 1 else text.replace(",", "")
    elif text.count(".") > 1:
        text = text.replace(".", "")  # '1.234.567' binlik ayraç
    try:
        return float(text)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Dosya okuma
# ---------------------------------------------------------------------------

class ImportFileError(ValueError):
    """Kullanıcıya gösterilecek dosya hatası."""


def read_table(filename: str, content: bytes) -> pd.DataFrame:
    """xlsx veya csv dosyasını tüm hücreler metin olacak şekilde okur."""
    name = (filename or "").lower()
    if not content:
        raise ImportFileError("Dosya boş.")
    if name.endswith(".xls"):
        raise ImportFileError("Eski .xls biçimi desteklenmiyor — ikas'tan XLSX veya CSV olarak dışa aktarın.")
    if name.endswith(".xlsx") or content[:2] == b"PK":
        try:
            df = pd.read_excel(io.BytesIO(content), dtype=str, engine="openpyxl")
        except Exception as e:  # bozuk / şifreli dosya
            raise ImportFileError(f"Excel dosyası okunamadı: {e}")
    else:
        text = None
        for encoding in ("utf-8-sig", "cp1254", "latin-1"):
            try:
                text = content.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        if text is None:
            raise ImportFileError("CSV dosyasının karakter kodlaması çözülemedi.")
        try:
            delimiter = csv.Sniffer().sniff(text[:5000], delimiters=",;\t").delimiter
        except csv.Error:
            delimiter = ";" if text.count(";") > text.count(",") else ","
        try:
            df = pd.read_csv(io.StringIO(text), dtype=str, sep=delimiter, keep_default_na=False)
        except Exception as e:
            raise ImportFileError(f"CSV dosyası okunamadı: {e}")
    df = df.dropna(how="all")
    df.columns = [str(c).strip() for c in df.columns]
    return df


# ---------------------------------------------------------------------------
# Sipariş gruplama
# ---------------------------------------------------------------------------

def parse_orders(df: pd.DataFrame) -> Dict[str, Any]:
    """DataFrame → {orders: [...], mapping, ignored_columns, missing_fields}.
    Her sipariş: {order_number, fields: {...}, lines: [...], raw_rows: [...]}."""
    mapping, ignored = match_columns(list(df.columns))
    missing = [f for f in REQUIRED_FIELDS if f not in mapping]
    if "order_number" not in mapping:
        return {"orders": [], "mapping": mapping, "ignored_columns": ignored, "missing_fields": missing}

    orders: Dict[str, Dict[str, Any]] = {}
    for _, row in df.iterrows():
        def get(field: str) -> Any:
            col = mapping.get(field)
            return row[col] if col is not None else None

        number = clean_id(get("order_number"))
        if not number:
            continue
        order = orders.setdefault(number, {"order_number": number, "fields": {}, "lines": [], "raw_rows": []})
        order["raw_rows"].append({str(k): clean_text(v) for k, v in row.items()})

        fields = order["fields"]
        for field in ORDER_FIELDS:
            if field in fields or field not in mapping:
                continue
            if field in ("order_total", "shipping_fee", "discount"):
                value = parse_amount(get(field))
                if value is not None:
                    fields[field] = value
            elif field in ("identity_number", "tax_number", "phone", "postal_code"):
                value = clean_id(get(field))
                if value:
                    fields[field] = value
            else:
                value = clean_text(get(field))
                if value:
                    fields[field] = value

        name = clean_text(get("product_name"))
        if name:
            line = {
                "name": name,
                "variant": clean_text(get("variant")),
                "sku": clean_id(get("sku")),
                "barcode": clean_id(get("barcode")),
                "quantity": parse_amount(get("quantity")) or 1,
                "unit_price": parse_amount(get("unit_price")),
                "line_total": parse_amount(get("line_total")),
                "line_discount": parse_amount(get("line_discount")) or 0.0,
                "vat_rate": parse_amount(get("line_vat_rate")),
            }
            order["lines"].append(line)

    return {
        "orders": list(orders.values()),
        "mapping": mapping,
        "ignored_columns": ignored,
        "missing_fields": missing,
    }


# ---------------------------------------------------------------------------
# Fatura taslağı
# ---------------------------------------------------------------------------

BILLING_FIELDS = ["full_name", "company_name", "identity_number", "tax_number", "tax_office", "email", "phone",
                  "address", "district", "city", "postal_code", "country"]

# TC bilinmeyen bireysel e-Arşiv faturalarında yaygın kullanılan değer — muhasebeciyle teyit edilmeli.
UNKNOWN_TCKN = "11111111111"
_TOLERANCE = 0.05


def _r2(x: float) -> float:
    return round(x + 0.0, 2)


def effective_billing(fields: Dict[str, Any], overrides: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    """Dosyadaki alanlardan fatura bilgilerini türetir, elle düzeltmeleri üstüne uygular."""
    full_name = fields.get("full_name") or " ".join(
        p for p in (fields.get("first_name"), fields.get("last_name")) if p
    )
    address = " ".join(p for p in (fields.get("address"), fields.get("address2")) if p)
    billing = {
        "full_name": full_name,
        "company_name": fields.get("company_name", ""),
        "identity_number": fields.get("identity_number", ""),
        "tax_number": fields.get("tax_number", ""),
        "tax_office": fields.get("tax_office", ""),
        "email": fields.get("email", ""),
        "phone": fields.get("phone", ""),
        "address": address or fields.get("shipping_address", ""),
        "district": fields.get("district") or fields.get("shipping_district", ""),
        "city": fields.get("city") or fields.get("shipping_city", ""),
        "postal_code": fields.get("postal_code", ""),
        "country": fields.get("country") or "Türkiye",
    }
    for key, value in (overrides or {}).items():
        if key in BILLING_FIELDS and value is not None:
            billing[key] = str(value).strip()
    return billing


def build_invoice_draft(
    order: Dict[str, Any],
    overrides: Optional[Dict[str, Any]] = None,
    product_vat_rate: float = 10.0,
    shipping_vat_rate: float = 20.0,
) -> Dict[str, Any]:
    """Sipariş → fatura taslağı (KDV ayrıştırılmış satırlar + toplamlar + sorunlar).

    errors: fatura kesilmesini ENGELLEYEN eksikler. warnings: kontrol edilmesi gerekenler.
    İndirim yorumu: dosyadaki sipariş toplamıyla hangi yorum tutuyorsa o seçilir —
    (a) satır tutarları indirimi zaten içeriyor, (b) indirim satırlara oransal dağıtılmalı."""
    fields = order.get("fields", {})
    billing = effective_billing(fields, overrides)
    errors: List[str] = []
    warnings: List[str] = []

    # --- Alıcı ---
    is_company = bool(billing["company_name"] or billing["tax_number"])
    if is_company:
        buyer_type = "kurumsal"
        tax_id = billing["tax_number"]
        if not billing["company_name"]:
            errors.append("Vergi numarası var ama firma ünvanı eksik.")
        if not re.fullmatch(r"\d{10}", tax_id or ""):
            errors.append("Kurumsal fatura için 10 haneli vergi numarası (VKN) gerekli.")
        if not billing["tax_office"]:
            errors.append("Kurumsal fatura için vergi dairesi gerekli.")
    else:
        buyer_type = "bireysel"
        tax_id = billing["identity_number"]
        if not billing["full_name"]:
            errors.append("Müşteri adı soyadı eksik.")
        if not tax_id:
            tax_id = UNKNOWN_TCKN
            warnings.append(f"TC kimlik no yok — {UNKNOWN_TCKN} kullanılacak (muhasebecinize teyit ettirin).")
        elif not re.fullmatch(r"\d{11}", tax_id):
            errors.append("TC kimlik no 11 haneli olmalı.")
    if not billing["address"]:
        errors.append("Fatura adresi eksik.")
    if not billing["city"]:
        errors.append("İl eksik.")
    if not billing["district"]:
        errors.append("İlçe eksik.")

    status_text = (fields.get("order_status") or "").lower()
    if any(word in status_text for word in ("iptal", "cancel", "iade", "refund")):
        warnings.append(f"Sipariş durumu '{fields.get('order_status')}' — iptal/iade edilmiş olabilir.")

    # --- Satırlar (KDV dahil brüt) ---
    raw_lines = order.get("lines", [])
    if not raw_lines:
        errors.append("Siparişte ürün satırı yok.")
    gross_lines: List[Tuple[Dict[str, Any], float]] = []
    for line in raw_lines:
        qty = line.get("quantity") or 1
        if line.get("line_total") is not None:
            gross = line["line_total"]
        elif line.get("unit_price") is not None:
            gross = line["unit_price"] * qty - (line.get("line_discount") or 0.0)
        else:
            errors.append(f"'{line.get('name')}' için fiyat bulunamadı.")
            gross = 0.0
        gross_lines.append((line, gross))

    lines_gross = sum(g for _, g in gross_lines)
    shipping = fields.get("shipping_fee") or 0.0
    discount = abs(fields.get("discount") or 0.0)
    order_total = fields.get("order_total")

    apply_discount = False
    if discount > 0:
        if order_total is None:
            apply_discount = True
            warnings.append("Sipariş toplamı dosyada yok — indirim ürün satırlarına dağıtıldı, tutarı kontrol edin.")
        elif abs(lines_gross + shipping - discount - order_total) <= _TOLERANCE:
            apply_discount = True
        elif abs(lines_gross + shipping - order_total) <= _TOLERANCE:
            apply_discount = False  # satır tutarları indirimi zaten içeriyor
        else:
            apply_discount = True
    if apply_discount and lines_gross > 0:
        factor = max(lines_gross - discount, 0.0) / lines_gross
        gross_lines = [(line, gross * factor) for line, gross in gross_lines]

    # --- KDV ayrıştırma ---
    invoice_lines: List[Dict[str, Any]] = []

    def add_line(name: str, qty: float, gross: float, rate: float, sku: str = "", barcode: str = ""):
        gross = _r2(gross)
        net = _r2(gross / (1 + rate / 100.0))
        invoice_lines.append({
            "name": name,
            "sku": sku,
            "barcode": barcode,
            "quantity": qty,
            "vat_rate": rate,
            "unit_price_net": round(net / qty, 6) if qty else net,
            "net_amount": net,
            "vat_amount": _r2(gross - net),
            "gross_amount": gross,
        })

    for line, gross in gross_lines:
        name = line["name"] + (f" - {line['variant']}" if line.get("variant") else "")
        rate = line["vat_rate"] if line.get("vat_rate") is not None else product_vat_rate
        add_line(name, line.get("quantity") or 1, gross, rate, line.get("sku", ""), line.get("barcode", ""))
    if shipping > 0:
        add_line("Kargo Bedeli", 1, shipping, shipping_vat_rate)

    net_total = _r2(sum(l["net_amount"] for l in invoice_lines))
    vat_total = _r2(sum(l["vat_amount"] for l in invoice_lines))
    gross_total = _r2(sum(l["gross_amount"] for l in invoice_lines))
    vat_breakdown: Dict[str, Dict[str, float]] = {}
    for l in invoice_lines:
        key = f"{l['vat_rate']:g}"
        bucket = vat_breakdown.setdefault(key, {"rate": l["vat_rate"], "net": 0.0, "vat": 0.0})
        bucket["net"] = _r2(bucket["net"] + l["net_amount"])
        bucket["vat"] = _r2(bucket["vat"] + l["vat_amount"])

    if order_total is not None and invoice_lines and abs(gross_total - order_total) > _TOLERANCE:
        warnings.append(
            f"Fatura toplamı ({gross_total:.2f}) ile ikas sipariş toplamı ({order_total:.2f}) tutmuyor."
        )
    if invoice_lines and gross_total <= 0:
        errors.append("Fatura toplamı sıfır veya negatif.")

    return {
        "order_number": order.get("order_number"),
        "buyer_type": buyer_type,
        "tax_id": tax_id,
        "billing": billing,
        "currency": fields.get("currency") or "TRY",
        "lines": invoice_lines,
        "totals": {
            "net": net_total,
            "vat": vat_total,
            "gross": gross_total,
            "vat_breakdown": list(vat_breakdown.values()),
            "order_total_in_file": order_total,
            "discount_applied": _r2(discount) if apply_discount else 0.0,
        },
        "errors": errors,
        "warnings": warnings,
        "ready": not errors,
    }
