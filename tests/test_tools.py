import pytest
from tools import lookup, calculate

DISTRICTS = ["Ossbridge", "Ossford", "Tarnvale", "Kelmarsh", "Brightwater", "Stonecairn",
             "Harrowfield", "Lindenmoor", "Redfen", "Ashgrove", "Millbrook", "Coldharbour"]
FIELDS = ["population_2025", "population_2020", "area_km2", "budget_million_tenge",
          "water_megalitres", "schools", "pupils", "roads_km", "founded_year"]


# ---------------- lookup
def test_lookup_correct_2025_number():
    r = lookup("Millbrook", "population_2025")
    assert r["value"] == 37203 and r["source"] == "NR-11"


def test_lookup_misspelled_name_gives_suggestion_not_a_guess():
    r = lookup("Ossbrige", "area_km2")
    assert r["error"] == "district_not_found" and "Ossbridge" in r["message"]
    assert "value" not in r


def test_lookup_similar_names_are_different_districts():
    assert lookup("Ossbridge", "area_km2")["value"] == 1284.6
    assert lookup("Ossford", "area_km2")["value"] == 846.2
    amb = lookup("Oss", "area_km2")
    assert amb["error"] == "ambiguous_district"
    assert set(amb["candidates"]) == {"Ossbridge", "Ossford"}


def test_lookup_ignores_archived_profile():
    r = lookup("Tarnvale", "pupils")           # archived NR-13 says 9,870
    assert r["value"] == 10652 and r["source"] == "NR-03"
    assert lookup("Kelmarsh", "schools")["value"] == 11   # archived NR-14 says 10


def test_lookup_applies_correction_notice():
    r = lookup("Brightwater", "area_km2")
    assert r["value"] == 921.4 and r["source"] == "NR-16"
    assert lookup("Brightwater", "population_2025")["source"] == "NR-05"


def test_lookup_converts_cubic_metres_to_megalitres():
    r = lookup("Lindenmoor", "water_megalitres")
    assert r["value"] == pytest.approx(2151.4) and r["unit"] == "megalitres" and "note" in r


def test_lookup_unknown_field_and_bad_arguments():
    assert lookup("Millbrook", "gdp")["error"] == "field_not_found"
    assert lookup(None, "area_km2")["error"] == "invalid_arguments"
    assert lookup("x" * 500, "area_km2")["error"] == "invalid_arguments"


def test_lookup_tariff():
    r = lookup("region", "water_tariff_2025")
    assert r["value"] == 142.35 and r["source"] == "NR-15"


@pytest.mark.parametrize("district", DISTRICTS)
def test_lookup_every_profile_parses_every_field(district):
    for f in FIELDS:
        r = lookup(district, f)
        assert "error" not in r, (district, f, r)


# ---------------- calculate
def test_calculate_basic_multiplication():
    assert calculate("48317 * 1.0947")["result"] == pytest.approx(52892.6199, abs=1e-3)


def test_calculate_division_and_precedence():
    assert calculate("44675 / 921.4")["result"] == pytest.approx(48.486, abs=1e-3)
    assert calculate("2 + 3 * 4")["result"] == 14
    assert calculate("-(3 - 5) / 4")["result"] == 0.5


def test_calculate_division_by_zero():
    assert calculate("1 / 0")["error"] == "division_by_zero"


@pytest.mark.parametrize("expr", ["__import__('os').system('echo hi')", "(1).__class__", "9**9**9"])
def test_calculate_refuses_dangerous_input(expr):
    r = calculate(expr)
    assert r["error"] == "unsafe_expression" and "result" not in r


def test_calculate_refuses_names_strings_and_garbage():
    assert calculate("abc")["error"] == "unsafe_expression"
    assert calculate("'a' * 3")["error"] == "invalid_expression"
    assert calculate("2 +")["error"] == "invalid_expression"
    assert calculate("")["error"] == "invalid_arguments"


def test_calculate_limits():
    assert calculate("1" * 300)["error"] == "expression_too_long"
    assert calculate("10000000000 * 10000000000 * 100000")["error"] == "number_too_large"