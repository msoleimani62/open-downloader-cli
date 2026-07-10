"""
فارسی: ابزارهای تشخیصی — بررسی/انجام آپدیت yt-dlp و بررسی سلامت نصب.
English: Diagnostic tools — checking/performing yt-dlp updates and installation health checks.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys

import yt_dlp
from rich.panel import Panel
from rich.table import Table

from . import constants as c
from .cookies import CRYPTO_AVAILABLE, is_desktop_linux
from .state import console


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
        table.add_row("[bold]Cookies[/bold]", "[red]none found[/red]")

    table.add_row(
        "[bold]Config directory[/bold]",
        f"{c.CONFIG_DIR} ({'writable' if os.access(c.CONFIG_DIR.parent, os.W_OK) else 'NOT writable'})",
    )
    table.add_row("[bold]Environment[/bold]", "Desktop Linux" if is_desktop_linux() else "Android/Termux")

    console.print(Panel(table, border_style="cyan"))
