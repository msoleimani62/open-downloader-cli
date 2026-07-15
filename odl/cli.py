"""
فارسی: پارسر آرگومان‌های خط فرمان و تابع main() که همه‌ی ماژول‌های دیگر را به هم متصل می‌کند.
English: The command-line argument parser and the main() function that wires all other modules together.
"""

from __future__ import annotations

import argparse
import platform
import sys

import yt_dlp

from . import constants as c
from . import state
from .config import load_config, parse_set_argument, save_default_config, write_config
from .cookies import (
    CookieError,
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
from .proxy_pool import ProxyPoolError, load_proxy_candidates, resolve_working_proxy, save_cached_proxy, test_proxy
from .state import console


def build_arg_parser() -> argparse.ArgumentParser:
    """
    فارسی: پارسر آرگومان‌های خط فرمان را می‌سازد.
    English: Build the command-line argument parser.
    """
    parser = argparse.ArgumentParser(
        prog="odl",
        description="Open Downloader CLI (odl) — a simple, resumable downloader built on "
        "yt-dlp, for any site yt-dlp supports (not just YouTube)",
    )
    parser.add_argument("url", nargs="?", help="video or playlist URL (any site yt-dlp supports)")
    parser.add_argument("-p", "--playlist", action="store_true", help="playlist mode")
    parser.add_argument(
        "-q",
        "--quality",
        type=int,
        default=None,
        help=f"video quality: {', '.join(map(str, c.ALLOWED_QUALITIES))}",
    )
    parser.add_argument("-s", "--sub-en", action="store_true", help="download English subtitles")
    parser.add_argument("-fs", "--sub-fa", action="store_true", help="download Persian subtitles (if available)")
    parser.add_argument("-a", "--audio-only", action="store_true", help="audio only (mp3)")
    parser.add_argument("-o", "--output", type=str, default=None, help="custom output directory")
    parser.add_argument("-b", "--batch", type=int, default=None, help="number of concurrent downloads in playlist mode")
    parser.add_argument(
        "-x",
        "--proxy",
        type=str,
        default=None,
        help="proxy address, e.g. socks5h://127.0.0.1:9050",
    )
    parser.add_argument(
        "--proxy-pool",
        type=str,
        default=None,
        metavar="FILE_OR_URL",
        help="a local file or URL with one proxy per line; odl will automatically "
        "test, cache, and rotate through them (beginners: no need to know "
        "which proxy actually works)",
    )
    parser.add_argument(
        "--proxy-pool-refresh",
        action="store_true",
        help="ignore the cached proxy and re-scan the whole --proxy-pool source",
    )
    parser.add_argument(
        "--test-proxies",
        action="store_true",
        help="test every proxy in --proxy-pool (or the configured proxy_pool_source) "
        "and show which ones work, without downloading anything",
    )
    parser.add_argument(
        "--player-client",
        type=str,
        default=None,
        help="force a specific YouTube playback client, e.g. 'android' (helps bypass bot detection)",
    )
    parser.add_argument(
        "--bypass",
        action="store_true",
        help="lighter/faster extraction that skips extra YouTube webpage requests (may miss some formats or subtitles)",
    )
    parser.add_argument(
        "--secure-cookies",
        action="store_true",
        help="encrypt the current cookies.txt file and store a secure version",
    )
    parser.add_argument(
        "--reset-cookies",
        action="store_true",
        help="delete the encrypted cookie file (use this if you forgot the master password)",
    )
    parser.add_argument(
        "--import-cookies",
        action="store_true",
        help="force a fresh automatic cookie import even if an encrypted cookie file already exists",
    )
    parser.add_argument(
        "--cookie-status",
        action="store_true",
        help="show whether cookies are encrypted/plaintext/missing and when they were imported",
    )
    parser.add_argument(
        "--no-estimate",
        action="store_true",
        help="skip the (potentially slow) total-size estimation step for large playlists",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="show detailed diagnostic info and full tracebacks on error",
    )
    parser.add_argument(
        "--doctor",
        action="store_true",
        help="check the health of the installation (Python, yt-dlp, ffmpeg, cookies, permissions)",
    )
    parser.add_argument(
        "--check-update",
        action="store_true",
        help="check whether a newer yt-dlp version is available, without installing it",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="update yt-dlp to the latest version",
    )
    parser.add_argument(
        "--check-self-update",
        action="store_true",
        help="check whether a newer version of Open Downloader CLI itself is available",
    )
    parser.add_argument(
        "--config",
        action="store_true",
        help="show the current configuration settings",
    )
    parser.add_argument(
        "--set",
        type=str,
        default=None,
        metavar="KEY=VALUE",
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


def _run_test_proxies(source: str) -> None:
    """
    فارسی: تمام کاندیدهای منبع پروکسی را تست می‌کند، نتیجه را در یک جدول
           نشان می‌دهد، و اولین پروکسی سالم را کش می‌کند. دانلودی انجام
           نمی‌شود؛ فقط برای دیدن وضعیت پروکسی‌ها قبل از یک دانلود واقعی است.
    English: Test every candidate from the proxy source, show the results
             in a table, and cache the first working one. No download
             happens; this is only for checking proxy status before a real
             download.
    """
    from rich.table import Table

    console.print(f"[cyan]Testing proxies from: {source}[/cyan]")
    try:
        candidates = load_proxy_candidates(source)
    except ProxyPoolError as e:
        console.print(f"[red]{e}[/red]")
        return

    table = Table(title="Proxy Test Results")
    table.add_column("#", justify="right")
    table.add_column("Proxy")
    table.add_column("Status", justify="center")
    table.add_column("Latency", justify="right")

    first_working: str | None = None
    for i, candidate in enumerate(candidates, start=1):
        console.print(f"[dim]Testing {i}/{len(candidates)}: {candidate}...[/dim]")
        result = test_proxy(candidate)
        if result.ok:
            latency = f"{result.latency_ms:.0f} ms" if result.latency_ms is not None else "-"
            table.add_row(str(i), candidate, "[green]✔ works[/green]", latency)
            if first_working is None:
                first_working = candidate
        else:
            table.add_row(str(i), candidate, "[red]✘ failed[/red]", "-")

    console.print(table)

    if first_working:
        save_cached_proxy(source, first_working)
        console.print(f"[green]✔ Cached working proxy for next time: {first_working}[/green]")
    else:
        console.print("[red]None of the proxies worked.[/red]")


def _resolve_proxy_via_pool(source: str, force_refresh: bool) -> str | None:
    """
    فارسی: پروکسی سالم را از استخر می‌گیرد و پیشرفت تست را روی ترمینال
           نشان می‌دهد. اگر منبع در دسترس نبود یا هیچ پروکسی کار نکرد،
           فاتال نیست — بدون پروکسی ادامه داده می‌شود.
    English: Get a working proxy from the pool and show test progress on
             the terminal. If the source is unreachable or no proxy works,
             it's not fatal — continues without a proxy.
    """

    def on_event(i: int, total: int, result) -> None:
        if i == 0:
            status = "[green]✔ still works[/green]" if result.ok else "[yellow]✘ dead now[/yellow]"
            console.print(f"[dim]Re-checking cached proxy {result.proxy}: {status}[/dim]")
        else:
            status = "[green]✔[/green]" if result.ok else "[red]✘[/red]"
            console.print(f"[dim]{status} proxy {i}/{total}: {result.proxy}[/dim]")

    try:
        proxy = resolve_working_proxy(source, force_refresh=force_refresh, on_event=on_event)
    except ProxyPoolError as e:
        console.print(f"[red]Proxy pool error: {e}[/red]")
        return None

    if proxy is None:
        console.print("[yellow]No working proxy found in the pool; continuing without a proxy.[/yellow]")
    return proxy


def _noop_cleanup() -> None:
    """
    فارسی: تابع cleanup پیش‌فرض وقتی هنوز فایل موقت کوکی‌ای ساخته نشده.
    English: Default no-op cleanup before any temp cookie file exists.
    """
    return None


def _exit_on_cookie_error(e: CookieError) -> None:
    """
    فارسی: پیام CookieError را روی ترمینال نشان می‌دهد و با کد ۱ خارج
           می‌شود. این تنها جایی‌ست که چنین خطایی به بستن کامل پردازه
           منجر می‌شود؛ لایه‌ی core (cookies.py) دیگر خودش sys.exit صدا
           نمی‌زند — یعنی وقتی این تابع از داخل یک GUI صدا زده بشه، به‌جای
           همین سه خط، می‌شه یه دیالوگ خطا نشون داد بدون این‌که کل اپ ببنده.
    English: Print the CookieError's message and exit with code 1. This is
             the only place such an error results in killing the whole
             process; the core layer (cookies.py) no longer calls
             sys.exit itself — meaning when this is called from a GUI
             context instead, these three lines can become an error
             dialog without the whole app disappearing.
    """
    console.print(f"[red]{e}[/red]")
    sys.exit(1)


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

    if args.test_proxies:
        cfg_for_proxy_test = load_config()
        source = args.proxy_pool or cfg_for_proxy_test.get("proxy_pool_source")
        if not source:
            console.print(
                "[red]No proxy pool source given. Use --proxy-pool <file_or_url>, "
                "or set a default with 'odl --set proxy_pool_source=<file_or_url>'.[/red]"
            )
            sys.exit(1)
        _run_test_proxies(source)
        sys.exit(0)

    if args.cookie_status:
        print_cookie_status()
        sys.exit(0)

    if args.reset_cookies:
        reset_encrypted_cookies()
        sys.exit(0)

    if args.secure_cookies:
        try:
            secure_cookies_setup()
        except CookieError as e:
            _exit_on_cookie_error(e)
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

    auto_cookies_path: str | None = None
    auto_cleanup: c.CleanupFn = _noop_cleanup
    if c.COOKIES_DEFAULT.exists():
        try:
            auto_cookies_path, auto_cleanup = secure_cookies_setup(auto=True)
        except CookieError as e:
            _exit_on_cookie_error(e)

    cfg = load_config()
    save_default_config()

    quality = args.quality if args.quality is not None else cfg.get("quality", c.DEFAULT_QUALITY)
    if quality not in c.ALLOWED_QUALITIES:
        console.print(f"[red]Quality {quality} is not valid.[/red]")
        console.print(f"Allowed qualities: {', '.join(map(str, c.ALLOWED_QUALITIES))}")
        sys.exit(1)

    out_dir = args.output if args.output else cfg.get("download_dir", str(c.DOWNLOAD_DIR_DEFAULT))
    batch_size = args.batch if args.batch is not None else cfg.get("batch_size", c.BATCH_SIZE)
    # فارسی: این چک صرفاً برای --set نیست؛ فایل کانفیگ ممکن است دستی
    #        ویرایش شده باشد، پس باید همینجا هم دوباره اعتبارسنجی شود
    #        وگرنه playlist.py با batch_size<=0 کرش می‌کند.
    # English: This check is not only for --set; the config file may have
    #          been hand-edited, so it must be re-validated here as well,
    #          otherwise playlist.py crashes with batch_size<=0.
    if batch_size < 1:
        console.print(f"[red]batch_size must be 1 or greater, got {batch_size}.[/red]")
        sys.exit(1)

    # فارسی: اولویت پروکسی: (۱) --proxy صریح همیشه برنده است، (۲) اگر
    #        استخر پروکسی تنظیم شده، پروکسی سالم را خودکار پیدا می‌کند،
    #        (۳) در غیر این صورت پروکسی ثابتِ کانفیگ (اگر باشد).
    # English: Proxy priority: (1) an explicit --proxy always wins, (2) if
    #          a proxy pool is configured, automatically find a working
    #          proxy, (3) otherwise the static config proxy (if any).
    proxy_pool_source = args.proxy_pool or cfg.get("proxy_pool_source")
    if args.proxy:
        proxy = args.proxy
    elif proxy_pool_source:
        proxy = _resolve_proxy_via_pool(proxy_pool_source, args.proxy_pool_refresh)
    else:
        proxy = cfg.get("proxy")

    allow_client_fallback = not bool(args.player_client)

    if args.player_client:
        cfg["player_client"] = args.player_client
    bypass = args.bypass or cfg.get("bypass", False)
    extractor_args = build_extractor_args(cfg, bypass)

    if auto_cookies_path:
        cookies_path, cleanup_cookies = auto_cookies_path, auto_cleanup
    else:
        try:
            cookies_path, cleanup_cookies = resolve_cookies_path(cfg)
        except CookieError as e:
            _exit_on_cookie_error(e)

    if cookies_path is None:
        print_cookie_export_guide()

    if state.DEBUG:
        from rich.panel import Panel

        console.print(
            Panel(
                f"Python: {platform.python_version()}\n"
                f"odl: {c.ODL_VERSION}\n"
                f"yt-dlp: {getattr(yt_dlp.version, '__version__', 'unknown')}\n"
                f"OS: {platform.system()} {platform.release()}\n"
                f"Proxy: {proxy or 'none'}\n"
                f"Player client override: {cfg.get('player_client') or 'auto'}\n"
                f"Cookies: {'yes' if cookies_path else 'no'}\n"
                f"Quality: {quality}p\n"
                f"Extractor args: {extractor_args}",
                title="DEBUG INFO",
                border_style="magenta",
            )
        )

    try:
        if args.playlist:
            download_playlist(
                args.url,
                cookies_path,
                quality,
                args.sub_en,
                args.sub_fa,
                out_dir,
                args.audio_only,
                batch_size,
                proxy,
                extractor_args,
                allow_client_fallback,
                args.no_estimate,
            )
        else:
            download_single(
                args.url,
                cookies_path,
                quality,
                args.sub_en,
                args.sub_fa,
                out_dir,
                args.audio_only,
                proxy,
                extractor_args,
                allow_client_fallback,
            )
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopped. Run the same command again to resume automatically.[/yellow]")
        sys.exit(130)
    finally:
        cleanup_cookies()
