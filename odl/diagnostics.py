"""
فارسی: ابزارهای تشخیصی — بررسی/انجام آپدیت yt-dlp، بررسی خود‌آپدیت odl، و بررسی سلامت نصب.
English: Diagnostic tools — checking/performing yt-dlp updates, checking
         odl's own self-update, and installation health checks.
"""

from __future__ import annotations

import contextlib
import json
import os
import platform
import shutil
import subprocess
import sys
import sysconfig
import time
import urllib.request

import yt_dlp
from rich.panel import Panel
from rich.table import Table

from . import constants as c
from .cookies import CRYPTO_AVAILABLE, detect_environment
from .state import console


def _parse_version_tuple(version_str: str) -> tuple:
    """
    فارسی: رشته‌ی نسخه (مثل «2.1.0» یا «v2.1.0») را به یک تاپل قابل‌مقایسه تبدیل می‌کند.
    English: Convert a version string (e.g. "2.1.0" or "v2.1.0") into a comparable tuple.
    """
    cleaned = version_str.strip().lstrip("vV")
    parts = []
    for piece in cleaned.split("."):
        digits = "".join(ch for ch in piece if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def _fetch_latest_release_tag(timeout: int) -> str | None:
    """
    فارسی: تگ آخرین ریلیز گیت‌هاب را برمی‌گرداند، یا None اگر شبکه/پاسخ
           مشکل داشت. این تابع خودش هیچ خطایی چاپ نمی‌کند و هیچ استثنایی
           رها نمی‌کند — تصمیم درباره‌ی نمایش خطا با فراخوان است، چون
           چک دستی (run_check_self_update) باید همیشه پیام بدهد ولی چک
           خودکار پس‌زمینه (check_self_update_if_due) باید کاملاً بی‌صدا
           شکست بخورد.
    English: Return the latest GitHub release tag, or None if the
             network/response failed. This function never prints an error
             and never lets an exception escape — whether to surface an
             error is left to the caller, since the manual check
             (run_check_self_update) should always report something, while
             the automatic background check (check_self_update_if_due)
             must fail completely silently.
    """
    try:
        url = f"https://api.github.com/repos/{c.GITHUB_REPO}/releases/latest"
        req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
        return data.get("tag_name") or None
    except Exception:
        return None


def _load_update_cache() -> dict:
    """
    فارسی: کش زمان آخرین چک خودکار آپدیت را می‌خواند؛ اگر فایل نبود یا
           خراب بود، دیکشنری خالی برمی‌گرداند (یعنی «تا حالا چک نشده»).
    English: Read the cache of when the last automatic update check ran;
             if the file is missing or corrupt, return an empty dict
             (meaning "never checked before").
    """
    try:
        return json.loads(c.SELF_UPDATE_CACHE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_update_cache(data: dict) -> None:
    """
    فارسی: کش چک آپدیت را ذخیره می‌کند. این کش صرفاً یک بهینه‌سازی است؛
           اگر نوشتنش (مثلاً به‌خاطر یک فایل‌سیستم read-only) شکست بخورد،
           نباید کل برنامه را متوقف کند — فقط یعنی چک بعدی هم دوباره انجام می‌شود.
    English: Persist the update-check cache. This cache is purely an
             optimization; if writing it fails (e.g. a read-only
             filesystem), that must never crash the program — it just
             means the next run checks again too.
    """
    with contextlib.suppress(Exception):
        c.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        c.SELF_UPDATE_CACHE_FILE.write_text(json.dumps(data), encoding="utf-8")


def run_check_self_update() -> None:
    """
    فارسی: نسخه‌ی نصب‌شده‌ی odl را با آخرین ریلیز گیت‌هاب مقایسه می‌کند
           (فقط بررسی می‌کند، خودش چیزی را آپدیت نمی‌کند). این نسخه‌ی
           دستی (`odl --check-self-update`) است: بدون توجه به کش، همیشه
           همین حالا چک می‌کند و همیشه نتیجه را (چه آپدیت باشد چه نباشد
           چه خطا) به کاربر نشان می‌دهد.
    English: Compare the installed odl version against the latest GitHub
             release (check only, does not update anything itself). This
             is the manual (`odl --check-self-update`) path: it ignores
             the cache, always checks right now, and always reports the
             outcome to the user (update available, up to date, or error).
    """
    console.print("[cyan]Checking for a newer version of Open Downloader CLI...[/cyan]")
    latest_tag = _fetch_latest_release_tag(timeout=10)
    if not latest_tag:
        console.print("[yellow]Could not check for updates — the network may be unreachable.[/yellow]")
        return

    current = _parse_version_tuple(c.ODL_VERSION)
    latest = _parse_version_tuple(latest_tag)

    if latest > current:
        console.print(f"[yellow]A newer version is available: {latest_tag} (you have {c.ODL_VERSION}).[/yellow]")
        console.print(f"[cyan]Get it from: https://github.com/{c.GITHUB_REPO}/releases/latest[/cyan]")
    else:
        console.print(f"[green]You're up to date (version {c.ODL_VERSION}).[/green]")

    _save_update_cache({"last_check_ts": time.time(), "last_check_ok": True, "latest_tag": latest_tag})


def check_self_update_if_due() -> None:
    """
    فارسی: نسخه‌ی خودکار و ساکت چک آپدیت — برای فراخوانی در ابتدای هر
           اجرای واقعی دانلود (نه در مسیرهای --doctor/--config/و…). فقط
           اگر از آخرین چک موفق حداقل ۴۸ ساعت (یا از آخرین تلاش ناموفق
           حداقل ۱ ساعت) گذشته باشد، با یک timeout کوتاه (۳ ثانیه) یک بار
           تلاش می‌کند. اگر شبکه در دسترس نبود، کاملاً بی‌صدا برمی‌گردد —
           هیچ پیام خطایی چاپ نمی‌شود، چون این چک از دید کاربر باید کاملاً
           نامحسوس باشد، نه یک مزاحمت روی هر دانلود. اگر نسخه‌ی جدیدتری
           پیدا شود، فقط یک خط اطلاع‌رسانی چاپ می‌شود؛ خودش چیزی نصب یا
           آپدیت نمی‌کند.
    English: The quiet, automatic update-check path — meant to be called
             at the start of every real download run (not on
             --doctor/--config/etc. paths). Only attempts a check (with a
             short 3-second timeout) if at least 48 hours have passed
             since the last successful check, or at least 1 hour since
             the last failed attempt. If the network is unreachable, it
             returns completely silently — no error is printed, since
             this check must be invisible to the user, not an annoyance
             on every download. If a newer version is found, it prints
             one informational line; it never installs or updates
             anything itself.
    """
    cache = _load_update_cache()
    now = time.time()
    last_check_ts = cache.get("last_check_ts", 0)
    last_check_ok = cache.get("last_check_ok", False)
    interval = c.SELF_UPDATE_CHECK_INTERVAL_SECONDS if last_check_ok else c.SELF_UPDATE_RETRY_INTERVAL_SECONDS

    if now - last_check_ts < interval:
        return

    latest_tag = _fetch_latest_release_tag(timeout=c.SELF_UPDATE_CHECK_TIMEOUT_SECONDS)
    _save_update_cache(
        {"last_check_ts": now, "last_check_ok": latest_tag is not None, "latest_tag": latest_tag or cache.get("latest_tag", "")}
    )

    if not latest_tag:
        return

    current = _parse_version_tuple(c.ODL_VERSION)
    latest = _parse_version_tuple(latest_tag)
    if latest > current:
        console.print(
            f"[yellow]ℹ A newer odl version is available: {latest_tag} (you have {c.ODL_VERSION}). "
            "Run 'odl --check-self-update' for details.[/yellow]"
        )


def run_check_update() -> None:
    """
    فارسی: فقط بررسی می‌کند که آیا نسخه‌ی جدیدتری از yt-dlp موجود است یا نه، بدون نصب.
    English: Only check whether a newer version of yt-dlp is available, without installing.
    """
    console.print("[cyan]Checking for a newer yt-dlp version (no changes will be made)...[/cyan]")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--dry-run", "-U", "yt-dlp", "--break-system-packages"],
            capture_output=True,
            text=True,
            timeout=60,
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
            capture_output=True,
            text=True,
            timeout=120,
        )
        console.print(result.stdout.strip())
        if result.returncode != 0:
            console.print(f"[red]{result.stderr.strip()}[/red]")
        else:
            console.print("[green]✔ yt-dlp updated successfully.[/green]")
    except Exception as e:
        console.print(f"[red]Update failed: {e}[/red]")


def _check_path_health() -> tuple[bool, str]:
    """
    فارسی: بررسی می‌کند که دستور «odl» از طریق PATH واقعاً قابل‌اجراست یا
           نه. pip فایل اجرایی را کنار سایر ابزارهای پایتون (مثلاً
           ~/.local/bin در نصب --user) می‌گذارد، ولی خودش را به PATH
           اضافه نمی‌کند — این یک نقطه‌ضعف شناخته‌شده‌ی pip روی توزیع‌هایی
           مثل آرچ است (روی Termux معمولاً مشکلی نیست چون $PREFIX/bin از
           قبل روی PATH ترموکس هست). اگر پیدا نشد، مسیر محتمل نصب (پوشه‌ی
           scripts پایتون) را برای اضافه‌کردن دستی به PATH برمی‌گرداند.
    English: Check whether the "odl" command is actually runnable via
             PATH. pip places the executable alongside other Python tools
             (e.g. ~/.local/bin for a --user install), but does not add
             that directory to PATH itself — a known pip pitfall on
             distros like Arch (usually not an issue on Termux, since
             $PREFIX/bin is already on Termux's PATH). If not found,
             return the likely install location (Python's scripts
             directory) so the caller can suggest adding it manually.
    """
    found = shutil.which("odl")
    if found:
        return True, found

    candidates = []
    for scheme in ("posix_user", "posix_prefix"):
        with contextlib.suppress(Exception):
            candidates.append(sysconfig.get_path("scripts", scheme))
    # فارسی: حذف موارد تکراری با حفظ ترتیب (posix_user معمولاً محتمل‌تره).
    # English: De-duplicate while preserving order (posix_user is usually
    #          the more likely culprit).
    candidates = list(dict.fromkeys(candidates))
    suggestion = candidates[0] if candidates else "your Python user-scripts directory"
    return False, suggestion


def run_doctor() -> None:
    """
    فارسی: وضعیت کلی نصب را بررسی و گزارش می‌دهد.
    English: Check and report the overall installation health.
    """
    table = Table(title="Open Downloader CLI — Doctor", show_header=False, box=None)

    table.add_row("[bold]odl version[/bold]", c.ODL_VERSION)
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

    if c.ENCRYPTED_COOKIES_FILE.exists():
        table.add_row("[bold]Cookies[/bold]", "[green]encrypted file present[/green]")
    elif c.COOKIES_DEFAULT.exists():
        table.add_row("[bold]Cookies[/bold]", "[yellow]plaintext file present (will be encrypted on next run)[/yellow]")
    else:
        # فارسی: قبلاً اینجا فقط ~/cookies.txt چک می‌شد؛ اگر کاربر فایل
        #        export‌شده را در مسیرهای معمول (مثل Download گوشی) گذاشته
        #        بود ولی هنوز import نشده بود (چون --doctor زودتر از منطق
        #        import خودکار خارج می‌شود)، پیام گمراه‌کننده‌ی «پیدا نشد»
        #        نمایش داده می‌شد.
        # English: This used to only check ~/cookies.txt; if the user had
        #          placed an exported file in a common location (like the
        #          phone's Download folder) but it hadn't been imported yet
        #          (since --doctor exits before the auto-import logic
        #          runs), it showed a misleading "not found" message.
        found_path = next((p for p in c.COOKIE_SEARCH_PATHS if p.exists() and p.is_file()), None)
        if found_path:
            table.add_row(
                "[bold]Cookies[/bold]",
                f"[yellow]found at {found_path}, not imported yet — run 'odl <url>' once to import it[/yellow]",
            )
        else:
            table.add_row("[bold]Cookies[/bold]", "[red]none found[/red]")

    table.add_row(
        "[bold]Config directory[/bold]",
        f"{c.CONFIG_DIR} ({'writable' if os.access(c.CONFIG_DIR.parent, os.W_OK) else 'NOT writable'})",
    )
    table.add_row("[bold]Environment[/bold]", detect_environment().value)

    path_ok, path_info = _check_path_health()
    if path_ok:
        table.add_row("[bold]odl on PATH[/bold]", f"[green]yes ({path_info})[/green]")
    else:
        table.add_row("[bold]odl on PATH[/bold]", "[red]NO — see note below[/red]")

    console.print(Panel(table, border_style="cyan"))

    if not path_ok:
        # فارسی: این هشدار عمداً بیرون از جدول است تا روی گوشی هم (عرض
        #        ترمینال کم) خط‌شکسته و خوانا بماند، برخلاف یک سلول جدول.
        # English: This warning is deliberately outside the table so it
        #          stays readable and word-wraps on a narrow phone
        #          terminal, unlike a table cell would.
        console.print(
            "[yellow]⚠ Typing a bare 'odl' will NOT work in a fresh shell — its install "
            "directory isn't on your PATH yet (you likely reached it just now via "
            "'python -m odl' or a full path).[/yellow]\n"
            f"[cyan]Fix: add this line to your ~/.zshrc (or ~/.bashrc) and restart your shell:[/cyan]\n"
            f'  export PATH="{path_info}:$PATH"'
        )
