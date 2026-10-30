from datetime import date

import pytest

from macro_peru.bcrp.periods import format_period, frequency, parse_period, parse_value


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("02.Ene.26", date(2026, 1, 2)),
        ("01.Set.26", date(2026, 9, 1)),  # daily series use "Set"
        ("Sep.2026", date(2026, 9, 1)),  # monthly series use "Sep"
        ("Dic.2025", date(2025, 12, 1)),
        ("T1.25", date(2025, 1, 1)),
        ("T4.26", date(2026, 10, 1)),
        ("2026", date(2026, 1, 1)),
    ],
)
def test_parse_period(label: str, expected: date) -> None:
    assert parse_period(label) == expected


@pytest.mark.parametrize("label", ["", "Foo.2026", "T5.26", "2026-01"])
def test_parse_period_rejects_unknown(label: str) -> None:
    with pytest.raises(ValueError):
        parse_period(label)


def test_parse_value() -> None:
    assert parse_value("3.45385714285714") == pytest.approx(3.45385714285714)
    assert parse_value("-0.35") == -0.35
    assert parse_value("n.d.") is None


@pytest.mark.parametrize(
    ("code", "freq"),
    [("PD04638PD", "diaria"), ("PN01273PM", "mensual"), ("PN02526AQ", "trimestral"),
     ("PM04863AA", "anual")],
)  # fmt: skip
def test_frequency(code: str, freq: str) -> None:
    assert frequency(code) == freq


def test_format_period() -> None:
    d = date(2026, 8, 15)
    assert format_period(d, "diaria") == "2026-08-15"
    assert format_period(d, "mensual") == "2026-8"
    assert format_period(d, "trimestral") == "2026-3"
    assert format_period(d, "anual") == "2026"
