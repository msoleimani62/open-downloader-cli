"""
فارسی: ثابت‌های مشترک پروژه — مسیرها، مقادیر پیش‌فرض، و نگاشت‌های ثابت که
       در چند ماژول دیگر استفاده می‌شوند.
English: Shared project constants — paths, defaults, and fixed mappings
         used across several other modules.
"""

from __future__ import annotations

import importlib.metadata
from collections.abc import Callable
from pathlib import Path

# فارسی: نسخه فقط در یک جا تعریف می‌شود — بخش [project.version] در
#        pyproject.toml. اینجا فقط از متادیتای پکیج نصب‌شده (چه با
#        «pip install .» چه با «pip install -e .») می‌خوانیمش، تا هیچ‌وقت
#        دوباره مثل این جلسه (2.3.1 -> 2.4.0 دستی در دو فایل) از هم عقب
#        نیفتند. اگر پکیج اصلاً نصب نشده باشد (مثلاً اجرای مستقیم از روی
#        سورس بدون pip install)، یک مقدار fallback ثابت استفاده می‌شود که
#        فقط باید همزمان با bump کردن pyproject.toml آپدیت شود.
# English: The version is defined in exactly one place — the
#          [project.version] field in pyproject.toml. Here we only read
#          it from the installed package's metadata (whether installed via
#          "pip install ." or "pip install -e ."), so the two copies can
#          never drift apart again like they did this session (2.3.1 ->
#          2.4.0 bumped by hand in two files). If the package isn't
#          installed at all (e.g. running straight from source without
#          pip install), a fixed fallback is used — it only needs to be
#          updated in lockstep with bumping pyproject.toml.
try:
    ODL_VERSION: str = importlib.metadata.version("open-downloader-cli")
except importlib.metadata.PackageNotFoundError:
    ODL_VERSION: str = "2.4.0"  # fallback برای اجرای مستقیم بدون نصب / fallback for running unpackaged

GITHUB_REPO: str = "msoleimani62/open-downloader-cli"

ALLOWED_QUALITIES: list[int] = [144, 240, 360, 480, 720, 1080, 1440, 2160]
DEFAULT_QUALITY: int = 480

CONFIG_DIR: Path = Path.home() / ".config" / "opendl"
CONFIG_FILE: Path = CONFIG_DIR / "config.json"
COOKIES_DEFAULT: Path = Path.home() / "cookies.txt"
ENCRYPTED_COOKIES_FILE: Path = CONFIG_DIR / "cookies.enc"
DOWNLOAD_DIR_DEFAULT: Path = Path.home() / "Downloads" / "opendl"
LOG_FILE: Path = CONFIG_DIR / "opendl.log"
LOG_DIR: Path = CONFIG_DIR / "logs"
PLAYLIST_STATE_DIR: Path = CONFIG_DIR / "playlist_state"
SELF_UPDATE_CACHE_FILE: Path = CONFIG_DIR / "self_update_check.json"
# فارسی: فاصله‌ی زمانی بین دو چک خودکار موفق (۴۸ ساعت) در برابر فاصله‌ی
#        کوتاه‌تر بعد از یک چک ناموفق (۱ ساعت، مثلاً چون شبکه/VPN آن لحظه
#        قطع بوده) — تا هم روی شبکه‌ی ناپایدار هر اجرا معطل نشود و هم بعد
#        از وصل شدن دوباره‌ی شبکه، خیلی زود دوباره امتحان کند.
# English: Interval between two successful automatic checks (48h) versus
#          the shorter interval after a failed check (1h, e.g. because the
#          network/VPN happened to be down at that moment) — so an
#          unstable network doesn't stall every single run, while a check
#          is retried soon after connectivity comes back.
SELF_UPDATE_CHECK_INTERVAL_SECONDS: int = 48 * 3600
SELF_UPDATE_RETRY_INTERVAL_SECONDS: int = 3600
SELF_UPDATE_CHECK_TIMEOUT_SECONDS: int = 3

