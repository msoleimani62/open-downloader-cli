"""
فارسی: پارسر آرگومان‌های خط فرمان و تابع main() که همه‌ی ماژول‌های دیگر را به هم متصل می‌کند.
English: The command-line argument parser and the main() function that wires all other modules together.
"""

from __future__ import annotations

import argparse
import platform
import sys
from typing import Optional

import yt_dlp

from . import constants as c
from . import state
from .config import load_config, parse_set_argument, save_default_config, write_config
from .cookies import (
    find_and_import_cookies_automatically,
    print_cookie_export_guide,
    print_cookie_status,
    reset_encrypted_cookies,
    resolve_cookies_path,
    secure_cookies_setup,
    try_automatic_cookie_import,
)
from .diagnostics import run_check_self_update, run_check_update, run_doctor, run_update
from .downloader import build_extractor_args, download_single
from .playlist import download_playlist
from .state import console


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
        help=f"video quality: {', '.join(map(str, c.ALLOWED_QUALITIES))}",
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
    parser.add_argument(
        "--check-self-update", action="store_true",
        help="check whether a newer version of Open Downloader CLI itself is available",
    )
    parser.add_argument(
        "--config", action="store_true",
        help="show the current configuration settings",
    )
    parser.add_argument(
        "--set", type=str, default=None, metavar="KEY=VALUE",
        help="change a configuration setting, e.g. --set quality=720",
    )
    parser.add_argument("--version", action="version", version=f"Open Downloader CLI (odl) {c.ODL_VERSION}")
    return parser


def _run_show_config() -> None:
    """
    فارسی: تنظیمات فعلی را در یک جدول نمایش می‌دهد.
    English: Display the current settings in a table.
    """
    from rich.panel import Panel
    from rich.table import Table

    cfg = load_config()
    table = Table(show_header=False, box=None)
    for key, value in cfg.items():
        if key == "cookies":
            continue
        table.add_row(f"[bold]{key}[/bold]", str(value) if value is not None else "[dim]not set[/dim]")
    console.print(Panel(table, title="Current Configuration", border_style="cyan"))
    console.print(f"[dim]Config file: {c.CONFIG_FILE}[/dim]")


def _run_set_config(arg: str) -> None:
    """
    فارسی: یک تنظیم را تغییر می‌دهد و روی فایل کانفیگ ذخیره می‌کند.
    English: Change one setting and save it to the config file.
    """
    try:
        key, value = parse_set_argument(arg)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        sys.exit(1)

    cfg = load_config()
    cfg[key] = value
    write_config(cfg)
    console.print(f"[green]✔ {key} set to {value!r}[/green]")


def main() -> None:
    args = build_arg_parser().parse_args()
    state.set_debug(args.debug)

    if args.doctor:
        run_doctor()
        sys.exit(0)

    if args.check_update:
        run_check_update()
        sys.exit(0)

    if args.update:
        run_update()
        sys.exit(0)

    if args.check_self_update:
        run_check_self_update()
        sys.exit(0)

    if args.config:
        _run_show_config()
        sys.exit(0)

    if args.set:
        _run_set_config(args.set)
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

    # فارسی: چک نبود URL باید قبل از منطق کوکی باشد، وگرنه کاربری که فقط
    #        می‌خواهد راهنما را ببیند، اول با پرامپت رمز عبور کوکی مواجه می‌شود.
    # English: The missing-URL check must come before the cookie logic,
    #          otherwise a user who just wants to see the help text is
    #          first confronted with a cookie master-password prompt.
    if not args.url:
        build_arg_parser().print_help()
        sys.exit(1)

    try_automatic_cookie_import(force=args.import_cookies)

    find_and_import_cookies_automatically(force=args.import_cookies)

    auto_cookies_path: Optional[str] = None
    auto_cleanup: c.CleanupFn = lambda: None
    if c.COOKIES_DEFAULT.exists():
        auto_cookies_path, auto_cleanup = secure_cookies_setup(auto=True)

    cfg = load_config()
    save_default_config()

    quality = args.quality if args.quality else cfg.get("quality", c.DEFAULT_QUALITY)
    if quality not in c.ALLOWED_QUALITIES:
        console.print(f"[red]Quality {quality} is not valid.[/red]")
        console.print(f"Allowed qualities: {', '.join(map(str, c.ALLOWED_QUALITIES))}")
        sys.exit(1)

    out_dir = args.output if args.output else cfg.get("download_dir", str(c.DOWNLOAD_DIR_DEFAULT))
    batch_size = args.batch if args.batch else cfg.get("batch_size", c.BATCH_SIZE)
    proxy = args.proxy if args.proxy else cfg.get("proxy")

    allow_client_fallback = not bool(args.player_client)

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

    if state.DEBUG:
        from rich.panel import Panel
        console.print(Panel(
            f"Python: {platform.python_version()}\n"
            f"odl: {c.ODL_VERSION}\n"
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
