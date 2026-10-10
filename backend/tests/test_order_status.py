from utils.order_status import is_countable_sale, order_status_of


def test_non_sale_statuses_excluded_case_insensitive():
    for s in ("Cancelled", "cancelled", "UnSupplied", "Un_Supplied", "RETURNED", " Returned "):
        assert not is_countable_sale(s), s
    for s in ("Created", "Picking", "Invoiced", "Shipped", "Delivered", "UnDelivered", None, ""):
        assert is_countable_sale(s), s


def test_order_status_of():
    assert order_status_of({"status": "Cancelled"}) == "Cancelled"
    assert order_status_of({"shipmentPackageStatus": "Delivered"}) == "Delivered"

    class O:
        status = "Returned"

    assert order_status_of(O()) == "Returned"