BATCH_SIZE: int = 3
# فارسی: قبلاً واقعاً بی‌نهایت بود (float('inf'))؛ مشکلش این بود که روی
#        یه لینک واقعاً مرده (حذف‌شده/private/شبکه‌ی قطع‌شده) برنامه بدون
#        هیچ پیام خطایی تا ابد گیر می‌کرد. ۳۰ برای شبکه‌ی ناپایدار (مثل
#        VPN/Xray) کاملاً کافیه، ولی در نهایت یه خطای واضح نشون می‌ده.
# English: This used to be truly infinite (float('inf')); the problem was
#          that on a genuinely dead link (deleted/private/network down)
#          the program would hang forever with no error at all. 30 is
#          plenty for a flaky network (e.g. VPN/Xray) while still
#          eventually surfacing a clear error.
MAX_RETRIES: int = 30
# فارسی: طبق توصیه‌ی فعلی OWASP برای PBKDF2-HMAC-SHA256 (حداقل ۶۰۰٬۰۰۰).
# English: Per the current OWASP recommendation for PBKDF2-HMAC-SHA256 (minimum 600,000).
PBKDF2_ITERATIONS: int = 600_000
MAX_PASSWORD_ATTEMPTS: int = 3
MAX_LOG_LINES: int = 300

PLAYER_CLIENT_FALLBACK_CHAIN: list[str] = ["web", "android", "mweb", "ios", "tv"]

COOKIE_SEARCH_PATHS: list[Path] = [
    Path.home() / "storage" / "downloads" / "cookies.txt",
    Path.home() / "storage" / "downloads" / "www.youtube.com_cookies.txt",
    Path.home() / "storage" / "downloads" / "youtube.com_cookies.txt",
    Path("/sdcard/Download/cookies.txt"),
    Path("/sdcard/Download/www.youtube.com_cookies.txt"),
    Path("/sdcard/Download/youtube.com_cookies.txt"),
]

ANDROID_FIREFOX_PROFILES_DIR: Path = Path("/data/data/org.mozilla.firefox/files/mozilla")

ANDROID_MARKER_PATHS: list[Path] = [Path("/system/build.prop"), Path("/system/bin/getprop")]
ANDROID_MARKER_ENV_VARS: list[str] = ["ANDROID_ROOT", "ANDROID_DATA", "TERMUX_VERSION"]

# فارسی: وقتی داخل یک chroot/proot هستیم (مثل Kali NetHunter)، نشونه‌های
#        بالا اصلاً دیده نمی‌شوند چون متعلق به بیرون chroot‌اند. ولی این
#        زیرسیستم‌های کرنلی مخصوص اندروید همیشه در /proc/mounts دیده
#        می‌شوند چون کرنل زیرِ chroot هم همان کرنل اندرویدی هاست است.
# English: When inside a chroot/proot (e.g. Kali NetHunter), the markers
#          above aren't visible at all since they belong outside the
#          chroot. But these Android-specific kernel subsystems always
#          show up in /proc/mounts, since the kernel underneath the
#          chroot is still the host's Android kernel.
ANDROID_KERNEL_MOUNT_SIGNALS: list[str] = ["binder ", " binderfs ", "cpuset", "schedtune", "seclabel"]

PROXY_STATE_FILE: Path = CONFIG_DIR / "proxy_state.json"
# فارسی: ویدیوی «Me at the zoo» — اولین ویدیوی یوتیوب، همیشه در دسترس و
#        بسیار کوچک؛ فقط برای تست واقعی سلامت پروکسی استفاده می‌شود
#        (simulate=True یعنی چیزی واقعاً دانلود نمی‌شود).
# English: The "Me at the zoo" video — YouTube's first ever upload, always
#          available and tiny; used only as a real health check for a
#          proxy (simulate=True means nothing is actually downloaded).
PROXY_TEST_URL: str = "https://www.youtube.com/watch?v=jNQXAC9IVRw"
PROXY_TEST_TIMEOUT_SECONDS: int = 15
PROXY_POOL_MAX_CANDIDATES: int = 30

CleanupFn = Callable[[], None]
