"""
فارسی: مدل‌های داده‌ی مشترک و کاملاً بدون وابستگی به رابط کاربری (بدون rich،
       بدون console، بدون getpass) — قابل استفاده از CLI، دسکتاپ‌جی‌یوآی، و
       لایه‌ی Chaquopy روی اندروید بدون هیچ تغییری.
English: Shared, fully UI-agnostic data models (no rich, no console, no
         getpass) — usable as-is from the CLI, desktop GUI, and the
         Chaquopy layer on Android.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class DownloadRequest:
    """
    فارسی: تمام پارامترهای لازم برای یک دانلود تکی، در یک شیء واحد به‌جای
           لیست طولانی آرگومان‌های positional.
    English: All parameters needed for a single download, bundled into one
             object instead of a long list of positional arguments.
    """

    url: str
    out_template: str
    cookies_path: Optional[str] = None
    quality: int = 480
    sub_en: bool = False
    sub_fa: bool = False
    audio_only: bool = False
    proxy: Optional[str] = None
    extractor_args: dict = field(default_factory=dict)
    allow_client_fallback: bool = True


@dataclass
class DownloadEvent:
    """
    فارسی: یک رویداد لحظه‌ای در طول دانلود. سه نوع دارد:
           "progress" (پیشرفت دانلود)، "status" (تغییر وضعیت مثل finalizing)،
           و "retry" (تلاش مجدد با کلاینت پخش دیگر).
    English: A single point-in-time download event. Three kinds:
             "progress" (download progress), "status" (a state change like
             finalizing), and "retry" (retrying with a different playback client).
    """

    kind: str
    downloaded_bytes: Optional[int] = None
    total_bytes: Optional[int] = None
    title: Optional[str] = None
    message: Optional[str] = None
    client: Optional[str] = None


@dataclass
class DownloadResult:
    """
    فارسی: نتیجه‌ی نهایی یک تلاش دانلود (موفق یا ناموفق با دسته‌بندی خطا).
    English: The final result of a download attempt (success, or failure
              with a classified error category).
    """

    ok: bool
    error_message: Optional[str] = None
    error_category: Optional[str] = None
    tried_clients: list = field(default_factory=list)


# فارسی: امضای تابع callback که رویدادهای دانلود را دریافت می‌کند.
# English: The signature of the callback function that receives download events.
DownloadEventCallback = Callable[[DownloadEvent], None]


@dataclass
class ProxyCheckResult:
    """
    فارسی: نتیجه‌ی یک تست سلامت واقعی روی یک پروکسی (نه فقط اتصال شبکه،
           بلکه تست واقعی extract_info روی یک ویدیوی یوتیوب).
    English: The result of a real health check against a proxy (not just a
             network connection, but an actual yt-dlp extract_info test
             against a YouTube video).
    """

    proxy: str
    ok: bool
    latency_ms: Optional[float] = None
    error: Optional[str] = None


# فارسی: امضای تابع callback که پیشرفت تست هر کاندید پروکسی را گزارش می‌کند.
# English: The signature of the callback function reporting each proxy
#          candidate's test progress.
ProxyTestEventCallback = Callable[[int, int, ProxyCheckResult], None]
