#!/usr/bin/env python3
"""
Open Downloader CLI (odl)

فارسی: دانلودر ساده، رزیوم‌پذیر و امن یوتیوب بر پایه‌ی yt-dlp.
English: A simple, resumable, and secure YouTube downloader built on yt-dlp.
"""

from __future__ import annotations

import argparse
import base64
import concurrent.futures
import getpass
import json
import os
import platform
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import traceback
from pathlib import Path
from typing import Callable, Optional, Tuple

try:
    import yt_dlp
except ImportError:
    print("yt-dlp not found. Install it with: pip install yt-dlp --break-system-packages")
    sys.exit(1)

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import (
        BarColumn,
        DownloadColumn,
        Progress,
        SpinnerColumn,
        TextColumn,
        TimeRemainingColumn,
        TransferSpeedColumn,
    )
    from rich.prompt import Confirm
    from rich.table import Table
except ImportError:
    print("rich library not found. Install it with: pip install rich --break-system-packages")
    sys.exit(1)

try:
    from cryptography.fernet import Fernet, InvalidToken
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

console = Console()

# فارسی: در حالت دیباگ، اطلاعات کامل و traceback نشان داده می‌شود (با --debug فعال می‌شود)
# English: in debug mode, full details and tracebacks are shown (enabled via --debug)
DEBUG: bool = False

# فارسی: کیفیت‌های استاندارد یوتیوب که کاربر مجاز به انتخابشونه
# English: Standard YouTube resolutions the user is allowed to pick from
ALLOWED_QUALITIES: list[int] = [144, 240, 360, 480, 720, 1080, 1440, 2160]
DEFAULT_QUALITY: int = 480

CONFIG_DIR: Path = Path.home() / ".config" / "opendl"
CONFIG_FILE: Path = CONFIG_DIR / "config.json"
COOKIES_DEFAULT: Path = Path.home() / "cookies.txt"
ENCRYPTED_COOKIES_FILE: Path = CONFIG_DIR / "cookies.enc"
DOWNLOAD_DIR_DEFAULT: Path = Path.home() / "Downloads" / "opendl"
LOG_FILE: Path = CONFIG_DIR / "opendl.log"

BATCH_SIZE: int = 5
PBKDF2_ITERATIONS: int = 390_000
MAX_PASSWORD_ATTEMPTS: int = 3
MAX_LOG_LINES: int = 300
ODL_VERSION: str = "1.9.0"

# فارسی: زنجیره‌ی کلاینت‌های پخش یوتیوب برای امتحان خودکار در صورت شکست
# English: chain of YouTube playback clients to try automatically on failure
PLAYER_CLIENT_FALLBACK_CHAIN: list[str] = ["web", "android", "mweb", "ios", "tv"]

# فارسی: نام دسته‌های ممکن برای خطاهای دانلود (برای خلاصه‌ی بهتر و تصمیم retry)
# English: possible categories for download errors (for a better summary and retry decisions)
class ErrorCategory:
    REGION_LOCKED = "Region Locked"
    AGE_RESTRICTED = "Age Restricted"
    PRIVATE_VIDEO = "Private"
    DELETED_VIDEO = "Deleted/Unavailable"
    MEMBERS_ONLY = "Members Only"
    LOGIN_REQUIRED = "Login Required"
    BOT_DETECTED = "Bot Detection"
    NETWORK_ERROR = "Network Error"
    PROXY_ERROR = "Proxy Error"
    COOKIE_INVALID = "Cookie Invalid"
    UNKNOWN = "Unknown"


# فارسی: فقط این دسته‌ها با تعویض کلاینت پخش احتمال حل‌شدن دارن؛ بقیه (مثل
#        Region یا Private) ربطی به کلاینت ندارن و retry اضافی فقط وقت تلف می‌کنه.
# English: only these categories have a real chance of being fixed by
#          switching playback clients; others (e.g. Region, Private) are
#          unrelated to the client and retrying would just waste time.
CLIENT_FALLBACK_RETRYABLE_CATEGORIES = {
    ErrorCategory.BOT_DETECTED,
    ErrorCategory.LOGIN_REQUIRED,
    ErrorCategory.UNKNOWN,
}

# فارسی: مسیرهای معمولی که فایل export‌شده‌ی دستیِ کوکی ممکنه در آن‌ها فرود بیاد
# English: common locations a manually exported cookie file might land in
COOKIE_SEARCH_PATHS: list[Path] = [
    Path.home() / "storage" / "downloads" / "cookies.txt",
    Path.home() / "storage" / "downloads" / "www.youtube.com_cookies.txt",
    Path.home() / "storage" / "downloads" / "youtube.com_cookies.txt",
    Path("/sdcard/Download/cookies.txt"),
    Path("/sdcard/Download/www.youtube.com_cookies.txt"),
    Path("/sdcard/Download/youtube.com_cookies.txt"),
]

# فارسی: مسیر پروفایل‌های فایرفاکس روی اندروید (فقط با دسترسی روت قابل‌خواندنه)
# English: Android Firefox profiles path (only readable with root access)
ANDROID_FIREFOX_PROFILES_DIR: Path = Path("/data/data/org.mozilla.firefox/files/mozilla")

# فارسی: نشانه‌هایی که وجودشون یعنی داریم روی اندروید اجرا می‌شیم، نه لینوکس دسکتاپ
# English: signals whose presence means we're running on Android, not desktop Linux
_ANDROID_MARKER_PATHS: list[Path] = [Path("/system/build.prop"), Path("/system/bin/getprop")]
_ANDROID_MARKER_ENV_VARS: list[str] = ["ANDROID_ROOT", "ANDROID_DATA", "TERMUX_VERSION"]

# فارسی: نوع تابع پاک‌سازی که بعد از استفاده از کوکی رمزگشایی‌شده صدا زده می‌شه
# English: type alias for the cleanup callback used after using a decrypted cookie file
CleanupFn = Callable[[], None]


# ---------------------------------------------------------------------------
# کانفیگ / Configuration
# ---------------------------------------------------------------------------

def load_config() -> dict:
    """
    فارسی: تنظیمات کاربر رو از فایل کانفیگ می‌خونه و با مقادیر پیش‌فرض ترکیب می‌کنه.
    English: Load user settings from the config file, merged with sane defaults.
    """
    defaults = {
        "cookies": str(COOKIES_DEFAULT),
        "quality": DEFAULT_QUALITY,
        "download_dir": str(DOWNLOAD_DIR_DEFAULT),
        "batch_size": BATCH_SIZE,
        "proxy": None,
        "player_client": None,
        "bypass": False,
    }
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                user_cfg = json.load(f)
            defaults.update(user_cfg)
        except Exception:
            # فارسی: اگه کانفیگ خراب بود، بی‌صدا از پیش‌فرض‌ها استفاده کن
            # English: fall back silently to defaults on a corrupt config file
            pass
    return defaults


def save_default_config() -> None:
    """
    فارسی: اگه فایل کانفیگ وجود نداشت، یک نسخه‌ی پیش‌فرض می‌سازه.
    English: Create a default config file if one doesn't already exist.
    """
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_FILE.exists():
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "cookies": str(COOKIES_DEFAULT),
                    "quality": DEFAULT_QUALITY,
                    "download_dir": str(DOWNLOAD_DIR_DEFAULT),
                    "batch_size": BATCH_SIZE,
                    "proxy": None,
                    "player_client": None,
                    "bypass": False,
                },
                f,
                ensure_ascii=False,
                indent=2,
            )


