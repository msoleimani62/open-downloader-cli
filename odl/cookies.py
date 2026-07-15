"""
فارسی: تمام منطق مربوط به کوکی — تشخیص محیط اجرا، دریافت خودکار (دسکتاپ/
       روت/دستی)، رمزنگاری با رمز اصلی، بازنشانی، و نمایش وضعیت.
English: All cookie-related logic — environment detection, automatic
         retrieval (desktop/root/manual), master-password encryption,
         reset, and status reporting.
"""

from __future__ import annotations

import base64
import getpass
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import time
import traceback
from enum import Enum
from pathlib import Path
from typing import Optional, Tuple

from rich.panel import Panel
from rich.prompt import Confirm
from rich.table import Table

from . import constants as c
from . import state
from .logging_setup import log_debug_traceback
from .state import console

try:
    from cryptography.fernet import Fernet, InvalidToken
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False


class Environment(Enum):
    """
    فارسی: محیط اجرای واقعی odl. برخلاف یک بولی ساده (دسکتاپ/غیردسکتاپ)،
           این enum بین چند محیط لینوکسی متفاوت که هرکدام رفتار متفاوتی
           برای دسترسی به کوکی/فایل‌سیستم دارند تمایز قائل می‌شود.
    English: The actual environment odl is running in. Unlike a simple
             boolean (desktop/not-desktop), this enum distinguishes
             between several Linux-family environments that each need
             different cookie/filesystem access behavior.
    """

    ANDROID_TERMUX = "Android/Termux"
    KALI_NETHUNTER = "Kali NetHunter (Termux/proot)"
    DESKTOP_LINUX = "Desktop Linux"
    WSL = "WSL (Windows Subsystem for Linux)"
    OTHER = "Other/Unrecognized"


def _read_text_safely(path: Path) -> str:
    """
    فارسی: محتوای یک فایل را می‌خواند و در هر نوع خطا (شامل PermissionError
           — که خودش می‌تواند یک نشونه باشد، نه فقط یک خطای بی‌ربط) رشته‌ی
           خالی برمی‌گرداند.
    English: Read a file's content, returning an empty string on any error
             (including PermissionError — which can itself be a signal,
             not just an unrelated failure).
    """
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def _looks_like_android_kernel() -> bool:
    """
    فارسی: از داخل یک chroot/proot (مثل Kali NetHunter)، نشونه‌های معمول
           اندروید (مسیرها، متغیرهای محیطی) دیده نمی‌شوند چون متعلق به
           بیرون chroot‌اند. ولی زیرسیستم‌های کرنلی مخصوص اندروید — binder،
           cpuset، schedtune، یا mount option سراسری seclabel (SELinux
           اندروید) — همیشه در /proc/mounts دیده می‌شوند، چون کرنل زیرِ
           chroot هم همان کرنل هاست است. این نشونه‌ها با تست دستی روی یک
           نصب واقعی Kali NetHunter تأیید شده‌اند.
    English: From inside a chroot/proot (e.g. Kali NetHunter), the usual
             Android markers (paths, env vars) aren't visible since they
             belong outside the chroot. But Android-specific kernel
             subsystems — binder, cpuset, schedtune, or the seclabel mount
             option (Android's SELinux) — always show up in /proc/mounts,
             since the kernel underneath the chroot is still the host's.
             These signals were confirmed by hand on a real Kali NetHunter
             install.
    """
    mounts = _read_text_safely(Path("/proc/mounts"))
    return any(signal in mounts for signal in c.ANDROID_KERNEL_MOUNT_SIGNALS)


def _chroot_distro_id() -> Optional[str]:
    """
    فارسی: شناسه‌ی توزیع (ID در /etc/os-release) داخل chroot فعلی را
           برمی‌گرداند، مثلاً «kali». اگر پیدا نشد None برمی‌گردد.
    English: Return the distro ID (ID in /etc/os-release) inside the
             current chroot, e.g. "kali". Returns None if not found.
    """
    for line in _read_text_safely(Path("/etc/os-release")).splitlines():
        if line.startswith("ID="):
            return line.split("=", 1)[1].strip().strip('"').lower()
    return None


