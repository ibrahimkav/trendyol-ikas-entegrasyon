"""
Dashboard + Canlı Performans — Wave2a çekirdek sayfa endpoint'leri.

Her ikisi de store_id-scoped (Depends(get_current_store)) ve auth korumalı
(get_current_store zaten get_current_user'a bağımlı, JWT olmadan 401 döner).
Kârlılık hesaplaması backend/utils/profitability.py'de merkezileştirildi.
"""
from collections import defaultdict
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database.db import get_db
from database.models import Order, OrderLine, Product, Store
from security import get_current_store
from utils.profitability import compute_profitability, resolve_date_range

router = APIRouter()


@router.get("/summary")
async def get_dashboard_summary(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    store: Store = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    """6 KPI + gider kırılımı (donut) + kâr performansı zaman serisi.
    start_date/end_date: YYYY-MM-DD (verilmezse son 7 gün)."""
    start, end = resolve_date_range(start_date, end_date, default_days=7)
    result = compute_profitability(db, store.id, start, end)

    return {
        "period": {"start_date": start.strftime("%Y-%m-%d"), "end_date": end.strftime("%Y-%m-%d")},
        "kpis": {
            "total_revenue": result["total_revenue"],
            "cost_bearing_revenue": result["cost_bearing_revenue"],
            "gross_profit": result["gross_profit"],
            "net_profit": result["net_profit"],
            "net_profit_to_revenue_ratio": result["net_profit_to_revenue_ratio"],
            "net_profit_to_cost_ratio": result["net_profit_to_cost_ratio"],
        },
        "no_cost_data_revenue": result["no_cost_data_revenue"],
        "expense_breakdown": result["expense_breakdown"],
        "profit_performance": result["daily_net_profit"],
        "net_stage_deductions": result["net_stage_deductions"],
        "order_count": result["order_count"],
    }


@router.get("/live-performance")
async def get_live_performance(
    store: Store = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    """Bugünkü net kâr + saatlik seri + bugün sipariş alan ürünler."""
    now = datetime.now()
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)

    summary = compute_profitability(db, store.id, start_of_day, now)

    rows = (
        db.query(OrderLine, Order.order_date)
        .join(Order, OrderLine.order_id == Order.order_id)
        .filter(OrderLine.store_id == store.id, Order.store_id == store.id)
        .filter(Order.order_date >= start_of_day, Order.order_date <= now)
        .all()
    )

    product_costs = {
        p.product_id: p.default_cost
        for p in db.query(Product).filter(Product.store_id == store.id).all()
    }

    from routers import financial as financial_module

    hourly_profit: dict = defaultdict(float)
    product_today: dict = defaultdict(lambda: {"product_name": "", "quantity": 0, "revenue": 0.0})

    for line, order_date in rows:
        revenue = float(line.total_price or 0.0)
        product_today[line.product_id]["product_name"] = line.product_name or line.product_id
        product_today[line.product_id]["quantity"] += line.quantity or 0
        product_today[line.product_id]["revenue"] += revenue

        product_default_cost = product_costs.get(line.product_id)
        has_cost = bool((line.unit_cost and line.unit_cost > 0) or (product_default_cost and product_default_cost > 0))
        if not has_cost or not order_date:
            continue
        line_cost = (line.unit_cost * line.quantity) if (line.unit_cost and line.unit_cost > 0) else (product_default_cost * line.quantity)
        commission = financial_module.calculate_commission(revenue, line.category)
        cargo = (line.quantity or 1) * financial_module.CARGO_COST_PER_PRODUCT
        hourly_profit[order_date.hour] += revenue - line_cost - commission - cargo

    hourly_series = [
        {"hour": f"{h:02d}:00", "net_profit": round(hourly_profit.get(h, 0.0), 2)}
        for h in range(0, now.hour + 1)
    ]

    todays_products = sorted(
        (
            {"product_id": pid, **data, "revenue": round(data["revenue"], 2)}
            for pid, data in product_today.items()
        ),
        key=lambda x: x["revenue"],
        reverse=True,
    )

    return {
        "today": now.strftime("%Y-%m-%d"),
        "last_updated": now.strftime("%Y-%m-%d %H:%M:%S"),
        "net_profit": summary["net_profit"],
        "revenue": summary["total_revenue"],
        "net_profit_to_cost_ratio": summary["net_profit_to_cost_ratio"],
        "net_profit_to_revenue_ratio": summary["net_profit_to_revenue_ratio"],
        "hourly_profit_series": hourly_series,
        "todays_products": todays_products,
    }