def rotate_log() -> None:
    """
    فارسی: فایل لاگ را برای جلوگیری از رشد بی‌رویه، به حداکثر MAX_LOG_LINES خط محدود می‌کند.
    English: Trim the log file to at most MAX_LOG_LINES lines to prevent unbounded growth.
    """
    if not LOG_FILE.exists():
        return
    try:
        lines = LOG_FILE.read_text(encoding="utf-8").splitlines()
        if len(lines) > MAX_LOG_LINES:
            with open(LOG_FILE, "w", encoding="utf-8") as f:
                f.write("\n".join(lines[-MAX_LOG_LINES:]) + "\n")
    except Exception:
        # فارسی: چرخش لاگ حیاتی نیست، اگه شکست خورد بی‌صدا رد شو
        # English: log rotation isn't critical, fail silently if it errors
        pass


# ---------------------------------------------------------------------------
# دریافت خودکار کوکی بر اساس محیط اجرا / Environment-aware automatic cookies
# ---------------------------------------------------------------------------

def is_desktop_linux() -> bool:
    """
    فارسی: تشخیص می‌ده که آیا روی یک لینوکس دسکتاپ/سرور معمولی اجرا می‌شیم
           (نه اندروید/Termux)، تا بشه از دسترسی مستقیم به مرورگر استفاده کرد.
    English: Detect whether we're on a regular desktop/server Linux (not
             Android/Termux), so we can use direct browser-profile access.
    """
    if not sys.platform.startswith("linux"):
        return False
    if any(path.exists() for path in _ANDROID_MARKER_PATHS):
        return False
    if any(os.environ.get(var) for var in _ANDROID_MARKER_ENV_VARS):
        return False
    return True


def _extract_via_ytdlp_browser(browser: str) -> Optional[str]:
    """
    فارسی: با قابلیت داخلی yt-dlp، کوکی‌ها را مستقیم از پروفایل مرورگر
           دسکتاپ (فایرفاکس یا کروم/کرومیوم) می‌خواند و به متن Netscape تبدیل می‌کند.
    English: Use yt-dlp's built-in reader to pull cookies directly from a
             desktop browser profile (Firefox or Chrome/Chromium) and
             convert them to Netscape-format text.
    """
    try:
        from yt_dlp.cookies import extract_cookies_from_browser
    except ImportError:
        return None

    try:
        jar = extract_cookies_from_browser(browser)
    except Exception:
        return None

    if jar is None or len(jar) == 0:
        return None

    # فارسی: mktemp به‌خاطر race condition ناامنه؛ به‌جاش از mkstemp استفاده می‌کنیم
    # English: mktemp has a race-condition risk; use mkstemp instead
    fd, tmp_path_str = tempfile.mkstemp(suffix=".txt")
    os.close(fd)
    tmp_path = Path(tmp_path_str)
    try:
        jar.save(str(tmp_path), ignore_discard=True, ignore_expires=True)
        return tmp_path.read_text(encoding="utf-8")
    except Exception:
        return None
    finally:
        tmp_path.unlink(missing_ok=True)


def find_android_firefox_profile() -> Optional[Path]:
    """
    فارسی: اگه بشه مستقیم (مثلاً با روت) به دیتابیس کوکی فایرفاکس اندروید
           خوندن دسترسی داشت، مسیر پوشه‌ی پروفایل را برمی‌گرداند؛ در غیر
           این‌صورت None (که یعنی باید به مسیر دستی برگردیم).
    English: If the Android Firefox cookie database is directly readable
             (e.g. with root), return the profile folder's path; otherwise
             return None (meaning we must fall back to the manual path).
    """
    try:
        if not ANDROID_FIREFOX_PROFILES_DIR.exists():
            return None
        for profile in sorted(ANDROID_FIREFOX_PROFILES_DIR.glob("*.default*")):
            cookie_db = profile / "cookies.sqlite"
            if profile.is_dir() and cookie_db.exists() and os.access(cookie_db, os.R_OK):
                return profile
    except PermissionError:
        return None
    return None


def _extract_via_android_firefox(profile_dir: Path) -> Optional[str]:
    """
    فارسی: کوکی‌های یوتیوب/گوگل را مستقیم از دیتابیس SQLite فایرفاکس اندروید
           می‌خواند و به فرمت Netscape تبدیل می‌کند. چون فایرفاکس ممکنه
           هم‌زمان دیتابیس را باز نگه داشته باشه، ابتدا از آن یک کپی موقت
           می‌گیریم تا خطای «database is locked» رخ ندهد.
    English: Read YouTube/Google cookies directly from the Android Firefox
             SQLite database and convert them to Netscape format. Since
             Firefox may keep the database open, we first copy it to a
             temp file to avoid a "database is locked" error.
    """
    cookie_db = profile_dir / "cookies.sqlite"
    fd, tmp_copy_str = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    tmp_copy = Path(tmp_copy_str)
    try:
        shutil.copy(cookie_db, tmp_copy)
        conn = sqlite3.connect(str(tmp_copy))
        try:
            rows = conn.execute(
                "SELECT host, path, isSecure, expiry, name, value FROM moz_cookies "
                "WHERE host LIKE '%youtube.com%' OR host LIKE '%google.com%'"
            ).fetchall()
        finally:
            conn.close()
    except Exception:
        return None
    finally:
        tmp_copy.unlink(missing_ok=True)

    if not rows:
        return None

    lines = [
        "# Netscape HTTP Cookie File",
        "# Generated automatically by Open Downloader CLI (odl) from the Android Firefox profile.",
        "",
    ]
    for host, path, is_secure, expiry, name, value in rows:
        domain_specified = "TRUE" if host.startswith(".") else "FALSE"
        secure_flag = "TRUE" if is_secure else "FALSE"
        expiry_value = str(int(expiry)) if expiry else "0"
        lines.append("\t".join([host, domain_specified, path or "/", secure_flag, expiry_value, name, value]))
    return "\n".join(lines) + "\n"


def try_automatic_cookie_import(force: bool = False) -> bool:
    """
    فارسی:
        به ترتیب اولویت، روش‌های کاملاً خودکارِ دریافت کوکی را امتحان می‌کند:
          ۱. لینوکس دسکتاپ: خواندن مستقیم از پروفایل فایرفاکس یا کروم/کرومیوم.
          ۲. اندروید با دسترسی مستقیم (روت یا معادل آن): خواندن مستقیم از
             دیتابیس فایرفاکس اندروید.
        اگه هیچ‌کدام ممکن نبود (مثلاً اندروید بدون روت)، False برمی‌گرداند
        تا مسیر نیمه‌خودکار/دستی و راهنمای قدم‌به‌قدم اجرا شود.
        اگه از قبل یک فایل کوکی رمزنگاری‌شده وجود داشته باشه، این تابع کاری
        انجام نمی‌ده (مگر force=True باشه، یعنی کاربر صریحاً با
        --import-cookies خواسته دوباره از نو کوکی بگیره)؛ این جلوی
        رمزنگاری مجدد ناخواسته و پرسیدن رمز جدید در هر اجرا را می‌گیرد.

    English:
        In priority order, try fully automatic cookie retrieval methods:
          1. Desktop Linux: read directly from a Firefox or Chrome/Chromium
             profile.
          2. Android with direct read access (root or equivalent): read
             directly from the Android Firefox database.
        Returns False if neither worked (e.g. non-rooted Android), so the
        semi-automatic/manual path and step-by-step guide run instead.
        If an encrypted cookie file already exists, this function does
        nothing (unless force=True, i.e. the user explicitly asked for a
        fresh import via --import-cookies); this prevents unwanted
        re-encryption and a new password prompt on every single run.

    Returns:
        True if cookies were imported automatically, False otherwise.
    """
    if COOKIES_DEFAULT.exists():
        return False
    if ENCRYPTED_COOKIES_FILE.exists() and not force:
        return False

    if is_desktop_linux():
        for browser in ("firefox", "chrome", "chromium"):
            content = _extract_via_ytdlp_browser(browser)
            if content:
                COOKIES_DEFAULT.write_text(content, encoding="utf-8")
                console.print(
                    f"[green]✔ Cookies imported automatically from your {browser.capitalize()} profile.[/green]"
                )
                return True
        return False

    profile_dir = find_android_firefox_profile()
    if profile_dir:
        content = _extract_via_android_firefox(profile_dir)
        if content:
            COOKIES_DEFAULT.write_text(content, encoding="utf-8")
            console.print("[green]✔ Cookies imported automatically (root access detected).[/green]")
            return True

    return False