def detect_environment() -> Environment:
    """
    فارسی:
        محیط واقعی اجرا را تشخیص می‌دهد. ترتیب بررسی:
        ۱. override دستی با متغیر محیطی ODL_FORCE_ENVIRONMENT (برای
           مواقعی که تشخیص خودکار اشتباه رفت).
        ۲. WSL: از روی محتوای /proc/version.
        ۳. Android/Termux واقعی (نه chroot): نشانه‌های اندروید مستقیماً
           دیده می‌شوند.
        ۴. Kali NetHunter روی Termux/proot: نشانه‌های اندروید مستقیم دیده
           نمی‌شوند (چون داخل chroot هستیم) ولی زیرسیستم‌های کرنلی
           مخصوص اندروید در /proc/mounts دیده می‌شوند؛ اگر توزیع chroot
           هم «kali» باشد، دقیقاً Kali NetHunter است.
        ۵. در غیر این صورت: Desktop Linux معمولی.
    English:
        Detect the actual runtime environment. Check order:
        1. Manual override via the ODL_FORCE_ENVIRONMENT env var (for
           cases where auto-detection gets it wrong).
        2. WSL: from the contents of /proc/version.
        3. Genuine Android/Termux (not chrooted): Android markers are
           directly visible.
        4. Kali NetHunter on Termux/proot: direct Android markers aren't
           visible (since we're inside the chroot) but Android-specific
           kernel subsystems show up in /proc/mounts; if the chroot's
           distro is also "kali", it's specifically Kali NetHunter.
        5. Otherwise: a regular Desktop Linux.
    """
    override = os.environ.get("ODL_FORCE_ENVIRONMENT", "").strip().upper()
    if override:
        try:
            return Environment[override]
        except KeyError:
            pass  # فارسی: مقدار نامعتبر بود؛ به تشخیص خودکار برمی‌گردیم
            # English: invalid value; fall through to auto-detection

    if not sys.platform.startswith("linux"):
        return Environment.OTHER

    proc_version = _read_text_safely(Path("/proc/version")).lower()
    if "microsoft" in proc_version:
        return Environment.WSL

    android_markers_visible = any(path.exists() for path in c.ANDROID_MARKER_PATHS) or any(
        os.environ.get(var) for var in c.ANDROID_MARKER_ENV_VARS
    )
    if android_markers_visible:
        return Environment.ANDROID_TERMUX

    if _looks_like_android_kernel():
        return Environment.KALI_NETHUNTER if _chroot_distro_id() == "kali" else Environment.ANDROID_TERMUX

    return Environment.DESKTOP_LINUX


def is_desktop_linux() -> bool:
    """
    فارسی: نسخه‌ی بولیِ سازگار با نسخه‌ی قبلی، بر پایه‌ی detect_environment.
           فقط برای عادی‌ترین شاخه‌بندی رفتاری (دسکتاپ در برابر بقیه) نگه
           داشته شده؛ برای نمایش/گزارش از detect_environment() مستقیم
           استفاده کنید.
    English: Backward-compatible boolean wrapper around detect_environment,
             kept only for the simplest behavioral branching (desktop vs.
             everything else). For display/reporting, use
             detect_environment() directly.
    """
    return detect_environment() is Environment.DESKTOP_LINUX


