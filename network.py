"""
HTTP-сессия с retry, backoff и обёртками.
"""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import (
    HEADERS, POOL_CONNECTIONS, POOL_MAXSIZE,
    MAX_RETRIES, RETRY_BACKOFF,
)
from logger import get_logger

log = get_logger("network")


def create_session() -> requests.Session:
    """Создаёт сессию с retry-стратегией."""
    s = requests.Session()
    s.headers.update(HEADERS)

    retry = Retry(
        total=MAX_RETRIES,
        backoff_factor=RETRY_BACKOFF,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "HEAD"],
        raise_on_status=False,
    )

    adapter = HTTPAdapter(
        pool_connections=POOL_CONNECTIONS,
        pool_maxsize=POOL_MAXSIZE,
        max_retries=retry,
    )
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s


session = create_session()


def safe_get(url: str, timeout: int = 30, **kwargs) -> requests.Response | None:
    """GET с обработкой ошибок."""
    try:
        resp = session.get(url, timeout=timeout, **kwargs)
        resp.raise_for_status()
        return resp
    except requests.RequestException as e:
        log.debug(f"GET failed: {url} — {e}")
        return None


def safe_head(url: str, timeout: int = 10, **kwargs) -> requests.Response | None:
    """HEAD с обработкой ошибок."""
    try:
        return session.head(url, timeout=timeout, allow_redirects=True, **kwargs)
    except requests.RequestException as e:
        log.debug(f"HEAD failed: {url} — {e}")
        return None