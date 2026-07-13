"""
فارسی: توابع کمکی مشترک دانلود و منطق دانلود یک ویدیوی تکی (با نوار
       پیشرفت زنده و fallback خودکار کلاینت پخش).
English: Shared download helper functions and single-video download logic
         (with a live progress bar and automatic playback-client fallback).
"""

from __future__ import annotations

import traceback
from pathlib import Path
from typing import Optional, Tuple

import yt_dlp
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

from . import constants as c
from . import state
from .errors import CLIENT_FALLBACK_RETRYABLE_CATEGORIES, classify_error
from .logging_setup import log_download_error, log_info, log_warning
from .state import console


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
    فارسی: تنظیمات پیشرفته‌ی extractor_args یوتیوب را می‌سازد.
    English: Build advanced YouTube extractor_args.
    """
    args: dict = {"youtubetab": {"skip": ["authcheck"]}}

    if bypass:
        args["youtubetab"]["skip"].append("webpage")
        args["youtube"] = {"player_skip": ["webpage", "configs"]}

    if cfg.get("player_client"):
        clients = [x.strip() for x in cfg["player_client"].split(",") if x.strip()]
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
    ignore_errors: bool = True,
) -> dict:
    """
    فارسی:
        دیکشنری تنظیمات مشترک yt-dlp رو برای همه‌ی انواع دانلود می‌سازه.
        برای دانلود تکی باید ignore_errors=False داده بشه، وگرنه ممکنه
        خطای واقعی بی‌صدا مخفی بمونه؛ فقط برای پلی‌لیست باید True باشه.
    English:
        Build the shared yt-dlp options dict used by every download kind.
        For single downloads, ignore_errors must be False, otherwise a
        real error could be silently swallowed; it should only be True
        for playlists.
    """
    opts = {
        "format": "bestaudio/best" if audio_only else build_format(quality),
        "outtmpl": out_template,
        "continuedl": True,
        "retries": "infinite",
        "fragment_retries": "infinite",
        "noprogress": True,
        "quiet": True,
        "no_warnings": True,
        "ignoreerrors": ignore_errors,
        "extractor_args": extractor_args,
    }
    if cookies_path:
        opts["cookiefile"] = cookies_path
    if proxy:
        opts["proxy"] = proxy

    postprocessors = []
    if audio_only:
        postprocessors.append(
            {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}
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
    فارسی: یک ویدیوی تکی رو با نوار پیشرفت زنده دانلود می‌کنه.
    English: Download a single video with a live progress bar.
    """
    if not is_youtube_url(url):
        console.print("[red]This does not look like a valid YouTube URL.[/red]")
        return False

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    out_template = str(out_path / "%(title)s.%(ext)s")

    log_info(f"Starting single download: {url}")

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
                cookies_path, quality, sub_en, sub_fa, out_template, audio_only, proxy,
                current_extractor_args, ignore_errors=False,
            )
            opts["progress_hooks"] = [hook]
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    ydl.download([url])
                return True, None
            except Exception as e:
                if state.DEBUG:
                    console.print("[red]--- DEBUG: full traceback ---[/red]")
                    traceback.print_exc()
                return False, str(e)

        tried_clients: list[str] = ["default"]
        ok, err = attempt(extractor_args)

        if not ok and allow_client_fallback:
            category = classify_error(err or "")
            if category in CLIENT_FALLBACK_RETRYABLE_CATEGORIES:
                for client in c.PLAYER_CLIENT_FALLBACK_CHAIN:
                    progress.update(task_id, title=f"Retrying with '{client}' client...")
                    log_warning(f"Retrying {url} with player_client={client}")
                    tried_clients.append(client)
                    fallback_args = dict(extractor_args)
                    fallback_args["youtube"] = {"player_client": [client]}
                    ok, err = attempt(fallback_args)
                    if ok:
                        break

        if ok:
            progress.update(task_id, title="[green]✔ Done[/green]")
            log_info(f"Successfully downloaded: {url}")
            return True

        category = classify_error(err or "")
        suggestion = _suggestion_for_category(category)
        console.print(f"\n[red]✘ Download failed[/red]")
        console.print(f"[yellow]Reason:[/yellow] {category}")
        if len(tried_clients) > 1:
            console.print(f"[yellow]Tried clients:[/yellow] {', '.join(tried_clients)}")
        if suggestion:
            console.print(f"[cyan]Suggestion:[/cyan] {suggestion}")
        log_download_error(url, f"[{category}] {err}")
        return False


def _suggestion_for_category(category: str) -> str:
    """
    فارسی: بر اساس دسته‌ی خطا، یک پیشنهاد کوتاه و عملی به کاربر می‌دهد.
    English: Give a short, actionable suggestion to the user based on the error category.
    """
    from .errors import ErrorCategory

    suggestions = {
        ErrorCategory.BOT_DETECTED: "Run 'odl --import-cookies' to refresh your cookies, or use --player-client android.",
        ErrorCategory.LOGIN_REQUIRED: "Run 'odl --import-cookies' to refresh your cookies.",
        ErrorCategory.COOKIE_INVALID: "Run 'odl --import-cookies' to refresh your cookies.",
        ErrorCategory.REGION_LOCKED: "Try again with a proxy in an allowed country: odl -x <proxy> <URL>.",
        ErrorCategory.NETWORK_ERROR: "Check your internet connection and try again.",
        ErrorCategory.PROXY_ERROR: "Check that your proxy is running and reachable.",
        ErrorCategory.PRIVATE_VIDEO: "This video is private; nothing can be done from this side.",
        ErrorCategory.DELETED_VIDEO: "This video was deleted or made unavailable by its owner.",
        ErrorCategory.MEMBERS_ONLY: "This video requires a paid channel membership.",
    }
    return suggestions.get(category, "Run 'odl --doctor' to check your installation, or 'odl --debug' for details.")
