"""
w3-manual-numeric-validation (Phyllis'in UX incelemesi, bulgu #3): gerçek
satıcı verisine (maliyet/desi/fiyat) sayı yazan uçların HİÇBİRİ arasında bu
mantık tekrar tekrar yazılmasın diye TEK yerde toplandı — toplu CSV yolunun
zaten sahip olduğu NEGATIVE_VALUE kuralıyla AYNI, artı yeni bir üst-sınır
kontrolü (fat-finger / yanlışlıkla fazladan basamak yakalar).

Üst sınırlar GERÇEK bir iş kuralı DEĞİL — bilinçli olarak çok cömert seçildi
(gerçek hiçbir veriyi reddetmesin diye), sadece "500 yerine 50000" türü açık
veri-giriş hatalarını yakalamak için bir güvenlik ağı.
"""
from typing import Optional

COST_MAX = 1_000_000.0
DESI_MAX = 1_000.0
PRICE_MAX = 1_000_000.0


def numeric_field_error(value: Optional[float], field_label: str, max_value: float) -> Optional[str]:
    """value None ise (alan gönderilmedi / değiştirilmeyecek) None döner.
    Negatifse veya üst sınırı aşıyorsa açıklayıcı Türkçe mesaj döner, aksi halde None."""
    if value is None:
        return None
    if value < 0:
        return f"{field_label} negatif olamaz"
    if value > max_value:
        return f"{field_label} {max_value:g} değerini aşamaz (muhtemelen yanlışlıkla fazladan basamak girildi)"
    return None


def is_negative(value: Optional[float]) -> bool:
    return value is not None and value < 0