def find_and_import_cookies_automatically(force: bool = False) -> bool:
    """
    فارسی:
        روش نیمه‌خودکار (سطح دوم اولویت): اگه cookies.txt هنوز توی مسیر
        اصلی نباشه، مسیرهای معمولِ export دستی (مثل پوشه‌ی Download گوشی)
        را چک می‌کند؛ اگه پیدا شد، خودکار به مسیر اصلی کپی می‌کند. اگه از
        قبل یک فایل کوکی رمزنگاری‌شده وجود داشته باشه، کاری نمی‌کند (مگر
        force=True باشه).

    English:
        Semi-automatic method (second priority): if cookies.txt isn't
        already at its main location, check common manual-export locations
        (e.g. the phone's Download folder); if found, copy it in
        automatically. If an encrypted cookie file already exists, this
        does nothing (unless force=True).

    Returns:
        True if a file was found and imported, False otherwise.
    """
    if COOKIES_DEFAULT.exists():
        return False
    if ENCRYPTED_COOKIES_FILE.exists() and not force:
        return False

    for candidate in COOKIE_SEARCH_PATHS:
        if candidate.exists() and candidate.is_file():
            try:
                shutil.copy(candidate, COOKIES_DEFAULT)
            except Exception:
                continue
            console.print(f"[green]✔ Found an exported cookie file at {candidate} and imported it automatically.[/green]")
            return True

    return False


def print_cookie_export_guide() -> None:
    """
    فارسی: راهنمای کامل و شماره‌گذاری‌شده برای export دستی کوکی یوتیوب را
           چاپ می‌کند؛ فقط وقتی نشان داده می‌شود که هیچ روش خودکاری جواب
           نداده باشد.
    English: Print a full, numbered, step-by-step guide for manually
             exporting YouTube cookies; only shown when no automatic
             method has succeeded.
    """
    console.print(
        "\n"
        "[bold yellow]No cookies found yet — here's how to set them up manually:[/bold yellow]\n\n"
        "  [bold]1.[/bold] Open Firefox on your phone and sign in to youtube.com\n"
        "     with your Google account (a secondary account is recommended).\n"
        "  [bold]2.[/bold] Watch a couple of videos so the account looks naturally active.\n"
        "  [bold]3.[/bold] Install the 'cookies.txt' add-on from Firefox add-ons\n"
        "     (addons.mozilla.org, search 'cookies.txt').\n"
        "  [bold]4.[/bold] While still on youtube.com, tap the add-on icon and export/\n"
        "     download the cookies — it saves a file named something like\n"
        "     'cookies.txt' or 'www.youtube.com_cookies.txt' to your Downloads folder.\n"
        "  [bold]5.[/bold] Just run odl again with any video or playlist link —\n"
        "     it will automatically find that file, ask you to set a master\n"
        "     password, encrypt it, and continue your download.\n"
    )


# ---------------------------------------------------------------------------
# رمزنگاری کوکی / Cookie encryption
# ---------------------------------------------------------------------------

def _require_crypto() -> None:
    """
    فارسی: اگه کتابخونه‌ی cryptography نصب نباشه، با پیام واضح خروج می‌کنه.
    English: Exit with a clear message if the cryptography library is missing.
    """
    if not CRYPTO_AVAILABLE:
        console.print("[red]The 'cryptography' library is not installed.[/red]")
        console.print("Install it with: pip install cryptography --break-system-packages")
        sys.exit(1)


def derive_key(password: str, salt: bytes) -> bytes:
    """
    فارسی: از رمز اصلی و یک salt، کلید رمزنگاری AES (از طریق Fernet) می‌سازه.
    English: Derive an AES encryption key (via Fernet) from a master password and salt.
    """
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
    )
    return base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))


def _prompt_new_master_password() -> str:
    """
    فارسی: رمز اصلی جدید رو دوبار می‌پرسه تا از عدم اشتباه تایپی مطمئن بشه.
    English: Prompt twice for a new master password to guard against typos.
    """
    while True:
        pw1 = getpass.getpass("Master password: ")
        pw2 = getpass.getpass("Confirm master password: ")
        if not pw1:
            console.print("[red]Password cannot be empty. Try again.[/red]")
            continue
        if pw1 != pw2:
            console.print("[red]Passwords do not match. Try again.[/red]")
            continue
        return pw1


def secure_cookies_setup(auto: bool = False) -> Tuple[Optional[str], CleanupFn]:
    """
    فارسی:
        رمزنگاری فایل cookies.txt موجود با یک رمز اصلی (که هیچ‌جا ذخیره نمی‌شه).
        اگه auto=True باشه، یعنی این تابع به‌صورت خودکار و اجباری، قبل از هر
        دستور دیگه صدا زده شده. در هر دو حالت، فایل متن‌ساده همیشه (بدون
        استثنا) بعد از رمزنگاری موفق حذف می‌شه.
        در حالت auto، برای این‌که رمز اصلی دوباره پرسیده نشه، همون دیتای
        رمزگشایی‌شده رو مستقیم برای همین اجرا برمی‌گردونه.

    English:
        Encrypt the existing cookies.txt file using a master password (never
        stored anywhere). If auto=True, this function was invoked
        automatically and mandatorily before another command ran. In both
        cases the plaintext file is always deleted after a successful
        encryption. In auto mode, the just-encrypted data is handed back
        directly for the current run, so the master password isn't asked
        for twice.

    Returns:
        (decrypted_cookie_path_or_None, cleanup_function)
    """
    _require_crypto()

    if not COOKIES_DEFAULT.exists():
        if not auto:
            console.print(f"[red]File {COOKIES_DEFAULT} not found. Export your cookies first.[/red]")
        return None, (lambda: None)

    if auto:
        console.print(
            "\n[bold yellow]⚠ A plaintext cookie file was found.[/bold yellow] "
            "For your account's safety, it must be protected with a password before use:\n\n"
            "  [bold]1.[/bold] Choose a master password below (anything you'll remember).\n"
            "  [bold]2.[/bold] Type it again to confirm there's no typo.\n"
            "  [bold]3.[/bold] The app encrypts the file and deletes the plaintext copy.\n"
            "  [bold]4.[/bold] From now on, odl will ask for this same password each time\n"
            "     it needs to use your cookies — it is never saved anywhere.\n"
        )
    console.print(
        "[cyan]Choose a master password (it is never stored anywhere — only you will know it).[/cyan]"
    )

    master_password = _prompt_new_master_password()

    salt = os.urandom(16)
    key = derive_key(master_password, salt)
    fernet = Fernet(key)
    plain_data = COOKIES_DEFAULT.read_bytes()
    token = fernet.encrypt(plain_data)

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "salt": base64.b64encode(salt).decode("ascii"),
        "data": token.decode("ascii"),
        "imported_at": time.time(),
    }
    with open(ENCRYPTED_COOKIES_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f)
    os.chmod(ENCRYPTED_COOKIES_FILE, 0o600)

    # فارسی: حذف اجباری فایل متن‌ساده — بدون استثنا، بدون سؤال
    # English: mandatory deletion of the plaintext file — no exceptions, no prompt
    COOKIES_DEFAULT.unlink()

    console.print("[green]✔ Cookie file encrypted and plaintext file deleted.[/green]")

    if not auto:
        return None, (lambda: None)

    console.print("[cyan]Continuing command...[/cyan]")

    # فارسی: همون دیتایی که همین الان رمزنگاری کردیم رو مستقیم برای همین
    #        اجرا استفاده می‌کنیم تا رمز اصلی دوباره پرسیده نشه.
    # English: reuse the plaintext we already have in memory for this run,
    #          instead of asking for the master password a second time.
    return _write_temp_cookie_file(plain_data)


