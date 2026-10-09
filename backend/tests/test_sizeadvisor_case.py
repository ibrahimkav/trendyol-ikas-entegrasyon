"""
w3-sizeadvisor-case: utils/size_advisor.py::parse_chart_text case-sensitivity
regresyonu. Kök neden: _extract_value_pairs, zaten _norm_tr() ile normalize
edilmiş 'label'ı HAM (normalize edilmemiş) 'chunk' içinde arıyordu — "bel"
deseni "Bel"/"BEL" ile hiç eşleşmiyordu. Saf fonksiyon testi, DB/HTTP yok.
"""
from utils.size_advisor import parse_chart_text


def test_documented_example_parses():
    """Bug'ın tanımı tam olarak buydu: endpoint'in KENDİ dokümante ettiği
    örnek metin (routers/size_chart.py'nin hata mesajındaki örnekle birebir
    aynı) parse edilemiyordu. Artık edilmeli."""
    text = (
        "S: Bel 71-76, Göğüs 83-88, Boy 165-170, Kilo 50-60\n"
        "M: Bel 76-81, Göğüs 88-93, Boy 170-175, Kilo 60-70"
    )
    rows = parse_chart_text(text)
    assert len(rows) == 2

    s_row = rows[0]
    assert s_row["size"] == "S"
    assert (s_row["bel_min"], s_row["bel_max"]) == (71, 76)
    assert (s_row["gogus_min"], s_row["gogus_max"]) == (83, 88)
    assert (s_row["boy_min"], s_row["boy_max"]) == (165, 170)
    assert (s_row["kilo_min"], s_row["kilo_max"]) == (50, 60)

    m_row = rows[1]
    assert m_row["size"] == "M"
    assert (m_row["bel_min"], m_row["bel_max"]) == (76, 81)


def test_mixed_and_upper_case_labels_parse():
    """Büyük/karışık harf + Türkçe aksan karışık bir varyant daha."""
    text = "l: BEDEN olcusu - Bel:81-86, gögüs 93-98, BOY 175-180, kilo 70-80"
    rows = parse_chart_text(text)
    assert len(rows) == 1
    row = rows[0]
    assert row["size"] == "L"
    assert (row["bel_min"], row["bel_max"]) == (81, 86)
    assert (row["gogus_min"], row["gogus_max"]) == (93, 98)
    assert (row["boy_min"], row["boy_max"]) == (175, 180)
    assert (row["kilo_min"], row["kilo_max"]) == (70, 80)