def _extract_via_ytdlp_browser(browser: str) -> Optional[str]:
    """
    فارسی: با قابلیت داخلی yt-dlp، کوکی‌ها را مستقیم از پروفایل مرورگر
           دسکتاپ می‌خواند و به متن Netscape تبدیل می‌کند.
    English: Use yt-dlp's built-in reader to pull cookies directly from a
             desktop browser profile and convert them to Netscape-format text.
    """
    try:
        from yt_dlp.cookies import extract_cookies_from_browser
    except ImportError:
        return None

    try:
        jar = extract_cookies_from_browser(browser)
    except Exception:
        # فارسی: شکست در این مرحله طبیعی است (مثلاً مرورگر نصب نیست)، پس
        #        روی ترمینال چیزی چاپ نمی‌شود؛ ولی دلیل دقیق برای دیباگ بعدی ثبت می‌شود.
        # English: Failure here is expected (e.g. the browser isn't installed),
        #          so nothing is printed to the terminal; but the exact reason
        #          is still logged for later debugging.
        log_debug_traceback(traceback.format_exc())
        return None

    if jar is None or len(jar) == 0:
        return None

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
           خوندن دسترسی داشت، مسیر پوشه‌ی پروفایل را برمی‌گرداند.
    English: If the Android Firefox cookie database is directly readable
             (e.g. with root), return the profile folder's path.
    """
    try:
        if not c.ANDROID_FIREFOX_PROFILES_DIR.exists():
            return None
        for profile in sorted(c.ANDROID_FIREFOX_PROFILES_DIR.glob("*.default*")):
            cookie_db = profile / "cookies.sqlite"
            if profile.is_dir() and cookie_db.exists() and os.access(cookie_db, os.R_OK):
                return profile
    except PermissionError:
        return None
    return None


def _extract_via_android_firefox(profile_dir: Path) -> Optional[str]:
    """
    فارسی: کوکی‌های یوتیوب/گوگل را مستقیم از دیتابیس SQLite فایرفاکس اندروید
           می‌خواند و به فرمت Netscape تبدیل می‌کند.
    English: Read YouTube/Google cookies directly from the Android Firefox
             SQLite database and convert them to Netscape format.
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
        log_debug_traceback(traceback.format_exc())
        return None
    finally:
        tmp_copy.unlink(missing_ok=True)

    if not rows:
        return None

    lines = [
        "# Netscape HTTP Cookie File",
        "# Generated automatically by open-downloader-cli (odl) from the Android Firefox profile.",
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
    فارسی: به ترتیب اولویت، روش‌های کاملاً خودکارِ دریافت کوکی را امتحان می‌کند.
    English: In priority order, try fully automatic cookie retrieval methods.

    Returns:
        True if cookies were imported automatically, False otherwise.
    """
    if c.COOKIES_DEFAULT.exists():
        return False
    if c.ENCRYPTED_COOKIES_FILE.exists() and not force:
        return False

    if is_desktop_linux():
        for browser in ("firefox", "chrome", "chromium"):
            content = _extract_via_ytdlp_browser(browser)
            if content:
                c.COOKIES_DEFAULT.write_text(content, encoding="utf-8")
                console.print(
                    f"[green]✔ Cookies imported automatically from your {browser.capitalize()} profile.[/green]"
                )
                return True
        return False

    profile_dir = find_android_firefox_profile()
    if profile_dir:
        content = _extract_via_android_firefox(profile_dir)
        if content:
            c.COOKIES_DEFAULT.write_text(content, encoding="utf-8")
            console.print("[green]✔ Cookies imported automatically (root access detected).[/green]")
            return True

    return False


def find_and_import_cookies_automatically(force: bool = False) -> bool:
    """
    فارسی: روش نیمه‌خودکار — دنبال فایل export دستی توی مسیرهای معمول می‌گردد.
    English: Semi-automatic method — looks for a manually exported file in common locations.
    """
    if c.COOKIES_DEFAULT.exists():
        return False
    if c.ENCRYPTED_COOKIES_FILE.exists() and not force:
        return False

    for candidate in c.COOKIE_SEARCH_PATHS:
        if candidate.exists() and candidate.is_file():
            try:
                shutil.copy(candidate, c.COOKIES_DEFAULT)
            except Exception:
                continue
            console.print(f"[green]✔ Found an exported cookie file at {candidate} and imported it automatically.[/green]")
            return True

    return False


def print_cookie_export_guide() -> None:
    """
    فارسی: راهنمای کامل و شماره‌گذاری‌شده برای export دستی کوکی یوتیوب را چاپ می‌کند.
    English: Print a full, numbered, step-by-step guide for manually exporting YouTube cookies.
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


def _require_crypto() -> None:
    """
    فارسی: اگه کتابخونه‌ی cryptography نصب نباشه، با پیام واضح خروج می‌کنه.
    English: Exit with a clear message if the cryptography library is missing.
    """
    if not CRYPTO_AVAILABLE:
        console.print("[red]The 'cryptography' library is not installed.[/red]")
        console.print("Install it with: pip install cryptography --break-system-packages")
        sys.exit(1)


def derive_key(password: str, salt: bytes, iterations: Optional[int] = None) -> bytes:
    """
    فارسی: از رمز اصلی و یک salt، کلید رمزنگاری AES (از طریق Fernet) می‌سازه.
           iterations باید همیشه با مقداری که هنگام رمزنگاری استفاده شده یکی باشد
           (برای فایل‌های جدید از payload خوانده می‌شود، نه از ثابت سراسری).
           اگر داده نشود، مقدار فعلی ثابت سراسری در لحظه‌ی فراخوانی خوانده می‌شود
           (نه در لحظه‌ی import، تا از رفتار late-binding آرگومان پیش‌فرض جلوگیری شود).
    English: Derive an AES encryption key (via Fernet) from a master password
             and salt. iterations must always match the value used at
             encryption time (for new files, it's read from the payload,
             not from the global constant). If not given, the current value
             of the global constant is read at call time (not at import
             time, to avoid the default-argument late-binding pitfall).
    """
    if iterations is None:
        iterations = c.PBKDF2_ITERATIONS
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=iterations,
    )
    return base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))