def _write_temp_cookie_file(data: bytes) -> Tuple[str, CleanupFn]:
    """
    فارسی: دیتای کوکی رو در یک فایل موقت با دسترسی محدود (600) می‌نویسه.
    English: Write cookie data to a temporary file with restricted (600) permissions.
    """
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix="_odl_cookies.txt")
    try:
        tmp.write(data)
    finally:
        tmp.close()
    os.chmod(tmp.name, 0o600)

    def cleanup() -> None:
        try:
            os.unlink(tmp.name)
        except FileNotFoundError:
            pass

    return tmp.name, cleanup


def print_cookie_status() -> None:
    """
    فارسی: وضعیت فعلی کوکی (رمزنگاری‌شده/متن‌ساده/عدم‌وجود) و زمان import آن را نشان می‌دهد.
    English: Show the current cookie status (encrypted/plaintext/none) and when it was imported.
    """
    table = Table(show_header=False, box=None)
    if ENCRYPTED_COOKIES_FILE.exists():
        table.add_row("[bold]Status[/bold]", "[green]Encrypted[/green]")
        try:
            with open(ENCRYPTED_COOKIES_FILE, "r", encoding="utf-8") as f:
                payload = json.load(f)
            imported_at = payload.get("imported_at")
            if imported_at:
                age_days = (time.time() - imported_at) / 86400
                imported_str = time.strftime("%Y-%m-%d %H:%M", time.localtime(imported_at))
                table.add_row("[bold]Imported at[/bold]", f"{imported_str} ({age_days:.1f} days ago)")
            else:
                table.add_row("[bold]Imported at[/bold]", "unknown (older file, no timestamp saved)")
        except Exception:
            table.add_row("[bold]Note[/bold]", "[yellow]Could not read metadata[/yellow]")
    elif COOKIES_DEFAULT.exists():
        table.add_row("[bold]Status[/bold]", "[yellow]Plaintext (not yet encrypted)[/yellow]")
    else:
        table.add_row("[bold]Status[/bold]", "[red]No cookies found[/red]")
    console.print(Panel(table, title="Cookie Status", border_style="cyan"))


def reset_encrypted_cookies() -> None:
    """
    فارسی: فایل کوکی رمزنگاری‌شده را برای همیشه حذف می‌کند (بازنشانی کامل).
    English: Permanently delete the encrypted cookie file (a full reset).
    """
    if ENCRYPTED_COOKIES_FILE.exists():
        ENCRYPTED_COOKIES_FILE.unlink()
        console.print("[green]✔ Encrypted cookie file removed.[/green]")
    else:
        console.print("[yellow]There is no encrypted cookie file to remove.[/yellow]")
    print_cookie_export_guide()


def resolve_cookies_path(cfg: dict) -> Tuple[Optional[str], CleanupFn]:
    """
    فارسی:
        اگه نسخه‌ی رمزنگاری‌شده‌ی کوکی وجود داشته باشه، رمز اصلی رو می‌پرسه،
        به یک فایل موقت رمزگشایی می‌کنه و مسیرش رو برمی‌گردونه. تا سقف
        MAX_PASSWORD_ATTEMPTS بار اجازه‌ی تلاش دوباره داده می‌شه؛ اگه همه‌ی
        تلاش‌ها با رمز اشتباه شکست بخوره، از کاربر می‌پرسه که آیا رمز رو
        فراموش کرده و می‌خواد فایل رمزنگاری‌شده بازنشانی (حذف) بشه. اگه
        هیچ فایل رمزنگاری‌شده‌ای وجود نداشت، به یک cookies.txt معمولی
        (نامرمزنگاری‌شده) برمی‌گردد، اگر موجود باشد.

    English:
        If an encrypted cookie file exists, prompt for the master password
        and decrypt it into a temp file, returning its path. The user gets
        up to MAX_PASSWORD_ATTEMPTS tries; if all attempts fail, they're
        asked whether they forgot the password and want to reset (delete)
        the encrypted file. Falls back to a plain (unencrypted) cookies.txt
        if no encrypted file exists.

    Returns:
        (cookie_path_or_None, cleanup_function)
    """
    if ENCRYPTED_COOKIES_FILE.exists():
        _require_crypto()
        try:
            with open(ENCRYPTED_COOKIES_FILE, "r", encoding="utf-8") as f:
                payload = json.load(f)
            salt = base64.b64decode(payload["salt"])
            token = payload["data"].encode("ascii")
        except Exception as e:
            console.print(f"[red]Error reading the encrypted cookie file: {e}[/red]")
            sys.exit(1)

        for attempt in range(1, MAX_PASSWORD_ATTEMPTS + 1):
            password = getpass.getpass("Cookie master password: ")
            key = derive_key(password, salt)
            fernet = Fernet(key)
            try:
                data = fernet.decrypt(token)
                return _write_temp_cookie_file(data)
            except InvalidToken:
                remaining = MAX_PASSWORD_ATTEMPTS - attempt
                if remaining > 0:
                    console.print(f"[red]Wrong password. {remaining} attempt(s) left.[/red]")

        # فارسی: بعد از اتمام همه‌ی تلاش‌ها، گزینه‌ی بازنشانی رو پیشنهاد بده
        # English: after all attempts are exhausted, offer to reset
        console.print("[red]Maximum password attempts reached.[/red]")
        if Confirm.ask(
            "Did you forget the password? Reset the encrypted cookie file and start fresh?",
            default=False,
        ):
            reset_encrypted_cookies()
            return None, (lambda: None)

        sys.exit(1)

    plain_path = Path(cfg["cookies"])
    if plain_path.exists():
        return str(plain_path), (lambda: None)

    return None, (lambda: None)


# ---------------------------------------------------------------------------
# توابع کمکی / Helper functions
# ---------------------------------------------------------------------------

def classify_error(message: str) -> str:
    """
    فارسی: پیام خطای yt-dlp را بر اساس محتوای متنش به یک دسته‌ی قابل‌فهم
           (مثل Region Locked یا Bot Detection) طبقه‌بندی می‌کند. این برای
           خلاصه‌ی نهایی و تصمیم‌گیری درباره‌ی تلاش دوباره با کلاینت دیگر استفاده می‌شود.
    English: Classify a yt-dlp error message into a human-friendly category
             (e.g. Region Locked, Bot Detection) based on its text content.
             Used for the final summary and for deciding whether a
             player-client retry is worth attempting.
    """
    m = message.lower()
    if "not available in your country" in m or "not made this video available" in m:
        return ErrorCategory.REGION_LOCKED
    if "age" in m and ("restrict" in m or "confirm" in m and "birthday" in m):
        return ErrorCategory.AGE_RESTRICTED
    if "private video" in m:
        return ErrorCategory.PRIVATE_VIDEO
    if "video has been removed" in m or "no longer available" in m or "video unavailable" in m:
        return ErrorCategory.DELETED_VIDEO
    if "members-only" in m or "members only" in m or "join this channel" in m:
        return ErrorCategory.MEMBERS_ONLY
    if "confirm you" in m and "not a bot" in m:
        return ErrorCategory.BOT_DETECTED
    if "sign in" in m or "login" in m:
        return ErrorCategory.LOGIN_REQUIRED
    if "proxy" in m:
        return ErrorCategory.PROXY_ERROR
    if "cookie" in m:
        return ErrorCategory.COOKIE_INVALID
    if "timed out" in m or "temporary failure in name resolution" in m or "connection" in m:
        return ErrorCategory.NETWORK_ERROR
    return ErrorCategory.UNKNOWN


