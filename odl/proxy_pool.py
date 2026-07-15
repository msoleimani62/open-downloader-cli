"""
فارسی: استخر پروکسی خودکار — از یک منبع (فایل محلی یا URL) که خود کاربر
       معرفی می‌کند، لیست پروکسی‌ها را می‌خواند، هرکدام را با یک تست واقعی
       (نه فقط پینگ) روی yt-dlp امتحان می‌کند، اولین پروکسی سالم را کش
       می‌کند، و پیش از هر استفاده‌ی بعدی دوباره همان را تست می‌کند تا اگر
       هنوز زنده بود، منبع دوباره اسکن نشود.
       این ماژول عمداً بدون هیچ sys.exit نوشته شده (برخلاف cookies.py که
       این بدهی را دارد) تا از همان ابتدا برای استفاده‌ی مستقیم از دسکتاپ
       GUI و اندروید هم آماده باشد؛ خطاها با ProxyPoolError گزارش می‌شوند.
English: Automatic proxy pool — reads a proxy list from a source (a local
         file or URL) that the user provides, real-tests each one (not
         just a ping) via yt-dlp, caches the first working proxy, and
         re-tests that same cached proxy before every later use so the
         source only needs to be re-scanned when the cached proxy actually
         dies.
         This module is deliberately written without any sys.exit (unlike
         cookies.py, which carries that debt) so it's ready for direct
         reuse from the desktop GUI and Android from day one; failures are
         reported via ProxyPoolError.
"""

from __future__ import annotations

import json
import time
import traceback
import urllib.request
from pathlib import Path
from typing import Callable, Optional

from . import constants as c
from .logging_setup import log_debug_traceback, log_info, log_warning
from .models import ProxyCheckResult, ProxyTestEventCallback


class ProxyPoolError(Exception):
    """
    فارسی: خطای بارگذاری منبع پروکسی (فایل پیدا نشد، URL در دسترس نبود،
           یا هیچ پروکسی معتبری در آن یافت نشد). عمداً از Exception معمولی
           ارث می‌برد (نه سیستم خروج) تا لایه‌ی UI خودش تصمیم بگیرد.
    English: Error loading the proxy source (file not found, URL
             unreachable, or no valid proxies found in it). Deliberately a
             plain Exception (not a process exit) so the UI layer decides
             what to do.
    """


def _normalize_proxy(raw: str) -> str:
    """
    فارسی: اگر پروکسی بدون scheme داده شده باشد (مثل «1.2.3.4:8080»)،
           پیش‌فرض http:// را اضافه می‌کند؛ چون این رایج‌ترین قالب در
           لیست‌های پروکسی عمومی است. اگر کاربر خودش socks5://... داده
           باشد، دست‌نخورده باقی می‌ماند.
    English: If a proxy is given without a scheme (e.g. "1.2.3.4:8080"),
             prefix it with http:// by default, since that's the most
             common format in public proxy lists. If the user already gave
             socks5://... etc., it's left untouched.
    """
    raw = raw.strip()
    if "://" not in raw:
        raw = f"http://{raw}"
    return raw


def load_proxy_candidates(source: str) -> list[str]:
    """
    فارسی: از یک فایل محلی یا یک URL، لیست پروکسی‌ها را می‌خواند (هر خط
           یک پروکسی؛ خطوط خالی و خطوطی که با # شروع می‌شوند نادیده گرفته
           می‌شوند، تکراری‌ها حذف می‌شوند). سقف تعداد کاندید با
           PROXY_POOL_MAX_CANDIDATES محدود می‌شود تا یک فایل بسیار بزرگ
           باعث یک اسکن چندساعته نشود.
    English: Read the proxy list from a local file or a URL (one proxy per
             line; blank lines and lines starting with # are ignored,
             duplicates are removed). Capped at PROXY_POOL_MAX_CANDIDATES
             so a huge file can't turn into an hours-long scan.
    """
    if source.startswith("http://") or source.startswith("https://"):
        try:
            req = urllib.request.Request(source, headers={"User-Agent": "odl-proxy-pool"})
            with urllib.request.urlopen(req, timeout=10) as response:
                raw_text = response.read().decode("utf-8", errors="ignore")
        except Exception as e:
            raise ProxyPoolError(f"Could not fetch the proxy list from {source}: {e}") from e
    else:
        path = Path(source).expanduser()
        if not path.exists():
            raise ProxyPoolError(f"Proxy list file not found: {path}")
        try:
            raw_text = path.read_text(encoding="utf-8")
        except Exception as e:
            raise ProxyPoolError(f"Could not read the proxy list file {path}: {e}") from e

    candidates: list[str] = []
    seen: set[str] = set()
    for line in raw_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        normalized = _normalize_proxy(line)
        if normalized in seen:
            continue
        seen.add(normalized)
        candidates.append(normalized)
        if len(candidates) >= c.PROXY_POOL_MAX_CANDIDATES:
            break

    if not candidates:
        raise ProxyPoolError(f"No proxies found in source: {source}")
    return candidates


