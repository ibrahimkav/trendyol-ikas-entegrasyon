"""
Wave 2a — paylaşılan kârlılık hesaplama motoru.

Dashboard, Kâr Marjı Listesi, Ürün Fiyatlandırma ve Canlı Performans sayfalarının
hepsi AYNI formülü kullanır; tekrarı önlemek için burada merkezîleştirildi.

VERİ KAYNAĞI KARARI: mevcut financial.py/products.py/orders.py gibi router'lar
Trendyol API'yi CANLI ve TEK (env'deki) kimlik bilgisiyle çekiyor — bu hem
çok-kiracılılıkla uyumsuz (her mağazanın kendi kimlik bilgisi olmalı) hem de
Trendyol API kotasına/yavaşlığına bağımlı. Bu modül bunun yerine LOKAL DB'yi
(Order/OrderLine/Product, store_id ile filtrelenmiş) kullanır — SyncService zaten
bu tabloları dolduruyor. Bu, çok-kiracılı doğru temel; canlı-API'den okuyan eski
router'ların retrofit'i (Wave2b) ayrı bir iştir (bkz. w2a-pam notu).

FORMÜL — Jim'in `hive/agents/jim-mttzcpqv/w2a-profit-formulas.md` araştırmasından
(ekran görüntüsü rakamlarından ters mühendislikle YÜKSEK GÜVENLE doğrulanmış):
  Toplam Ciro        = tüm sipariş satırlarının toplam tutarı
  Maliyeti Olan Ciro = maliyeti BİLİNEN (unit_cost>0 veya Product.default_cost>0)
                       satırların toplam tutarı — kâr hesaplanabilen ciro alt kümesi
  Ürün Maliyeti      = maliyeti bilinen satırlar için toplam maliyet (kullanıcı girişi)
  Brüt Kâr           = Maliyeti Olan Ciro − (Ürün Maliyeti + Komisyon + Kargo)
  Net Kâr            = Brüt Kâr − (Net KDV + Hizmet Bedeli + Ödeme Hizmeti Yansıması +
                        Stopaj + Ceza + Erken Ödeme Kesintisi + Diğer Faturalar + Ekstra Maliyet)
  Net Kâr/Satış Fiyatı Oranı  = Net Kâr ÷ Maliyeti Olan Ciro × 100   (payda Toplam Ciro DEĞİL!)
  Net Kâr/Ürün Maliyeti Oranı = Net Kâr ÷ Ürün Maliyeti × 100        (payda SADECE ürün maliyeti)

Net Kâr'daki 7 kalemden (Net KDV, Hizmet Bedeli, Ödeme Hizmeti, Stopaj, Ceza,
Erken Ödeme, Diğer Faturalar) hiçbiri şu an gerçek Trendyol Settlement/OtherFinancials
verisiyle beslenmiyor (o entegrasyon ayrı/daha büyük bir iş — bkz. Jim'in
trendyol-api-capability-map.md'si) — DÜŞÜK güven seviyeli oldukları için Jim'in
önerisiyle ŞİMDİLİK ₺0 PLACEHOLDER bırakıldı (gerçek Settlement verisiyle kalibre
edilecek). Sadece "Ekstra Maliyet" kullanıcı girişi (financial.py'deki mevcut
in-memory `expenses` — kargo/reklam/stok/diğer) bu döneme denk gelenler toplanarak
dahil edildi. Bu yüzden bu placeholder'lar 0 olduğu sürece Brüt Kâr = Net Kâr çıkar
— ki bu TAM OLARAK ekran görüntüsündeki demo davranışıyla örtüşüyor (Jim madde 2).
"""
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, Optional

from sqlalchemy.orm import Session

from database.models import Order, OrderLine, Product
from routers import financial as financial_module  # CARGO_COST_PER_PRODUCT/VAT_RATE/expenses canlı okunsun diye modül referansı
from utils.image_cdn import trendyol_thumbnail_url