def build_format(quality: int) -> str:
    """
    فارسی: رشته‌ی فرمت yt-dlp رو بر اساس سقف کیفیت انتخابی می‌سازه.
    English: Build the yt-dlp format string for a given max resolution.
    """
    return f"bestvideo[height<={quality}]+bestaudio/best[height<={quality}]"


def is_youtube_url(url: str) -> bool:
    """
    فارسی: بررسی سطحی می‌کنه که آیا لینک متعلق به یوتیوبه یا نه.
    English: Loosely check whether the given URL belongs to YouTube.
    """
    return any(domain in url for domain in ("youtube.com", "youtu.be"))


def human_size(num_bytes: Optional[float]) -> str:
    """
    فارسی: تعداد بایت رو به یک رشته‌ی خوانا (مثل «۱۲.۳ MB») تبدیل می‌کنه.
    English: Convert a byte count into a human-readable string (e.g. "12.3 MB").
    """
    if not num_bytes:
        return "unknown"
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


def resolve_video_url(entry: dict) -> Optional[str]:
    """
    فارسی: از یک entry برگشتی حالت flat-playlist، لینک کامل ویدیو رو می‌سازه.
    English: Build a full video URL from a flat-playlist entry dict.
    """
    video_id = entry.get("id")
    if video_id:
        return f"https://www.youtube.com/watch?v={video_id}"
    url = entry.get("url")
    if url:
        return url if url.startswith("http") else f"https://www.youtube.com/watch?v={url}"
    return None


def build_extractor_args(cfg: dict, bypass: bool = False) -> dict:
    """
    فارسی:
        تنظیمات پیشرفته‌ی extractor_args یوتیوب را می‌سازد.
        - همیشه چک احراز هویتی که با IP های مشکوک (مثل Tor) فعال می‌شه رد می‌شود.
        - اگه bypass=True باشه (فلگ --bypass)، دانلود دادهٔ کمتری از یوتیوب
          می‌خواند (رد شدن از دانلود صفحه‌ی وب و کانفیگ‌های اضافی) که
          سریع‌تره ولی ممکنه بعضی فرمت‌ها یا زیرنویس‌ها را از دست بدهد.
        - اگه player_client توی کانفیگ تنظیم شده باشه (مثلاً "android")،
          یوتیوب را وادار می‌کند از همان کلاینت پخش استفاده کند؛ این روش
          برای دور زدن تشخیص بات مفید است (همان ترفندی که قبلاً روی این
          پروژه امتحان و تأیید شد).

    English:
        Build advanced YouTube extractor_args.
        - Always skips the auth-check that can trigger with suspicious IPs
          (e.g. Tor).
        - If bypass=True (the --bypass flag), fetch less data from YouTube
          (skip the webpage/extra-configs downloads) — faster, but may miss
          some formats or subtitles.
        - If player_client is set in the config (e.g. "android"), force
          YouTube to use that playback client; this is useful for working
          around bot detection (the same trick already proven earlier in
          this project).
    """
    args: dict = {"youtubetab": {"skip": ["authcheck"]}}

    if bypass:
        args["youtubetab"]["skip"].append("webpage")
        args["youtube"] = {"player_skip": ["webpage", "configs"]}

    if cfg.get("player_client"):
        clients = [c.strip() for c in cfg["player_client"].split(",") if c.strip()]
        args.setdefault("youtube", {})["player_client"] = clients

    return args


def ydl_opts_base(
    cookies_path: Optional[str],
    quality: int,
    sub_en: bool,
    sub_fa: bool,
    out_template: str,
    audio_only: bool,
    proxy: Optional[str],
    extractor_args: dict,
) -> dict:
    """
    فارسی: دیکشنری تنظیمات مشترک yt-dlp رو برای همه‌ی انواع دانلود می‌سازه.
    English: Build the shared yt-dlp options dict used by every download kind.
    """
    opts = {
        "format": "bestaudio/best" if audio_only else build_format(quality),
        "outtmpl": out_template,
        "continuedl": True,  # فارسی: پشتیبانی از رزیوم / English: enables resume support
        "retries": "infinite",
        "fragment_retries": "infinite",
        "noprogress": True,  # فارسی: خودمون UI رو مدیریت می‌کنیم / English: we render our own UI
        "quiet": True,
        "no_warnings": True,
        "ignoreerrors": True,
        "extractor_args": extractor_args,
    }
    if cookies_path:
        opts["cookiefile"] = cookies_path
    if proxy:
        opts["proxy"] = proxy

    postprocessors = []
    if audio_only:
        postprocessors.append(
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        )

    langs = []
    if sub_en:
        langs.append("en")
    if sub_fa:
        langs.append("fa")
    if langs:
        opts["writesubtitles"] = True
        opts["subtitleslangs"] = langs
        opts["subtitlesformat"] = "srt"
        postprocessors.append({"key": "FFmpegSubtitlesConvertor", "format": "srt"})

    if postprocessors:
        opts["postprocessors"] = postprocessors

    return opts


def log_error(url: str, message: str) -> None:
    """
    فارسی: خطای دانلود یک لینک رو با زمان‌مهر به فایل لاگ اضافه می‌کنه و لاگ رو می‌چرخاند.
    English: Append a timestamped download error for a URL to the log file and rotate it.
    """
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {url} -> {message}\n")
    rotate_log()


# ---------------------------------------------------------------------------
# دانلود تکی / Single video download
# ---------------------------------------------------------------------------

def download_single(
    url: str,
    cookies_path: Optional[str],
    quality: int,
    sub_en: bool,
    sub_fa: bool,
    out_dir: str,
    audio_only: bool,
    proxy: Optional[str],
    extractor_args: dict,
    allow_client_fallback: bool,
) -> bool:
    """
    فارسی: یک ویدیوی تکی رو با نوار پیشرفت زنده دانلود می‌کنه. اگه با یک
           کلاینت پخش خاص شکست بخوره و خطا از نوع قابل‌حل با تعویض کلاینت
           باشد (و کاربر خودش صریحاً کلاینت را انتخاب نکرده باشد)، به‌ترتیب
           کلاینت‌های دیگر را هم امتحان می‌کند.
    English: Download a single video with a live progress bar. If it fails
             with a particular playback client and the error looks fixable
             by switching clients (and the user hasn't explicitly forced a
             client), other clients are tried in order automatically.
    """
    if not is_youtube_url(url):
        console.print("[red]This does not look like a valid YouTube URL.[/red]")
        return False

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    out_template = str(out_path / "%(title)s.%(ext)s")

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.fields[title]}"),
        BarColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task_id = progress.add_task("download", title="Fetching info...", total=None)

        def hook(d: dict) -> None:
            # فارسی: کال‌بک زنده‌ی yt-dlp برای آپدیت نوار پیشرفت
            # English: yt-dlp's live callback used to update the progress bar
            if d["status"] == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate")
                downloaded = d.get("downloaded_bytes", 0)
                if total:
                    progress.update(task_id, total=total, completed=downloaded)
                info = d.get("info_dict") or {}
                title = info.get("title")
                if title:
                    progress.update(task_id, title=title[:40])
            elif d["status"] == "finished":
                progress.update(task_id, title="Finalizing (merge)...")

        def attempt(current_extractor_args: dict) -> Tuple[bool, Optional[str]]:
            opts = ydl_opts_base(
                cookies_path, quality, sub_en, sub_fa, out_template, audio_only, proxy, current_extractor_args
            )
            opts["progress_hooks"] = [hook]
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    ydl.download([url])
                return True, None
            except Exception as e:
                if DEBUG:
                    console.print("[red]--- DEBUG: full traceback ---[/red]")
                    traceback.print_exc()
                return False, str(e)

        ok, err = attempt(extractor_args)

        if not ok and allow_client_fallback:
            category = classify_error(err or "")
            if category in CLIENT_FALLBACK_RETRYABLE_CATEGORIES:
                for client in PLAYER_CLIENT_FALLBACK_CHAIN:
                    progress.update(task_id, title=f"Retrying with '{client}' client...")
                    fallback_args = dict(extractor_args)
                    fallback_args["youtube"] = {"player_client": [client]}
                    ok, err = attempt(fallback_args)
                    if ok:
                        break

        if ok:
            progress.update(task_id, title="[green]✔ Done[/green]")
            return True

        console.print(f"[red]Download error ({classify_error(err or '')}): {err}[/red]")
        log_error(url, err or "unknown error")
        return False