def test_proxy(
    proxy: str,
    cookies_path: Optional[str] = None,
    timeout: int = c.PROXY_TEST_TIMEOUT_SECONDS,
) -> ProxyCheckResult:
    """
    فارسی: یک تست واقعی (نه فقط پینگ TCP) روی پروکسی انجام می‌دهد — با
           yt-dlp در حالت simulate، اطلاعات یک ویدیوی همیشه-در-دسترس
           یوتیوب را از پشت این پروکسی می‌خواند. اگر یوتیوب پروکسی را
           به‌عنوان ربات/دیتاسنتر فلگ کند یا اصلاً اتصال برقرار نشود،
           شکست با پیام خطا گزارش می‌شود.
    English: Run a real (not just a TCP ping) test against a proxy — using
             yt-dlp in simulate mode, fetch info for an always-available
             YouTube video through it. If YouTube flags the proxy as
             bot/datacenter, or the connection fails outright, failure is
             reported with an error message.
    """
    import yt_dlp  # فارسی: ایمپورت محلی تا این ماژول بدون yt-dlp هم قابل تست واحد بماند
    # English: local import so this module stays unit-testable without yt-dlp installed

    opts = {
        "proxy": proxy,
        "quiet": True,
        "no_warnings": True,
        "simulate": True,
        "skip_download": True,
        "socket_timeout": timeout,
    }
    if cookies_path:
        opts["cookiefile"] = cookies_path

    start = time.monotonic()
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.extract_info(c.PROXY_TEST_URL, download=False)
        latency_ms = (time.monotonic() - start) * 1000
        return ProxyCheckResult(proxy=proxy, ok=True, latency_ms=latency_ms)
    except Exception as e:
        log_debug_traceback(traceback.format_exc())
        return ProxyCheckResult(proxy=proxy, ok=False, error=str(e))


def load_cached_proxy(source: str) -> Optional[str]:
    """
    فارسی: آخرین پروکسی سالم ذخیره‌شده برای دقیقاً همین منبع را برمی‌گرداند.
           اگر منبع عوض شده باشد (مثلاً کاربر --proxy-pool دیگری داده)،
           کش قدیمی نامعتبر است و None برمی‌گردد.
    English: Return the last known-good proxy cached for this exact source.
             If the source has changed (e.g. the user passed a different
             --proxy-pool), the old cache is invalid and None is returned.
    """
    if not c.PROXY_STATE_FILE.exists():
        return None
    try:
        data = json.loads(c.PROXY_STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None
    if data.get("source") != source:
        return None
    proxy = data.get("proxy")
    return proxy if isinstance(proxy, str) else None


def save_cached_proxy(source: str, proxy: str) -> None:
    """
    فارسی: پروکسی سالم فعلی را همراه با منبعش و زمان تأییدش ذخیره می‌کند.
    English: Persist the current known-good proxy along with its source
             and verification timestamp.
    """
    c.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    c.PROXY_STATE_FILE.write_text(
        json.dumps(
            {"source": source, "proxy": proxy, "verified_at": time.time()},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def clear_cached_proxy() -> None:
    """
    فارسی: کش پروکسی را حذف می‌کند (مثلاً برای اجبار به اسکن کامل دوباره).
    English: Delete the proxy cache (e.g. to force a full re-scan).
    """
    if c.PROXY_STATE_FILE.exists():
        c.PROXY_STATE_FILE.unlink()


def resolve_working_proxy(
    source: str,
    cookies_path: Optional[str] = None,
    force_refresh: bool = False,
    on_event: Optional[ProxyTestEventCallback] = None,
    tester: Callable[..., ProxyCheckResult] = test_proxy,
) -> Optional[str]:
    """
    فارسی:
        هسته‌ی اصلی استخر پروکسی:
        ۱. اگر force_refresh نباشد، اول پروکسی کش‌شده را دوباره تست
           می‌کند؛ اگر هنوز سالم بود همان را برمی‌گرداند بدون این‌که
           اصلاً به منبع سر بزند.
        ۲. اگر کش وجود نداشت یا مرده بود، کاندیدهای منبع را یکی‌یکی تست
           می‌کند تا اولین پروکسی سالم را پیدا کند، آن را کش کرده و
           برمی‌گرداند.
        ۳. اگر هیچ‌کدام کار نکردند، None برمی‌گرداند — این خطای فاتال
           نیست؛ لایه‌ی فراخوان می‌تواند بدون پروکسی ادامه دهد.
        پارامتر tester فقط برای تست واحد است (تا بدون yt-dlp واقعی و
        بدون اتصال شبکه، منطق رتست/کش/چرخش قابل بررسی باشد).
    English:
        The proxy pool's core:
        1. Unless force_refresh, re-tests the cached proxy first; if it
           still works, returns it as-is without touching the source at
           all.
        2. If there's no cache or it's dead, tests source candidates one
           by one until the first working proxy is found, caches it, and
           returns it.
        3. If none work, returns None — not a fatal error; the caller can
           continue without a proxy.
        The tester parameter exists purely for unit testing (so the
        retest/cache/rotate logic can be exercised without real yt-dlp or
        network access).
    """
    if not force_refresh:
        cached = load_cached_proxy(source)
        if cached:
            result = tester(cached, cookies_path)
            if on_event is not None:
                on_event(0, 0, result)
            if result.ok:
                save_cached_proxy(source, cached)
                return cached
            log_warning(f"Cached proxy {cached} is no longer working; scanning the pool again.")

    candidates = load_proxy_candidates(source)

    total = len(candidates)
    for i, candidate in enumerate(candidates, start=1):
        result = tester(candidate, cookies_path)
        if on_event is not None:
            on_event(i, total, result)
        if result.ok:
            latency = f"{result.latency_ms:.0f}ms" if result.latency_ms is not None else "unknown latency"
            log_info(f"Proxy {candidate} works ({latency}); caching it.")
            save_cached_proxy(source, candidate)
            return candidate

    log_warning(f"None of the {total} proxies from {source} worked.")
    return None