def _extra_expense_for_period(start_date: datetime, end_date: datetime) -> float:
    """financial.py'nin in-memory `expenses` deposundan bu döneme denk gelenlerin toplamı
    ("Ekstra Maliyet" kalemi). NOT: bu depo process-memory-only ve store'a göre AYRIŞMIYOR
    (backend-gap-analysis.md'de zaten flag edilmişti) — Wave2b'de DB'ye taşınıp store_id
    eklenmeli; o zamana kadar tüm mağazalar aynı gider havuzunu paylaşıyor (bilinen sınır)."""
    total = 0.0
    for exp in financial_module.expenses.values():
        try:
            exp_date = datetime.fromisoformat(exp.date).date()
        except Exception:
            continue
        if start_date.date() <= exp_date <= end_date.date():
            total += exp.amount
    return total


def compute_profitability(
    db: Session,
    store_id: int,
    start_date: datetime,
    end_date: datetime,
) -> Dict:
    """Verilen tarih aralığı için store_id'ye ait tüm sipariş satırlarından
    toplam KPI'ları + günlük net kâr serisini + gider kırılımını hesaplar."""
    cargo_per_product = financial_module.CARGO_COST_PER_PRODUCT

    rows = (
        db.query(OrderLine, Order.order_date)
        .join(Order, OrderLine.order_id == Order.order_id)
        .filter(OrderLine.store_id == store_id, Order.store_id == store_id)
        .filter(Order.order_date >= start_date, Order.order_date <= end_date)
        .all()
    )

    product_costs = {
        p.product_id: p.default_cost
        for p in db.query(Product).filter(Product.store_id == store_id).all()
    }

    total_revenue = 0.0
    cost_bearing_revenue = 0.0
    product_cost_total = 0.0
    commission_total = 0.0
    cargo_total = 0.0
    daily_gross_profit: Dict[str, float] = defaultdict(float)

    for line, order_date in rows:
        revenue = float(line.total_price or 0.0)
        total_revenue += revenue

        product_default_cost = product_costs.get(line.product_id)
        has_cost = bool((line.unit_cost and line.unit_cost > 0) or (product_default_cost and product_default_cost > 0))
        if not has_cost:
            continue

        line_cost = (line.unit_cost * line.quantity) if (line.unit_cost and line.unit_cost > 0) else (product_default_cost * line.quantity)
        commission = financial_module.calculate_commission(revenue, line.category)
        cargo = (line.quantity or 1) * cargo_per_product

        cost_bearing_revenue += revenue
        product_cost_total += line_cost
        commission_total += commission
        cargo_total += cargo

        line_gross_profit = revenue - line_cost - commission - cargo
        if order_date:
            daily_gross_profit[order_date.strftime("%Y-%m-%d")] += line_gross_profit

    gross_profit = cost_bearing_revenue - product_cost_total - commission_total - cargo_total

    # Düşük güvenli net-aşama kalemleri — gerçek Trendyol Settlement/OtherFinancials
    # entegrasyonu olmadan hesaplanamaz, şimdilik ₺0 (bkz. modül docstring'i).
    net_vat = 0.0
    service_fee = 0.0
    payment_service_cost = 0.0
    withholding_tax = 0.0
    penalty = 0.0
    early_payment_deduction = 0.0
    other_invoices = 0.0
    extra_cost = _extra_expense_for_period(start_date, end_date)

    net_stage_deductions = (
        net_vat + service_fee + payment_service_cost + withholding_tax
        + penalty + early_payment_deduction + other_invoices + extra_cost
    )
    net_profit = gross_profit - net_stage_deductions

    # Ekstra Maliyet dışındaki net-aşama kalemleri şu an her zaman 0 olduğu için günlük
    # seride ekstra maliyeti tarihe göre dağıtmıyoruz (hangi güne ait olduğu expense
    # kaydında var ama günlük kırılım MVP'de brüt kâr üzerinden veriliyor).
    daily_net_profit = [
        {"date": d, "net_profit": round(v, 2)} for d, v in sorted(daily_gross_profit.items())
    ]

    return {
        "total_revenue": round(total_revenue, 2),
        "cost_bearing_revenue": round(cost_bearing_revenue, 2),
        "no_cost_data_revenue": round(total_revenue - cost_bearing_revenue, 2),
        "product_cost": round(product_cost_total, 2),
        "commission": round(commission_total, 2),
        "cargo_cost": round(cargo_total, 2),
        "gross_profit": round(gross_profit, 2),
        "net_stage_deductions": {
            "net_vat": net_vat,
            "service_fee": service_fee,
            "payment_service_cost": payment_service_cost,
            "withholding_tax": withholding_tax,
            "penalty": penalty,
            "early_payment_deduction": early_payment_deduction,
            "other_invoices": other_invoices,
            "extra_cost": round(extra_cost, 2),
            "_note": "net_vat/service_fee/payment_service_cost/withholding_tax/penalty/early_payment_deduction/other_invoices şu an ₺0 placeholder (gerçek Trendyol Settlement/OtherFinancials verisi olmadan hesaplanamıyor, bkz. w2a-profit-formulas.md). Sadece extra_cost gerçek (financial.py expenses deposundan).",
        },
        "net_profit": round(net_profit, 2),
        "net_profit_to_revenue_ratio": round((net_profit / cost_bearing_revenue * 100), 2) if cost_bearing_revenue > 0 else 0.0,
        "net_profit_to_cost_ratio": round((net_profit / product_cost_total * 100), 2) if product_cost_total > 0 else 0.0,
        "daily_net_profit": daily_net_profit,
        "expense_breakdown": [
            {"category": "Ürün Maliyeti", "amount": round(product_cost_total, 2)},
            {"category": "Komisyon", "amount": round(commission_total, 2)},
            {"category": "Kargo", "amount": round(cargo_total, 2)},
            {"category": "Ekstra Maliyet", "amount": round(extra_cost, 2)},
        ],
        "order_count": len({line.order_id for line, _ in rows}),
    }