def encrypt_cookie_data(plain_data: bytes, master_password: str) -> dict:
    """
    فارسی: رمزنگاری خالص کوکی — بدون هیچ چاپ، پرسش تعاملی، یا نوشتن فایل.
           فقط payload آماده برای ذخیره را برمی‌گرداند. این تابع مستقیماً
           از GUI و لایه‌ی Chaquopی روی اندروید هم قابل فراخوانی است.
    English: Pure cookie encryption — no printing, no interactive prompt, no
             file writing. Just returns the payload ready to be persisted.
             This function can be called directly from the GUI and the
             Chaquopy layer on Android too.
    """
    salt = os.urandom(16)
    key = derive_key(master_password, salt)
    fernet = Fernet(key)
    token = fernet.encrypt(plain_data)
    return {
        "salt": base64.b64encode(salt).decode("ascii"),
        "data": token.decode("ascii"),
        "imported_at": time.time(),
        "pbkdf2_iterations": c.PBKDF2_ITERATIONS,
    }


def decrypt_cookie_payload(payload: dict, master_password: str) -> bytes:
    """
    فارسی: رمزگشایی خالص کوکی. در صورت رمز اشتباه، استثنای
           cryptography.fernet.InvalidToken می‌اندازد (خودش را نمی‌گیرد)،
           تا تصمیم نمایش پیام خطا بر عهده‌ی لایه‌ی UI باقی بماند.
    English: Pure cookie decryption. Raises
             cryptography.fernet.InvalidToken on a wrong password (does not
             catch it itself), leaving the decision of how to display the
             error message to the UI layer.
    """
    salt = base64.b64decode(payload["salt"])
    token = payload["data"].encode("ascii")
    # فارسی: فایل‌های رمزنگاری‌شده‌ی قدیمی‌تر از این فیکس، مقدار
    #        pbkdf2_iterations را ذخیره نکرده‌اند؛ برای آن‌ها از مقدار
    #        قدیمی (که قبلاً هاردکد بود) استفاده می‌کنیم.
    # English: Files encrypted before this fix don't have a stored
    #          pbkdf2_iterations value; fall back to the old
    #          previously-hardcoded value for those.
    iterations = payload.get("pbkdf2_iterations", 390_000)
    key = derive_key(master_password, salt, iterations)
    fernet = Fernet(key)
    return fernet.decrypt(token)


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


def _write_temp_cookie_file(data: bytes) -> Tuple[str, c.CleanupFn]:
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


