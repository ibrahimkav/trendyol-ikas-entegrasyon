"""
Ürün Fiyatlandırma — maliyet+kâr+kargo+KDV+komisyon'dan önerilen fiyat hesaplama.

NOT (bilinçli tasarım kararı): Bu, İLERİYE dönük "yeni fiyat belirle" hesaplayıcısı —
Dashboard/Kâr Marjı Listesi'nin GEÇMİŞE dönük KPI raporlamasından (utils/profitability.py,
Jim'in w2a-profit-formulas.md'sine göre KDV'yi ayrı net-aşama placeholder'ı sayan model)
FARKLI bir kalıp kullanır: burada KDV, standart "satış fiyatı KDV dahildir, KDV oranına
göre geri hesaplanır" TR e-ticaret konvansiyonuyla fiyattan düşülür (komisyon da fiyat
üzerinden). Bu iki modelin (raporlama vs. fiyatlandırma) birbiriyle TAM tutarlı olup
olmadığı insan/Jim tarafından teyit edilmeli — god'un orijinal görev tanımı KDV'yi
hesaplayıcının bir girdisi olarak açıkça istiyordu, bu yüzden burada korundu.

Formül (Net Kâr = P - KDV - Komisyon - Kargo - Maliyet'ten P için çözülür):
  Tutara göre (₺ hedef kâr):
    P = (hedef_kâr + kargo + maliyet) / (1 - kdv_oranı/(1+kdv_oranı) - komisyon_oranı)
  Orana göre (% hedef kâr marjı, margin = Net Kâr / P):
    P = (kargo + maliyet) / (1 - kdv_oranı/(1+kdv_oranı) - komisyon_oranı - margin)
"""
from typing import Optional


def calculate_suggested_price(
    cost: float,
    cargo_cost: float,
    category: Optional[str],
    target_mode: str,  # "amount" | "percent"
    target_value: float,
    vat_rate: Optional[float] = None,
    commission_rate: Optional[float] = None,
) -> Optional[dict]:
    from routers import financial as financial_module

    if vat_rate is None:
        vat_rate = financial_module.VAT_RATE
    if commission_rate is None:
        # calculate_commission tek bir toplam tutar üzerinden oran uyguluyor; oranı
        # ayıklamak için 1 birim üzerinden çağırıyoruz (rate = commission(1.0)).
        commission_rate = financial_module.calculate_commission(1.0, category)

    vat_fraction = vat_rate / (1 + vat_rate)
    denom_base = 1 - vat_fraction - commission_rate

    if target_mode == "amount":
        denom = denom_base
        if denom <= 0:
            return None
        price = (target_value + cargo_cost + cost) / denom
    elif target_mode == "percent":
        margin_fraction = target_value / 100.0
        denom = denom_base - margin_fraction
        if denom <= 0:
            return None
        price = (cargo_cost + cost) / denom
    else:
        return None

    vat_amount = price * vat_fraction
    commission_amount = price * commission_rate
    net_profit = price - vat_amount - commission_amount - cargo_cost - cost

    return {
        "suggested_price": round(price, 2),
        "cost": round(cost, 2),
        "cargo_cost": round(cargo_cost, 2),
        "vat_amount": round(vat_amount, 2),
        "vat_rate": round(vat_rate * 100, 2),
        "commission_amount": round(commission_amount, 2),
        "commission_rate": round(commission_rate * 100, 2),
        "net_profit": round(net_profit, 2),
        "profit_margin_percent": round((net_profit / price * 100), 2) if price > 0 else 0.0,
    }