def compute_product_profitability(
    db: Session,
    store_id: int,
    start_date: datetime,
    end_date: datetime,
) -> list:
    """Kâr Marjı Listesi için ürün-bazlı kırılım. Aynı formül (Brüt/Net Kâr,
    Ürün Maliyeti paydalı oran) ama toplam yerine ürün başına döner."""
    rows = (
        db.query(OrderLine)
        .join(Order, OrderLine.order_id == Order.order_id)
        .filter(OrderLine.store_id == store_id, Order.store_id == store_id)
        .filter(Order.order_date >= start_date, Order.order_date <= end_date)
        .all()
    )

    products = {p.product_id: p for p in db.query(Product).filter(Product.store_id == store_id).all()}

    agg: Dict[str, Dict] = {}
    for line in rows:
        product = products.get(line.product_id)
        default_cost = product.default_cost if product else 0.0
        revenue = float(line.total_price or 0.0)
        has_cost = bool((line.unit_cost and line.unit_cost > 0) or (default_cost and default_cost > 0))
        cost = (line.unit_cost * line.quantity) if (line.unit_cost and line.unit_cost > 0) else ((default_cost or 0.0) * line.quantity)
        commission = financial_module.calculate_commission(revenue, line.category) if has_cost else 0.0
        cargo = ((line.quantity or 1) * financial_module.CARGO_COST_PER_PRODUCT) if has_cost else 0.0

        row = agg.setdefault(line.product_id, {
            "product_id": line.product_id,
            "product_name": line.product_name or (product.product_name if product else line.product_id),
            "barcode": product.barcode if product else None,
            "category": line.category or (product.category if product else None),
            "current_price": product.current_price if product else None,
            "thumbnail_url": trendyol_thumbnail_url(product.image_url) if product else None,
            "quantity_sold": 0,
            "revenue": 0.0,
            "product_cost": 0.0,
            "commission": 0.0,
            "cargo_cost": 0.0,
            "has_cost_data": has_cost,
        })
        row["quantity_sold"] += line.quantity or 0
        row["revenue"] += revenue
        if has_cost:
            row["product_cost"] += cost
            row["commission"] += commission
            row["cargo_cost"] += cargo
            row["has_cost_data"] = True

    results = []
    for row in agg.values():
        gross_profit = row["revenue"] - row["product_cost"] - row["commission"] - row["cargo_cost"] if row["has_cost_data"] else None
        net_profit = gross_profit  # net-aşama placeholder'ları şu an 0 (bkz. modül docstring'i)
        margin = (net_profit / row["revenue"] * 100) if (row["has_cost_data"] and row["revenue"] > 0) else None
        results.append({
            **{k: v for k, v in row.items() if k != "has_cost_data"},
            "revenue": round(row["revenue"], 2),
            "product_cost": round(row["product_cost"], 2),
            "commission": round(row["commission"], 2),
            "cargo_cost": round(row["cargo_cost"], 2),
            "gross_profit": round(gross_profit, 2) if gross_profit is not None else None,
            "net_profit": round(net_profit, 2) if net_profit is not None else None,
            "profit_margin_percent": round(margin, 2) if margin is not None else None,
            "has_cost_data": row["has_cost_data"],
            "is_profitable": (net_profit is not None and net_profit >= 0),
        })
    return results