# ---------------------------------------------------------------------------
# دانلود پلی‌لیست / Playlist download
# ---------------------------------------------------------------------------

def fetch_playlist_entries(
    url: str, cookies_path: Optional[str], proxy: Optional[str], extractor_args: dict
) -> Tuple[list, str]:
    """
    فارسی: لیست ویدیوهای یک پلی‌لیست و نام آن را (بدون دانلود) برمی‌گرداند.
    English: Fetch a playlist's video entries and its title without downloading.
    """
    opts = {
        "extract_flat": True,
        "quiet": True,
        "no_warnings": True,
        "extractor_args": extractor_args,
    }
    if cookies_path:
        opts["cookiefile"] = cookies_path
    if proxy:
        opts["proxy"] = proxy

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)

    entries = [e for e in (info.get("entries", []) if info else []) if e]
    title = info.get("title", "playlist") if info else "playlist"
    return entries, title


def estimate_size(
    url: str,
    cookies_path: Optional[str],
    quality: int,
    audio_only: bool,
    proxy: Optional[str],
    extractor_args: dict,
) -> int:
    """
    فارسی: بدون دانلود واقعی، حجم تقریبی یک ویدیو را برمی‌گرداند.
    English: Return a video's approximate file size without actually downloading it.
    """
    opts = {
        "format": "bestaudio/best" if audio_only else build_format(quality),
        "quiet": True,
        "no_warnings": True,
        "simulate": True,
        "extractor_args": extractor_args,
    }
    if cookies_path:
        opts["cookiefile"] = cookies_path
    if proxy:
        opts["proxy"] = proxy
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
        return info.get("filesize") or info.get("filesize_approx") or 0
    except Exception:
        # فارسی: اگه حجم یک ویدیو قابل تخمین نبود، صفر برگردون و ادامه بده
        # English: if a single video's size can't be estimated, return 0 and continue
        return 0


def _print_playlist_summary(
    playlist_title: str, count: int, quality: int, audio_only: bool,
    total_size: int, out_dir: str, proxy: Optional[str],
) -> None:
    """
    فارسی: جدول خلاصه‌ی اطلاعات پلی‌لیست را قبل از شروع دانلود نمایش می‌دهد.
    English: Display the playlist summary table before downloads start.
    """
    table = Table(show_header=False, box=None)
    table.add_row("[bold]Playlist name[/bold]", playlist_title)
    table.add_row("[bold]Video count[/bold]", str(count))
    table.add_row("[bold]Quality[/bold]", "audio (mp3)" if audio_only else f"{quality}p")
    table.add_row("[bold]Estimated total size[/bold]", human_size(total_size))
    table.add_row("[bold]Save path[/bold]", str(out_dir))
    if proxy:
        table.add_row("[bold]Proxy[/bold]", proxy)
    console.print(Panel(table, title="Playlist Info", border_style="green"))


def download_playlist(
    url: str,
    cookies_path: Optional[str],
    quality: int,
    sub_en: bool,
    sub_fa: bool,
    out_dir: str,
    audio_only: bool,
    batch_size: int,
    proxy: Optional[str],
    extractor_args: dict,
    allow_client_fallback: bool,
    skip_estimate: bool,
) -> None:
    """
    فارسی: کل پلی‌لیست را پس از تأیید کاربر، دسته‌به‌دسته (batch) دانلود می‌کند.
    English: Download an entire playlist in batches, after user confirmation.
    """
    console.print("[cyan]Fetching video list...[/cyan]")
    try:
        entries, playlist_title = fetch_playlist_entries(url, cookies_path, proxy, extractor_args)
    except Exception as e:
        console.print(f"[red]Error fetching the playlist: {e}[/red]")
        console.print("[yellow]The cookie may have expired, or the current exit node is blocked.[/yellow]")
        log_error(url, str(e))
        return

    if not entries:
        console.print("[red]No videos found in this playlist.[/red]")
        return

    count = len(entries)

    total_size = 0
    if skip_estimate:
        console.print(f"[cyan]Size estimation skipped ({count} videos found).[/cyan]")
    else:
        console.print(f"[yellow]Estimating total size for {count} videos...[/yellow]")
        with Progress(SpinnerColumn(), TextColumn("Checking {task.completed}/{task.total}"), console=console) as p:
            check_task = p.add_task("check", total=count)
            for entry in entries:
                video_url = resolve_video_url(entry)
                if video_url:
                    total_size += estimate_size(video_url, cookies_path, quality, audio_only, proxy, extractor_args)
                p.update(check_task, advance=1)

    _print_playlist_summary(playlist_title, count, quality, audio_only, total_size, out_dir, proxy)

    if not Confirm.ask("Start the download?", default=True):
        console.print("[red]Cancelled.[/red]")
        return

    out_path = Path(out_dir) / playlist_title
    out_path.mkdir(parents=True, exist_ok=True)

    results: list[tuple[int, str, bool]] = []
    videos = [
        (i + 1, resolve_video_url(entry), entry.get("title") or "untitled")
        for i, entry in enumerate(entries)
    ]

    start_time = time.time()

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.fields[title]}"),
        BarColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:

        # فارسی: یک نوار پیشرفت کلی (X از کل، درصد) جدا از نوارهای هر ویدیو
        # English: an overall progress bar (X of total, percent) separate from per-video bars
        overall_task = progress.add_task("overall", title="[bold]Overall progress[/bold]", total=count)

        for batch_start in range(0, len(videos), batch_size):
            batch = videos[batch_start:batch_start + batch_size]
            task_ids: dict[int, int] = {}

            for idx, video_url, title in batch:
                short_title = (title[:35] + "...") if len(title) > 35 else title
                task_ids[idx] = progress.add_task("dl", title=f"[{idx}] {short_title}", total=None)

            def worker(idx: int, video_url: Optional[str], title: str, task_id: int) -> tuple[int, str, bool]:
                # فارسی: دانلود یک ویدیو در thread جدا، به‌صورت هم‌زمان با بقیه‌ی دسته
                # English: download a single video on its own thread, alongside the rest of the batch
                if not video_url:
                    progress.update(task_id, title=f"[red]✘ [{idx}] invalid URL[/red]")
                    progress.update(overall_task, advance=1)
                    return idx, title, False

                out_template = str(out_path / f"{idx:03d} - %(title)s.%(ext)s")
                short_title = (title[:35] + "...") if len(title) > 35 else title

                def hook(d: dict) -> None:
                    if d["status"] == "downloading":
                        total = d.get("total_bytes") or d.get("total_bytes_estimate")
                        downloaded = d.get("downloaded_bytes", 0)
                        if total:
                            progress.update(task_id, total=total, completed=downloaded)
                    elif d["status"] == "finished":
                        progress.update(task_id, title=f"[{idx}] processing...")

                def attempt(current_extractor_args: dict) -> Tuple[bool, Optional[str]]:
                    opts = ydl_opts_base(
                        cookies_path, quality, sub_en, sub_fa, out_template, audio_only, proxy, current_extractor_args
                    )
                    opts["progress_hooks"] = [hook]
                    try:
                        with yt_dlp.YoutubeDL(opts) as ydl:
                            ydl.download([video_url])
                        return True, None
                    except Exception as e:
                        if DEBUG:
                            traceback.print_exc()
                        return False, str(e)

                ok, err = attempt(extractor_args)

                if not ok and allow_client_fallback:
                    category = classify_error(err or "")
                    if category in CLIENT_FALLBACK_RETRYABLE_CATEGORIES:
                        for client in PLAYER_CLIENT_FALLBACK_CHAIN:
                            fallback_args = dict(extractor_args)
                            fallback_args["youtube"] = {"player_client": [client]}
                            ok, err = attempt(fallback_args)
                            if ok:
                                break

                progress.update(overall_task, advance=1)

                if ok:
                    progress.update(task_id, title=f"[green]✔ [{idx}] {short_title}[/green]")
                    return idx, title, True

                progress.update(task_id, title=f"[red]✘ [{idx}] {short_title}[/red]")
                log_error(video_url, err or "unknown error")
                return idx, title, False

            with concurrent.futures.ThreadPoolExecutor(max_workers=len(batch)) as executor:
                futures = [
                    executor.submit(worker, idx, video_url, title, task_ids[idx])
                    for idx, video_url, title in batch
                ]
                for future in concurrent.futures.as_completed(futures):
                    results.append(future.result())

    elapsed = time.time() - start_time
    _print_download_summary(results, count, elapsed, total_size if not skip_estimate else None)


