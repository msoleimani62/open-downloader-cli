"""
فارسی: مدل‌های داده‌ی مشترک و کاملاً بدون وابستگی به رابط کاربری (بدون rich،
       بدون console، بدون getpass) — قابل استفاده از CLI، دسکتاپ‌جی‌یوآی، و
       لایه‌ی Chaquopy روی اندروید بدون هیچ تغییری.
English: Shared, fully UI-agnostic data models (no rich, no console, no
         getpass) — usable as-is from the CLI, desktop GUI, and the
         Chaquopy layer on Android.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field


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
    cookies_path: str | None = None
    quality: int = 480
    sub_en: bool = False
    sub_fa: bool = False
    audio_only: bool = False
    proxy: str | None = None
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
    downloaded_bytes: int | None = None
    total_bytes: int | None = None
    title: str | None = None
    message: str | None = None
    client: str | None = None


@dataclass
class DownloadResult:
    """
    فارسی: نتیجه‌ی نهایی یک تلاش دانلود (موفق یا ناموفق با دسته‌بندی خطا).
    English: The final result of a download attempt (success, or failure
              with a classified error category).
    """

    ok: bool
    error_message: str | None = None
    error_category: str | None = None
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
    latency_ms: float | None = None
    error: str | None = None


# فارسی: امضای تابع callback که پیشرفت تست هر کاندید پروکسی را گزارش می‌کند.
# English: The signature of the callback function reporting each proxy
#          candidate's test progress.
ProxyTestEventCallback = Callable[[int, int, ProxyCheckResult], None]


@dataclass
class PlaylistItemResult:
    """
    فارسی: نتیجه‌ی دانلود یک آیتم از پلی‌لیست. note برای موارد خاص مثل
           "resumed" (قبلاً در اجرای قبلی کامل شده) استفاده می‌شود؛ لایه‌ی
           UI بر اساس آن متن نمایشی مناسب را انتخاب می‌کند.
    English: The result of downloading a single playlist item. note is used
             for special cases like "resumed" (already completed in a
             previous run); the UI layer picks the right display text
             based on it.
    """

    index: int
    title: str
    ok: bool
    error_category: str = ""
    note: str = ""


@dataclass
class PlaylistDownloadEvent:
    """
    فارسی: یک رویداد لحظه‌ای در طول تخمین حجم یا دانلود دسته‌ای پلی‌لیست.
           kind یکی از این مقادیر است:
           "estimate_progress" (پیشرفت تخمین حجم)،
           "batch_start" (شروع یک دسته‌ی جدید، همراه با لیست آیتم‌های آن)،
           "item_progress" (پیشرفت دانلود یک آیتم)،
           "item_status" (تغییر وضعیت مثل finalizing)،
           "item_retry" (تلاش مجدد یک آیتم با کلاینت پخش دیگر)،
           "item_done" (پایان یک آیتم، موفق یا ناموفق).
    English: A single point-in-time event during playlist size estimation
             or the batch download. kind is one of:
             "estimate_progress" (size-estimation progress),
             "batch_start" (a new batch is starting, with its item list),
             "item_progress" (a single item's download progress),
             "item_status" (a state change like finalizing),
             "item_retry" (retrying a single item with a different client),
             "item_done" (a single item finished, success or failure).
    """

    kind: str
    index: int | None = None
    title: str | None = None
    downloaded_bytes: int | None = None
    total_bytes: int | None = None
    client: str | None = None
    checked: int | None = None
    total: int | None = None
    batch: list | None = None
    result: PlaylistItemResult | None = None


# فارسی: امضای تابع callback که رویدادهای تخمین حجم/دانلود پلی‌لیست را دریافت می‌کند.
# English: The signature of the callback function that receives playlist
#          size-estimation/download events.
PlaylistEventCallback = Callable[[PlaylistDownloadEvent], None]
