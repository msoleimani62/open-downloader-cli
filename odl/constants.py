"""
فارسی: ثابت‌های مشترک پروژه — مسیرها، مقادیر پیش‌فرض، و نگاشت‌های ثابت که
       در چند ماژول دیگر استفاده می‌شوند.
English: Shared project constants — paths, defaults, and fixed mappings
         used across several other modules.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

ODL_VERSION: str = "2.1.0"
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

CleanupFn = Callable[[], None]