def _print_download_summary(
    results: list[tuple[int, str, bool]],
    total_count: int,
    elapsed_seconds: Optional[float] = None,
    total_estimated_size: Optional[int] = None,
) -> None:
    """
    فارسی: جدول نتیجه‌ی نهایی دانلود پلی‌لیست را به همراه زمان سپری‌شده و سرعت میانگین چاپ می‌کند.
    English: Print the final results table for a playlist download, including elapsed time and average speed.
    """
    summary = Table(title="Download Summary")
    summary.add_column("#", justify="right")
    summary.add_column("Title")
    summary.add_column("Status", justify="center")
    for idx, title, ok in sorted(results, key=lambda r: r[0]):
        status = "[green]✔ success[/green]" if ok else "[red]✘ failed[/red]"
        short_title = (title[:50] + "...") if len(title) > 50 else title
        summary.add_row(str(idx), short_title, status)
    console.print(summary)

    success_count = sum(1 for _, _, ok in results if ok)
    console.print(f"\n[bold green]{success_count} of {total_count} videos downloaded successfully.[/bold green]")

    if elapsed_seconds:
        minutes, seconds = divmod(int(elapsed_seconds), 60)
        console.print(f"[cyan]Elapsed time: {minutes}m {seconds}s[/cyan]")
        if total_estimated_size:
            avg_speed = total_estimated_size / elapsed_seconds
            console.print(f"[cyan]Average speed: {human_size(avg_speed)}/s[/cyan]")

    if success_count < total_count:
        console.print(f"[yellow]See this log file for error details: {LOG_FILE}[/yellow]")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def run_check_update() -> None:
    """
    فارسی: فقط بررسی می‌کند که آیا نسخه‌ی جدیدتری از yt-dlp موجود است یا نه، بدون نصب.
    English: Only check whether a newer version of yt-dlp is available, without installing.
    """
    console.print("[cyan]Checking for a newer yt-dlp version (no changes will be made)...[/cyan]")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--dry-run", "-U", "yt-dlp", "--break-system-packages"],
            capture_output=True, text=True, timeout=60,
        )
        output = (result.stdout or "") + (result.stderr or "")
        if "Would install" in output:
            console.print("[yellow]A newer version of yt-dlp is available. Run 'odl --update' to install it.[/yellow]")
        elif result.returncode == 0:
            console.print("[green]yt-dlp is already up to date.[/green]")
        else:
            console.print("[yellow]Could not determine update status. Output below:[/yellow]")
            console.print(output.strip())
    except Exception as e:
        console.print(f"[red]Update check failed: {e}[/red]")


def run_update() -> None:
    """
    فارسی: yt-dlp را به آخرین نسخه آپدیت می‌کند.
    English: Update yt-dlp to its latest version.
    """
    console.print("[cyan]Updating yt-dlp...[/cyan]")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-U", "yt-dlp", "--break-system-packages"],
            capture_output=True, text=True, timeout=120,
        )
        console.print(result.stdout.strip())
        if result.returncode != 0:
            console.print(f"[red]{result.stderr.strip()}[/red]")
        else:
            console.print("[green]✔ yt-dlp updated successfully.[/green]")
    except Exception as e:
        console.print(f"[red]Update failed: {e}[/red]")


def run_doctor() -> None:
    """
    فارسی: وضعیت کلی نصب (پایتون، yt-dlp، ffmpeg، کتابخانه‌ها، کوکی، دسترسی‌ها) را بررسی و گزارش می‌دهد.
    English: Check and report the overall installation health (Python, yt-dlp, ffmpeg, libraries, cookies, permissions).
    """
    table = Table(title="Open Downloader CLI — Doctor", show_header=False, box=None)

    table.add_row("[bold]odl version[/bold]", ODL_VERSION)
    table.add_row("[bold]Python[/bold]", platform.python_version())
    table.add_row("[bold]OS[/bold]", f"{platform.system()} {platform.release()}")
    table.add_row("[bold]Architecture[/bold]", platform.machine())

    try:
        table.add_row("[bold]yt-dlp[/bold]", f"[green]{yt_dlp.version.__version__}[/green]")
    except Exception:
        table.add_row("[bold]yt-dlp[/bold]", "[red]not detected[/red]")

    ffmpeg_path = shutil.which("ffmpeg")
    table.add_row("[bold]ffmpeg[/bold]", f"[green]{ffmpeg_path}[/green]" if ffmpeg_path else "[red]not found[/red]")

    table.add_row(
        "[bold]cryptography lib[/bold]",
        "[green]available[/green]" if CRYPTO_AVAILABLE else "[red]missing[/red]",
    )

    if ENCRYPTED_COOKIES_FILE.exists():
        table.add_row("[bold]Cookies[/bold]", "[green]encrypted file present[/green]")
    elif COOKIES_DEFAULT.exists():
        table.add_row("[bold]Cookies[/bold]", "[yellow]plaintext file present (will be encrypted on next run)[/yellow]")
    else:
        table.add_row("[bold]Cookies[/bold]", "[red]none found[/red]")

    table.add_row(
        "[bold]Config directory[/bold]",
        f"{CONFIG_DIR} ({'writable' if os.access(CONFIG_DIR.parent, os.W_OK) else 'NOT writable'})",
    )
    table.add_row("[bold]Environment[/bold]", "Desktop Linux" if is_desktop_linux() else "Android/Termux")

    console.print(Panel(table, border_style="cyan"))


