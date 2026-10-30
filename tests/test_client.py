from datetime import date
from pathlib import Path

import pytest
import yaml

from macro_peru.bcrp.client import BcrpClient, BcrpError, decode_body
from macro_peru.bcrp.periods import parse_period, parse_value

FIXTURES = Path(__file__).parent / "fixtures"
ROOT = Path(__file__).resolve().parents[1]
CHALLENGE = b"<!DOCTYPE html><html><head><title>Pardon Our Interruption</title></head></html>"


class FakeResponse:
    def __init__(self, content: bytes) -> None:
        self.content = content

    def raise_for_status(self) -> None:
        pass


class FakeSession:
    """Returns the queued bodies in order and records the requested URLs."""

    def __init__(self, *bodies: bytes) -> None:
        self.bodies = list(bodies)
        self.urls: list[str] = []
        self.headers: dict[str, str] = {}
        self.cookies: dict[str, str] = {}

    def get(self, url: str, timeout: int) -> FakeResponse:
        self.urls.append(url)
        return FakeResponse(self.bodies.pop(0))


def fixture(code: str) -> bytes:
    return (FIXTURES / f"bcrp_{code}.json").read_bytes()


def test_url_uses_period_format_of_the_code_frequency() -> None:
    client = BcrpClient(FakeSession())
    start, end = date(2026, 1, 1), date(2026, 9, 30)
    assert client.url("PD04638PD", start, end).endswith("/PD04638PD/json/2026-01-01/2026-09-30/esp")
    assert client.url("PN01273PM", start, end).endswith("/PN01273PM/json/2026-1/2026-9/esp")
    assert client.url("PN02526AQ", start, end).endswith("/PN02526AQ/json/2026-1/2026-3/esp")


def test_fetch_series_requests_one_code_per_call() -> None:
    session = FakeSession(fixture("PN01273PM"), fixture("PN01277PM"))
    result = BcrpClient(session).fetch_series(["PN01273PM", "PN01277PM"], date(2026, 1, 1),
                                              date(2026, 9, 1))  # fmt: skip
    assert list(result) == ["PN01273PM", "PN01277PM"]
    assert len(session.urls) == 2
    assert "Sin Alimentos y Energ" in result["PN01277PM"]["config"]["series"][0]["name"]


def test_challenge_is_solved_once_and_retried() -> None:
    session = FakeSession(CHALLENGE, fixture("PD04638PD"))
    calls = []

    def solver(url: str) -> tuple[dict[str, str], str]:
        calls.append(url)
        return {"incap_ses": "abc"}, "Mozilla/5.0 test"

    payload = BcrpClient(session, solver=solver).fetch_one(
        "PD04638PD", date(2026, 10, 15), date(2026, 10, 29)
    )
    assert len(calls) == 1
    assert session.cookies == {"incap_ses": "abc"}
    assert session.headers["User-Agent"] == "Mozilla/5.0 test"
    assert payload["periods"]


def test_persistent_challenge_raises() -> None:
    client = BcrpClient(FakeSession(CHALLENGE, CHALLENGE), solver=lambda url: ({}, "ua"))
    with pytest.raises(BcrpError, match="persisted"):
        client.fetch_one("PD04638PD", date(2026, 10, 1), date(2026, 10, 2))


def test_unknown_code_raises() -> None:
    # Real API answer for an unknown code: status 200 with malformed JSON.
    client = BcrpClient(FakeSession(b'{ "config": { ] }, "periods": [ ] }'))
    with pytest.raises(BcrpError, match="code"):
        client.fetch_one("PN38712PM", date(2026, 8, 1), date(2026, 9, 1))


def test_decode_body_falls_back_to_latin1() -> None:
    assert decode_body("Tasas de interés".encode("latin-1")) == "Tasas de interés"
    assert decode_body("Índice".encode()) == "Índice"


@pytest.mark.parametrize("path", sorted(FIXTURES.glob("bcrp_*.json")), ids=lambda p: p.stem)
def test_every_fixture_parses(path: Path) -> None:
    code = path.stem.removeprefix("bcrp_")
    payload = BcrpClient(FakeSession(path.read_bytes())).fetch_one(code, date(2026, 1, 1),
                                                                  date(2026, 1, 2))  # fmt: skip
    for period in payload["periods"]:
        parse_period(period["name"])
        parse_value(period["values"][0])


def test_catalog_has_a_fixture_per_series() -> None:
    catalog = yaml.safe_load((ROOT / "config/series.yml").read_text(encoding="utf-8"))
    codes = {s["codigo"] for s in catalog["series"]}
    assert codes == {p.stem.removeprefix("bcrp_") for p in FIXTURES.glob("bcrp_*.json")}
    assert len({s["alias"] for s in catalog["series"]}) == len(codes)
