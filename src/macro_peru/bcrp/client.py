"""Client for the public BCRPData API.

The API sits behind an Incapsula bot filter: plain HTTP clients get a JavaScript
challenge page ("Pardon Our Interruption") with status 200 instead of JSON. When that
happens the client solves the challenge once with headless Chromium (Playwright),
copies its cookies and User-Agent into the requests session, and retries.

Other API quirks handled here:
- Several codes in one call are sorted by code and codes with a different frequency
  are silently dropped, so values cannot be mapped back by position. We request one
  code per call.
- The body encoding varies per series (UTF-8 or Latin-1) and the Content-Type header
  always says text/html.
- An unknown code returns status 200 with malformed JSON.
"""

import json
import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from macro_peru.bcrp.periods import format_period, frequency

BASE_URL = "https://estadisticas.bcrp.gob.pe/estadisticas/series/api"
TIMEOUT_S = 30

log = logging.getLogger(__name__)

ChallengeSolver = Callable[[str], tuple[dict[str, str], str]]


class BcrpError(RuntimeError):
    """The API answered, but not with usable data for the requested series."""


def solve_challenge(url: str) -> tuple[dict[str, str], str]:
    """Load the URL in headless Chromium until the bot filter lets it through.

    Returns the browser cookies and its User-Agent, which must be sent together.
    The sync Playwright API refuses to run inside a running asyncio loop, and
    Databricks serverless tasks and notebooks have one, so it runs in a worker thread.
    """
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(_solve_challenge, url).result()


def _solve_challenge(url: str) -> tuple[dict[str, str], str]:
    from playwright.sync_api import sync_playwright  # heavy, only needed when challenged

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(url, wait_until="networkidle", timeout=60_000)
            page.wait_for_timeout(5_000)  # the challenge script sets the cookies
            page.goto(url, wait_until="networkidle", timeout=60_000)
            cookies = {c["name"]: c["value"] for c in page.context.cookies()}
            return cookies, page.evaluate("navigator.userAgent")
        finally:
            browser.close()


def decode_body(content: bytes) -> str:
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        return content.decode("latin-1")


def is_challenge(body: str) -> bool:
    return not body.lstrip().startswith("{")


class BcrpClient:
    def __init__(
        self,
        session: requests.Session | None = None,
        solver: ChallengeSolver = solve_challenge,
    ) -> None:
        self.session = session or requests.Session()
        self.session.headers.setdefault("Accept", "application/json")
        self.solver = solver

    def url(self, code: str, start: date, end: date) -> str:
        freq = frequency(code)
        return f"{BASE_URL}/{code}/json/{format_period(start, freq)}/{format_period(end, freq)}/esp"

    @retry(
        retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, max=30),
        reraise=True,
    )
    def _get(self, url: str) -> str:
        resp = self.session.get(url, timeout=TIMEOUT_S)
        resp.raise_for_status()
        return decode_body(resp.content)

    def fetch_raw(self, code: str, start: date, end: date) -> str:
        """Return the raw JSON text for one series, solving the bot filter if needed."""
        url = self.url(code, start, end)
        body = self._get(url)
        if is_challenge(body):
            log.info("Bot challenge from BCRPData, solving it with headless Chromium")
            cookies, user_agent = self.solver(url)
            self.session.cookies.update(cookies)
            self.session.headers["User-Agent"] = user_agent
            body = self._get(url)
            if is_challenge(body):
                raise BcrpError(f"Bot challenge persisted after solving it: {url}")
        return body

    def fetch_one(self, code: str, start: date, end: date) -> dict:
        body = self.fetch_raw(code, start, end)
        try:
            payload = json.loads(body)
            series = payload["config"]["series"]
        except (json.JSONDecodeError, KeyError, TypeError):
            raise BcrpError(f"Invalid response for {code}; is the code correct?") from None
        if len(series) != 1:
            raise BcrpError(f"Expected 1 series for {code}, got {len(series)}")
        return payload

    def fetch_series(self, codes: list[str], start: date, end: date) -> dict[str, dict]:
        """Fetch several series between two dates; returns {code: payload}."""
        return {code: self.fetch_one(code, start, end) for code in codes}