def compute_order_profitability(
    db: Session,
    store_id: int,
    start_date: datetime,
    end_date: datetime,
    limit: Optional[int] = None,
) -> list:
    """Sipariş-bazlı kârlılık (Raporlar → Sipariş Kârlılık). Her sipariş için
    satırlarını toplayıp aynı w2a formülünü uygular."""
    q = (
        db.query(Order)
        .filter(Order.store_id == store_id)
        .filter(Order.order_date >= start_date, Order.order_date <= end_date)
        .order_by(Order.order_date.desc())
    )
    if limit:
        q = q.limit(limit)
    orders = q.all()

    products = {p.product_id: p for p in db.query(Product).filter(Product.store_id == store_id).all()}
    # order_id -> satırlar
    lines_by_order: Dict[str, list] = defaultdict(list)
    for line in db.query(OrderLine).filter(OrderLine.store_id == store_id).all():
        lines_by_order[line.order_id].append(line)

    results = []
    for order in orders:
        revenue = 0.0
        product_cost = 0.0
        commission = 0.0
        cargo = 0.0
        has_cost = False
        for line in lines_by_order.get(order.order_id, []):
            line_rev = float(line.total_price or 0.0)
            revenue += line_rev
            product = products.get(line.product_id)
            default_cost = product.default_cost if product else 0.0
            line_has_cost = bool((line.unit_cost and line.unit_cost > 0) or (default_cost and default_cost > 0))
            if line_has_cost:
                has_cost = True
                product_cost += (line.unit_cost * line.quantity) if (line.unit_cost and line.unit_cost > 0) else (default_cost * line.quantity)
                commission += financial_module.calculate_commission(line_rev, line.category)
                cargo += (line.quantity or 1) * financial_module.CARGO_COST_PER_PRODUCT

        gross_profit = (revenue - product_cost - commission - cargo) if has_cost else None
        net_profit = gross_profit  # net-aşama placeholder'ları 0
        margin = (net_profit / revenue * 100) if (has_cost and revenue > 0) else None
        results.append({
            "order_id": order.order_id,
            "order_number": order.order_number,
            "order_date": order.order_date.strftime("%Y-%m-%d %H:%M") if order.order_date else None,
            "customer_name": order.customer_name,
            "status": order.status,
            "revenue": round(revenue, 2),
            "product_cost": round(product_cost, 2),
            "commission": round(commission, 2),
            "cargo_cost": round(cargo, 2),
            "gross_profit": round(gross_profit, 2) if gross_profit is not None else None,
            "net_profit": round(net_profit, 2) if net_profit is not None else None,
            "profit_margin_percent": round(margin, 2) if margin is not None else None,
            "has_cost_data": has_cost,
            "is_profitable": (net_profit is not None and net_profit >= 0),
        })
    return results


