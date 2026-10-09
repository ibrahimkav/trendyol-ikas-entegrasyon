"""
Kargo hazırlığı sıralaması: aynı ürünü içeren siparişler art arda gelmeli
(utils/order_grouping.py). Trendyol'a çağrı yapılmaz.
"""
from utils.order_grouping import order_products, product_summary, sort_orders_by_product


def _order(number, lines, date=0):
    return {
        "orderNumber": number,
        "orderDate": date,
        "lines": [
            {"productName": name, "barcode": code, "quantity": qty}
            for name, code, qty in lines
        ],
    }


def _numbers(orders):
    return [o["orderNumber"] for o in orders]


def test_same_product_orders_are_adjacent():
    orders = [
        _order("1", [("Mom Jean Mavi, 30", "MJ30", 1)], date=1),
        _order("2", [("Boyfriend Kot Gri, 30", "BF30", 1)], date=2),
        _order("3", [("Mom Jean Mavi, 30", "MJ30", 1)], date=3),
        _order("4", [("Boyfriend Kot Gri, 30", "BF30", 1)], date=4),
        _order("5", [("Mom Jean Mavi, 28", "MJ28", 1)], date=5),
    ]
    result = _numbers(sort_orders_by_product(orders))
    # Aynı model bir arada, içinde aynı beden yan yana, aynı üründe eskiden yeniye
    assert result == ["2", "4", "5", "1", "3"]


def test_sizes_sort_naturally_and_mixed_orders_come_last():
    orders = [
        _order("A", [("Kot, 32", "K32", 1), ("Tişört, M", "TM", 1)]),
        _order("B", [("Kot, 100", "K100", 1)]),
        _order("C", [("Kot, 32", "K32", 1)]),
        _order("D", [("Tişört, M", "TM", 1), ("Kot, 32", "K32", 1)]),  # A ile aynı kombinasyon
        _order("E", [("Kot, 9", "K9", 1)]),
    ]
    result = _numbers(sort_orders_by_product(orders))
    assert result[:3] == ["E", "C", "B"]  # 9 < 32 < 100 (metin değil sayı olarak)
    assert result[3:] == ["A", "D"]  # karma siparişler sonda, aynı kombinasyon yan yana


def test_quantity_then_date_break_ties_and_case_is_ignored():
    orders = [
        _order("x", [("KOT PANTOLON İNDİGO", "K1", 2)], date=10),
        _order("y", [("Kot Pantolon İndigo", "K1", 1)], date=30),
        _order("z", [("kot pantolon indigo", "K1", 1)], date=20),
    ]
    assert _numbers(sort_orders_by_product(orders)) == ["z", "y", "x"]


def test_duplicate_lines_are_merged_and_summary():
    order = _order("1", [("Kot", "K1", 1), ("Kot", "K1", 2), ("Gömlek", "G1", 1)])
    products = order_products(order)
    assert [(p["name"], p["quantity"]) for p in products] == [("Gömlek", 1), ("Kot", 3)]
    assert product_summary(order) == "Gömlek ×1 + Kot ×3"
    # Aynı ürün iki satırda olsa da tek çeşit sayılır → karma değil
    single = _order("2", [("Kot", "K1", 1), ("Kot", "K1", 1)])
    mixed = _order("3", [("Kot", "K1", 1), ("Gömlek", "G1", 1)])
    assert _numbers(sort_orders_by_product([mixed, single])) == ["2", "3"]


def test_missing_fields_do_not_crash_and_input_is_not_mutated():
    orders = [
        {"orderNumber": "empty", "lines": []},
        {"orderNumber": "nodate", "lines": [{"productTitle": "Şort", "merchantSku": "S1"}]},
        {"id": 99, "orderDate": "bozuk", "lines": [{"name": "Şort", "sku": "S1", "quantity": "x"}]},
        {"orderNumber": "none", "lines": None},
    ]
    original = list(orders)
    result = sort_orders_by_product(orders)
    assert orders == original
    assert len(result) == 4
    # Ürünsüz siparişler en sonda
    assert {o.get("orderNumber") for o in result[-2:]} == {"empty", "none"}


def test_unicode_superscript_digits_do_not_break_sorting():
    """Regresyon (gözden geçirmede bulundu): '10²' gibi isdigit() olup int()'e
    çevrilemeyen karakterler sıralamayı ValueError ile düşürüyordu."""
    orders = [
        _order("1", [("Halı 10²", "A", 1)]),
        _order("2", [("Paket 3①", "B", 1)]),
        _order("3", [("²", "C", 1)]),
        _order("4", [("Halı 9", "D", 1)]),
    ]
    result = _numbers(sort_orders_by_product(orders))
    assert sorted(result) == ["1", "2", "3", "4"]
    assert result.index("4") < result.index("1")  # 'halı 9' < 'halı 10²'


def test_malformed_order_goes_last_instead_of_failing_batch():
    """Regresyon: tek bozuk sipariş (dict olmayan satır / sipariş) tüm toplu
    yazdırmayı 500'e düşürmemeli."""
    good = _order("good", [("Kot", "K1", 1)])
    bad_line = {"orderNumber": "bad", "lines": [None, "x"]}
    result = sort_orders_by_product([bad_line, "not-an-order", good])
    assert result[0] is good
    assert len(result) == 3
    assert product_summary(bad_line) == ""


def test_size_from_separate_field_is_used_for_grouping_and_summary():
    orders = [
        {"orderNumber": "1", "orderDate": 1, "lines": [{"productName": "Mom Jean", "productSize": "30", "barcode": "Z9"}]},
        {"orderNumber": "2", "orderDate": 2, "lines": [{"productName": "Mom Jean", "productSize": "28", "barcode": "Z1"}]},
        {"orderNumber": "3", "orderDate": 3, "lines": [{"productName": "Mom Jean", "productSize": "30", "barcode": "Z9"}]},
        # beden zaten adın içindeyse tekrar eklenmez
        {"orderNumber": "4", "orderDate": 4, "lines": [{"productName": "Kot, 32", "productSize": "32", "barcode": "K"}]},
    ]
    assert _numbers(sort_orders_by_product(orders)) == ["4", "2", "1", "3"]
    assert product_summary(orders[0]) == "Mom Jean, 30 ×1"
    assert product_summary(orders[3]) == "Kot, 32 ×1"
