"""
فارسی: ثابت‌های مشترک پروژه — مسیرها، مقادیر پیش‌فرض، و نگاشت‌های ثابت که
       در چند ماژول دیگر استفاده می‌شوند.
English: Shared project constants — paths, defaults, and fixed mappings
         used across several other modules.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

ODL_VERSION: str = "2.2.1"
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

BATCH_SIZE: int = 5
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