def secure_cookies_setup(auto: bool = False) -> Tuple[Optional[str], "c.CleanupFn"]:
    """
    فارسی: رمزنگاری فایل cookies.txt موجود با یک رمز اصلی (که هیچ‌جا ذخیره نمی‌شه).
    English: Encrypt the existing cookies.txt file using a master password
             (never stored anywhere).

    Returns:
        (decrypted_cookie_path_or_None, cleanup_function)
    """
    _require_crypto()

    if not c.COOKIES_DEFAULT.exists():
        if not auto:
            console.print(f"[red]File {c.COOKIES_DEFAULT} not found. Export your cookies first.[/red]")
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

    plain_data = c.COOKIES_DEFAULT.read_bytes()
    payload = encrypt_cookie_data(plain_data, master_password)

    c.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(c.ENCRYPTED_COOKIES_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f)
    os.chmod(c.ENCRYPTED_COOKIES_FILE, 0o600)

    c.COOKIES_DEFAULT.unlink()

    console.print("[green]✔ Cookie file encrypted and plaintext file deleted.[/green]")

    if not auto:
        return None, (lambda: None)

    console.print("[cyan]Continuing command...[/cyan]")
    return _write_temp_cookie_file(plain_data)


def print_cookie_status() -> None:
    """
    فارسی: وضعیت فعلی کوکی (رمزنگاری‌شده/متن‌ساده/عدم‌وجود) و زمان import آن را نشان می‌دهد.
    English: Show the current cookie status (encrypted/plaintext/none) and when it was imported.
    """
    table = Table(show_header=False, box=None)
    if c.ENCRYPTED_COOKIES_FILE.exists():
        table.add_row("[bold]Status[/bold]", "[green]Encrypted[/green]")
        perm = oct(c.ENCRYPTED_COOKIES_FILE.stat().st_mode)[-3:]
        perm_display = f"[green]{perm}[/green]" if perm == "600" else f"[yellow]{perm} (expected 600)[/yellow]"
        table.add_row("[bold]Permissions[/bold]", perm_display)
        try:
            with open(c.ENCRYPTED_COOKIES_FILE, "r", encoding="utf-8") as f:
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
    elif c.COOKIES_DEFAULT.exists():
        table.add_row("[bold]Status[/bold]", "[yellow]Plaintext (not yet encrypted)[/yellow]")
    else:
        table.add_row("[bold]Status[/bold]", "[red]No cookies found[/red]")
    console.print(Panel(table, title="Cookie Status", border_style="cyan"))


def reset_encrypted_cookies() -> None:
    """
    فارسی: فایل کوکی رمزنگاری‌شده را برای همیشه حذف می‌کند (بازنشانی کامل).
    English: Permanently delete the encrypted cookie file (a full reset).
    """
    if c.ENCRYPTED_COOKIES_FILE.exists():
        c.ENCRYPTED_COOKIES_FILE.unlink()
        console.print("[green]✔ Encrypted cookie file removed.[/green]")
    else:
        console.print("[yellow]There is no encrypted cookie file to remove.[/yellow]")
    print_cookie_export_guide()


def resolve_cookies_path(cfg: dict) -> Tuple[Optional[str], "c.CleanupFn"]:
    """
    فارسی: رمز اصلی را می‌پرسد (تا سقف MAX_PASSWORD_ATTEMPTS بار)، کوکی
           رمزنگاری‌شده را به یک فایل موقت رمزگشایی می‌کند، یا در نبود آن
           به cookies.txt معمولی برمی‌گردد.
    English: Prompt for the master password (up to MAX_PASSWORD_ATTEMPTS
             times) and decrypt into a temp file, or fall back to a plain
             cookies.txt if no encrypted file exists.

    Returns:
        (cookie_path_or_None, cleanup_function)
    """
    if c.ENCRYPTED_COOKIES_FILE.exists():
        _require_crypto()
        try:
            with open(c.ENCRYPTED_COOKIES_FILE, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except Exception as e:
            log_debug_traceback(traceback.format_exc())
            console.print(f"[red]Error reading the encrypted cookie file: {e}[/red]")
            sys.exit(1)

        for attempt in range(1, c.MAX_PASSWORD_ATTEMPTS + 1):
            password = getpass.getpass("Cookie master password: ")
            try:
                data = decrypt_cookie_payload(payload, password)
                return _write_temp_cookie_file(data)
            except InvalidToken:
                remaining = c.MAX_PASSWORD_ATTEMPTS - attempt
                if remaining > 0:
                    console.print(f"[red]Wrong password. {remaining} attempt(s) left.[/red]")

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