def compute_category_profitability(
    db: Session,
    store_id: int,
    start_date: datetime,
    end_date: datetime,
) -> list:
    """Kategori-bazlı kârlılık (Raporlar → Kategori Kârlılık). Ürün kırılımını
    kategoriye göre toplar."""
    per_product = compute_product_profitability(db, store_id, start_date, end_date)
    agg: Dict[str, Dict] = {}
    for p in per_product:
        cat = p["category"] or "Kategorisiz"
        row = agg.setdefault(cat, {
            "category": cat, "product_count": 0, "quantity_sold": 0,
            "revenue": 0.0, "product_cost": 0.0, "commission": 0.0, "cargo_cost": 0.0,
            "net_profit": 0.0, "has_cost_data": False,
        })
        row["product_count"] += 1
        row["quantity_sold"] += p["quantity_sold"]
        row["revenue"] += p["revenue"]
        if p["has_cost_data"]:
            row["has_cost_data"] = True
            row["product_cost"] += p["product_cost"]
            row["commission"] += p["commission"]
            row["cargo_cost"] += p["cargo_cost"]
            row["net_profit"] += p["net_profit"] or 0.0

    results = []
    for row in agg.values():
        margin = (row["net_profit"] / row["revenue"] * 100) if (row["has_cost_data"] and row["revenue"] > 0) else None
        results.append({
            "category": row["category"],
            "product_count": row["product_count"],
            "quantity_sold": row["quantity_sold"],
            "revenue": round(row["revenue"], 2),
            "product_cost": round(row["product_cost"], 2),
            "commission": round(row["commission"], 2),
            "cargo_cost": round(row["cargo_cost"], 2),
            "net_profit": round(row["net_profit"], 2) if row["has_cost_data"] else None,
            "profit_margin_percent": round(margin, 2) if margin is not None else None,
            "has_cost_data": row["has_cost_data"],
        })
    results.sort(key=lambda x: (x["net_profit"] if x["net_profit"] is not None else -1e18), reverse=True)
    return results


def compute_return_loss(
    db: Session,
    store_id: int,
    start_date: datetime,
    end_date: datetime,
) -> dict:
    """İade-zarar analizi (Raporlar → İade Zarar). return_refunds tablosundan
    store_id-scoped iade/iptal kayıtlarını toplayıp zarar tahmini üretir.
    NOT: iade edilen ürünün maliyeti geri kazanılıp kazanılmadığı (ürün tekrar
    satılabilir mi) bilinmiyor — bu yüzden 'kayıp' = iade edilen gelir + o gelirin
    kargo/komisyon maliyeti şeklinde muhafazakâr tahmin; kesin değer settlement
    Return kalemleriyle kalibre edilmeli (per-store Trendyol API — ayrı iş)."""
    from database.models import ReturnRefund

    returns = (
        db.query(ReturnRefund)
        .filter(ReturnRefund.store_id == store_id)
        .filter(ReturnRefund.created_at >= start_date, ReturnRefund.created_at <= end_date)
        .all()
    )

    by_reason: Dict[str, Dict] = defaultdict(lambda: {"count": 0, "refund_amount": 0.0})
    total_refund = 0.0
    total_count = 0
    for r in returns:
        total_count += 1
        total_refund += float(r.refund_amount or 0.0)
        reason = r.reason or "Belirtilmemiş"
        by_reason[reason]["count"] += 1
        by_reason[reason]["refund_amount"] += float(r.refund_amount or 0.0)

    return {
        "total_returns": total_count,
        "total_refund_amount": round(total_refund, 2),
        "by_reason": [
            {"reason": k, "count": v["count"], "refund_amount": round(v["refund_amount"], 2)}
            for k, v in sorted(by_reason.items(), key=lambda x: x[1]["refund_amount"], reverse=True)
        ],
    }


def resolve_date_range(start_date: Optional[str], end_date: Optional[str], default_days: int = 7):
    now = datetime.now()
    if end_date:
        end = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
    else:
        end = now
    if start_date:
        start = datetime.strptime(start_date, "%Y-%m-%d")
    else:
        start = end - timedelta(days=default_days)
    return start, end