def build_arg_parser() -> argparse.ArgumentParser:
    """
    فارسی: پارسر آرگومان‌های خط فرمان را می‌سازد.
    English: Build the command-line argument parser.
    """
    parser = argparse.ArgumentParser(
        prog="odl",
        description="Open Downloader CLI (odl) — a simple, resumable YouTube downloader built on yt-dlp",
    )
    parser.add_argument("url", nargs="?", help="YouTube video or playlist URL")
    parser.add_argument("-p", "--playlist", action="store_true", help="playlist mode")
    parser.add_argument(
        "-q", "--quality", type=int, default=None,
        help=f"video quality: {', '.join(map(str, ALLOWED_QUALITIES))}",
    )
    parser.add_argument("-s", "--sub-en", action="store_true", help="download English subtitles")
    parser.add_argument("-fs", "--sub-fa", action="store_true", help="download Persian subtitles (if available)")
    parser.add_argument("-a", "--audio-only", action="store_true", help="audio only (mp3)")
    parser.add_argument("-o", "--output", type=str, default=None, help="custom output directory")
    parser.add_argument("-b", "--batch", type=int, default=None, help="number of concurrent downloads in playlist mode")
    parser.add_argument(
        "-x", "--proxy", type=str, default=None,
        help="proxy address, e.g. socks5h://127.0.0.1:9050",
    )
    parser.add_argument(
        "--player-client", type=str, default=None,
        help="force a specific YouTube playback client, e.g. 'android' (helps bypass bot detection)",
    )
    parser.add_argument(
        "--bypass", action="store_true",
        help="lighter/faster extraction that skips extra YouTube webpage requests "
             "(may miss some formats or subtitles)",
    )
    parser.add_argument(
        "--secure-cookies", action="store_true",
        help="encrypt the current cookies.txt file and store a secure version",
    )
    parser.add_argument(
        "--reset-cookies", action="store_true",
        help="delete the encrypted cookie file (use this if you forgot the master password)",
    )
    parser.add_argument(
        "--import-cookies", action="store_true",
        help="force a fresh automatic cookie import even if an encrypted cookie file already exists",
    )
    parser.add_argument(
        "--cookie-status", action="store_true",
        help="show whether cookies are encrypted/plaintext/missing and when they were imported",
    )
    parser.add_argument(
        "--no-estimate", action="store_true",
        help="skip the (potentially slow) total-size estimation step for large playlists",
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="show detailed diagnostic info and full tracebacks on error",
    )
    parser.add_argument(
        "--doctor", action="store_true",
        help="check the health of the installation (Python, yt-dlp, ffmpeg, cookies, permissions)",
    )
    parser.add_argument(
        "--check-update", action="store_true",
        help="check whether a newer yt-dlp version is available, without installing it",
    )
    parser.add_argument(
        "--update", action="store_true",
        help="update yt-dlp to the latest version",
    )
    parser.add_argument("--version", action="version", version=f"Open Downloader CLI (odl) {ODL_VERSION}")
    return parser


def main() -> None:
    global DEBUG

    args = build_arg_parser().parse_args()
    DEBUG = args.debug

    if args.doctor:
        run_doctor()
        sys.exit(0)

    if args.check_update:
        run_check_update()
        sys.exit(0)

    if args.update:
        run_update()
        sys.exit(0)

    if args.cookie_status:
        print_cookie_status()
        sys.exit(0)

    if args.reset_cookies:
        reset_encrypted_cookies()
        sys.exit(0)

    if args.secure_cookies:
        secure_cookies_setup()
        sys.exit(0)

    # فارسی: اولویت ۱ — امتحان کردن روش‌های کاملاً خودکار متناسب با محیط
    #        اجرا (لینوکس دسکتاپ یا اندروید روت‌شده). اگه از قبل کوکی
    #        رمزنگاری‌شده وجود داشته باشه، این کار انجام نمی‌شه مگه با
    #        --import-cookies صریحاً درخواست بشه.
    # English: priority 1 — try fully automatic methods suited to the
    #          current environment (desktop Linux or rooted Android). If an
    #          encrypted cookie file already exists, this is skipped unless
    #          --import-cookies explicitly requests a fresh import.
    try_automatic_cookie_import(force=args.import_cookies)

    # فارسی: اولویت ۲ — اگه روش کاملاً خودکار جواب نداد، دنبال فایل export
    #        دستی توی مسیرهای معمول (مثل پوشه‌ی Download) بگرد.
    # English: priority 2 — if the fully automatic method didn't work, look
    #          for a manually exported file in common locations (e.g. Downloads).
    find_and_import_cookies_automatically(force=args.import_cookies)

    # فارسی: اجباری و خودکار — اگه در نتیجه‌ی مراحل بالا فایل کوکی متن‌ساده
    #        وجود داشته باشه، قبل از هر کاری امنش می‌کنیم و همون‌جا نسخه‌ی
    #        دیکریپت‌شده‌ش رو برای همین اجرا نگه می‌داریم تا رمز اصلی دوباره
    #        پرسیده نشه.
    # English: mandatory and automatic — if a plaintext cookie file exists
    #          as a result of the steps above, secure it before doing
    #          anything else, and keep its decrypted form for this run so
    #          the master password isn't asked twice.
    auto_cookies_path: Optional[str] = None
    auto_cleanup: CleanupFn = lambda: None
    if COOKIES_DEFAULT.exists():
        auto_cookies_path, auto_cleanup = secure_cookies_setup(auto=True)

    if not args.url:
        build_arg_parser().print_help()
        sys.exit(1)

    cfg = load_config()
    save_default_config()
    rotate_log()

    quality = args.quality if args.quality else cfg.get("quality", DEFAULT_QUALITY)
    if quality not in ALLOWED_QUALITIES:
        console.print(f"[red]Quality {quality} is not valid.[/red]")
        console.print(f"Allowed qualities: {', '.join(map(str, ALLOWED_QUALITIES))}")
        sys.exit(1)

    out_dir = args.output if args.output else cfg.get("download_dir", str(DOWNLOAD_DIR_DEFAULT))
    batch_size = args.batch if args.batch else cfg.get("batch_size", BATCH_SIZE)
    proxy = args.proxy if args.proxy else cfg.get("proxy")

    # فارسی: فقط وقتی fallback خودکار کلاینت فعال می‌شه که کاربر خودش صریحاً
    #        کلاینت خاصی رو انتخاب نکرده باشه (احترام به انتخاب صریح کاربر).
    # English: client auto-fallback is only enabled when the user hasn't
    #          explicitly forced a specific client (respecting an explicit choice).
    user_forced_client = bool(args.player_client)
    allow_client_fallback = not user_forced_client

    if args.player_client:
        cfg["player_client"] = args.player_client
    bypass = args.bypass or cfg.get("bypass", False)
    extractor_args = build_extractor_args(cfg, bypass)

    if auto_cookies_path:
        cookies_path, cleanup_cookies = auto_cookies_path, auto_cleanup
    else:
        cookies_path, cleanup_cookies = resolve_cookies_path(cfg)

    if cookies_path is None:
        print_cookie_export_guide()

    if DEBUG:
        console.print(Panel(
            f"Python: {platform.python_version()}\n"
            f"odl: {ODL_VERSION}\n"
            f"yt-dlp: {getattr(yt_dlp.version, '__version__', 'unknown')}\n"
            f"OS: {platform.system()} {platform.release()}\n"
            f"Proxy: {proxy or 'none'}\n"
            f"Player client override: {cfg.get('player_client') or 'auto'}\n"
            f"Cookies: {'yes' if cookies_path else 'no'}\n"
            f"Quality: {quality}p\n"
            f"Extractor args: {extractor_args}",
            title="DEBUG INFO", border_style="magenta",
        ))

    try:
        if args.playlist:
            download_playlist(
                args.url, cookies_path, quality, args.sub_en, args.sub_fa,
                out_dir, args.audio_only, batch_size, proxy, extractor_args,
                allow_client_fallback, args.no_estimate,
            )
        else:
            download_single(
                args.url, cookies_path, quality, args.sub_en, args.sub_fa,
                out_dir, args.audio_only, proxy, extractor_args, allow_client_fallback,
            )
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopped. Run the same command again to resume automatically.[/yellow]")
        cleanup_cookies()
        sys.exit(130)
    finally:
        cleanup_cookies()


if __name__ == "__main__":
    main()
