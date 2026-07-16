"""
فارسی: ابزارهای تشخیصی — بررسی/انجام آپدیت yt-dlp، بررسی خود‌آپدیت odl، و بررسی سلامت نصب.
English: Diagnostic tools — checking/performing yt-dlp updates, checking
         odl's own self-update, and installation health checks.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
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


def run_check_self_update() -> None:
    """
    فارسی: نسخه‌ی نصب‌شده‌ی odl را با آخرین ریلیز گیت‌هاب مقایسه می‌کند
           (فقط بررسی می‌کند، خودش چیزی را آپدیت نمی‌کند).
    English: Compare the installed odl version against the latest GitHub
             release (check only, does not update anything itself).
    """
    console.print("[cyan]Checking for a newer version of Open Downloader CLI...[/cyan]")
    url = f"https://api.github.com/repos/{c.GITHUB_REPO}/releases/latest"
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
        latest_tag = data.get("tag_name", "")
        if not latest_tag:
            console.print("[yellow]Could not determine the latest release.[/yellow]")
            return

        current = _parse_version_tuple(c.ODL_VERSION)
        latest = _parse_version_tuple(latest_tag)

        if latest > current:
            console.print(f"[yellow]A newer version is available: {latest_tag} (you have {c.ODL_VERSION}).[/yellow]")
            console.print(f"[cyan]Get it from: https://github.com/{c.GITHUB_REPO}/releases/latest[/cyan]")
        else:
            console.print(f"[green]You're up to date (version {c.ODL_VERSION}).[/green]")
    except Exception as e:
        console.print(f"[yellow]Could not check for updates: {e}[/yellow]")


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

    console.print(Panel(table, border_style="cyan"))
