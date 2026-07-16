"""
فارسی: توابع کمکی مشترک دانلود و منطق دانلود یک ویدیوی تکی (با نوار
       پیشرفت زنده و fallback خودکار کلاینت پخش).
English: Shared download helper functions and single-video download logic
         (with a live progress bar and automatic playback-client fallback).
"""

from __future__ import annotations

import traceback
from pathlib import Path

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
from .logging_setup import log_debug_traceback, log_download_error, log_info, log_warning
from .models import DownloadEvent, DownloadEventCallback, DownloadRequest, DownloadResult
from .state import console


def build_format(quality: int) -> str:
    """
    فارسی: رشته‌ی فرمت yt-dlp رو بر اساس سقف کیفیت انتخابی می‌سازه.
    English: Build the yt-dlp format string for a given max resolution.
    """
    return f"bestvideo[height<={quality}]+bestaudio/best[height<={quality}]"


def is_youtube_url(url: str) -> bool:
    """
    فارسی: بررسی سطحی می‌کنه که آیا لینک متعلق به یوتیوبه یا نه. این تابع
           دیگه برای رد کردن لینک‌های غیریوتیوب استفاده نمی‌شه (odl از هر
           سایتی که yt-dlp پشتیبانی می‌کنه — بیش از ۱۸۰۰ تا — دانلود
           می‌کنه)؛ فقط برای تصمیم‌گیری در مورد این‌که آیا منطق fallback
           بین کلاینت‌های پخش یوتیوب (که مفهومی کاملاً مخصوص یوتیوبه)
           باید فعال بشه یا نه، استفاده می‌شه.
    English: Loosely check whether the given URL belongs to YouTube. This
             is no longer used to reject non-YouTube links (odl downloads
             from any site yt-dlp supports — 1800+ of them); it's only
             used to decide whether the YouTube-specific playback-client
             fallback logic (a concept that only makes sense for YouTube)
             should be enabled.
    """
    return any(domain in url for domain in ("youtube.com", "youtu.be"))


def human_size(num_bytes: float | None) -> str:
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


def resolve_video_url(entry: dict) -> str | None:
    """
    فارسی: از یک entry برگشتی حالت flat-playlist (هر سایتی که yt-dlp
           پشتیبانی می‌کنه، نه فقط یوتیوب)، لینک کامل رو می‌سازه.
           اولویت با webpage_url است چون تقریباً همه‌ی extractorهای
           yt-dlp این فیلد رو با یک URL کامل و مستقیم پر می‌کنن. اگه
           نبود، از url استفاده می‌شه (اگه خودش با http شروع بشه). فقط
           به‌عنوان آخرین راه‌حل، اگه هیچ‌کدوم در دسترس نبود ولی id
           داشتیم، الگوی واچ‌یوتیوب رو امتحان می‌کنیم (چون این تابع
           اصلش فقط برای پلی‌لیست یوتیوب نوشته شده بود، برای وقتی که
           extractor دیگه‌ای هم به‌ندرت دقیقاً همین حالت رو داشته باشه).
    English: Build a full URL from a flat-playlist entry (any site
             yt-dlp supports, not just YouTube). webpage_url is preferred
             since nearly every yt-dlp extractor fills it with a direct,
             complete URL. Falls back to url (if it already starts with
             http). Only as a last resort, if neither is available but we
             have an id, try the YouTube watch-URL pattern (since this
             function was originally YouTube-playlist-only, for the rare
             case another extractor ends up in exactly that same shape).
    """
    webpage_url = entry.get("webpage_url")
    if webpage_url:
        return webpage_url
    url = entry.get("url")
    if url and url.startswith("http"):
        return url
    video_id = entry.get("id")
    if video_id:
        return f"https://www.youtube.com/watch?v={video_id}"
    return url or None


def build_extractor_args(cfg: dict, bypass: bool = False) -> dict:
    """
    فارسی: تنظیمات پیشرفته‌ی extractor_args یوتیوب را می‌سازد. این مقادیر
           فقط وقتی لینک واقعاً یوتیوب باشه توسط yt-dlp استفاده می‌شن؛
           برای هر سایت دیگه‌ای yt-dlp خودش این کلیدها رو نادیده می‌گیره،
           پس بی‌ضرر و بدون تأثیرن.
    English: Build advanced YouTube extractor_args. These are only used
             by yt-dlp when the link is actually YouTube; for any other
             site yt-dlp simply ignores these keys, so they're harmless
             no-ops.
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
    cookies_path: str | None,
    quality: int,
    sub_en: bool,
    sub_fa: bool,
    out_template: str,
    audio_only: bool,
    proxy: str | None,
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
        # فارسی: عدد محدود (نه بی‌نهایت واقعی). قبلاً اینجا رشته‌ی
        #        "infinite" بود که فقط از خط فرمان yt-dlp به float('inf')
        #        تبدیل می‌شه، نه از API پایتون که ما استفاده می‌کنیم —
        #        همون چیزی که باعث TypeError در دانلود HLS (مثل Vimeo)
        #        می‌شد. بعد به float('inf') واقعی فیکس شد، ولی مشکل
        #        دیگه‌ای داشت: روی یه لینک واقعاً مرده، برنامه بدون هیچ
        #        خطایی تا ابد گیر می‌کرد. yt-dlp خودش بین هر retry
        #        backoff (تأخیر تصاعدی) می‌ذاره، پس نیازی به منطق backoff
        #        دستی نداریم؛ فقط باید یه سقف داشته باشیم.
        # English: A bounded number, not true infinity. This used to be
        #          the string "infinite", which is only converted to
        #          float('inf') by yt-dlp's own CLI, not the Python API we
        #          use — that caused a TypeError on HLS downloads (e.g.
        #          Vimeo). It was then fixed to real float('inf'), but
        #          that had its own problem: on a genuinely dead link, the
        #          program would hang forever with no error. yt-dlp
        #          already backs off (exponential delay) between retries
        #          on its own, so no custom backoff logic is needed here;
        #          we just need a ceiling.
        "retries": c.MAX_RETRIES,
        "fragment_retries": c.MAX_RETRIES,
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
        postprocessors.append({"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"})

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


def attempt_download_with_fallback(
    request: DownloadRequest,
    ignore_errors: bool,
    on_event: DownloadEventCallback | None = None,
) -> DownloadResult:
    """
    فارسی:
        هسته‌ی خالص دانلود با تلاش مجدد و fallback خودکار کلاینت پخش —
        بدون هیچ وابستگی به Rich، console، یا ترمینال. این تابع مشترک
        هم توسط دانلود تکی (پایین همین فایل) و هم توسط هر ویدیوی پلی‌لیست
        (در playlist.py) استفاده می‌شود؛ قبلاً این منطق در دو جا کپی شده بود.
        پیشرفت و تغییرات وضعیت از طریق callback اختیاری on_event گزارش می‌شود
        تا CLI با Rich، GUI با Qt signal، و اندروید با Callback کاتلین بتوانند
        هرکدام به روش خودشان نمایشش بدهند.
    English:
        Pure download core with retry and automatic playback-client
        fallback — no dependency on Rich, console, or a terminal. This
        function is shared by both single-video download (below in this
        file) and each playlist video (in playlist.py); this logic used
        to be duplicated in both places. Progress and status changes are
        reported through the optional on_event callback so the CLI (Rich),
        GUI (Qt signal), and Android (Kotlin callback) can each display
        it in their own way.
    """

    def hook(d: dict) -> None:
        if on_event is None:
            return
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            downloaded = d.get("downloaded_bytes", 0)
            info = d.get("info_dict") or {}
            on_event(
                DownloadEvent(
                    kind="progress",
                    downloaded_bytes=downloaded,
                    total_bytes=total,
                    title=info.get("title"),
                )
            )
        elif d["status"] == "finished":
            on_event(DownloadEvent(kind="status", message="finalizing"))

    def attempt(current_extractor_args: dict) -> tuple[bool, str | None]:
        opts = ydl_opts_base(
            request.cookies_path,
            request.quality,
            request.sub_en,
            request.sub_fa,
            request.out_template,
            request.audio_only,
            request.proxy,
            current_extractor_args,
            ignore_errors=ignore_errors,
        )
        opts["progress_hooks"] = [hook]
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([request.url])
            return True, None
        except Exception as e:
            # فارسی: traceback همیشه در فایل لاگ ذخیره می‌شود؛ چاپ روی ترمینال
            #        دیگر اینجا انجام نمی‌شود چون این تابع دیگر UI-agnostic است
            #        (تصمیم چاپ یا نه، بر عهده‌ی لایه‌ی CLI/GUI باقی می‌ماند).
            # English: The traceback is always persisted to the log file;
            #          printing to the terminal no longer happens here since
            #          this function is now UI-agnostic (whether to print is
            #          left to the CLI/GUI layer).
            log_debug_traceback(traceback.format_exc())
            return False, str(e)

    tried_clients: list = ["default"]
    ok, err = attempt(request.extractor_args)

    # فارسی: fallback بین کلاینت‌های پخش («android»، «web»، ...) یک مفهوم
    #        کاملاً مخصوص یوتیوبه؛ برای هر سایت دیگه‌ای امتحانش کردن فقط
    #        همون خطای اول رو با تأخیر بیشتر تکرار می‌کنه، بدون فایده.
    # English: Playback-client fallback ("android", "web", ...) is a
    #          YouTube-only concept; trying it for any other site would
    #          just repeat the same failure with extra delay, for nothing.
    if not ok and request.allow_client_fallback and is_youtube_url(request.url):
        category = classify_error(err or "")
        if category in CLIENT_FALLBACK_RETRYABLE_CATEGORIES:
            for client in c.PLAYER_CLIENT_FALLBACK_CHAIN:
                if on_event is not None:
                    on_event(DownloadEvent(kind="retry", client=client))
                log_warning(f"Retrying {request.url} with player_client={client}")
                tried_clients.append(client)
                fallback_args = dict(request.extractor_args)
                fallback_args["youtube"] = {"player_client": [client]}
                ok, err = attempt(fallback_args)
                if ok:
                    break

    if ok:
        return DownloadResult(ok=True, tried_clients=tried_clients)

    category = classify_error(err or "")
    return DownloadResult(ok=False, error_message=err, error_category=category, tried_clients=tried_clients)


def download_single(
    url: str,
    cookies_path: str | None,
    quality: int,
    sub_en: bool,
    sub_fa: bool,
    out_dir: str,
    audio_only: bool,
    proxy: str | None,
    extractor_args: dict,
    allow_client_fallback: bool,
) -> bool:
    """
    فارسی: یک ویدیوی تکی رو با نوار پیشرفت زنده دانلود می‌کنه.
           این تابع فقط یک wrapper نازک روی Rich است؛ منطق واقعی در
           attempt_download_with_fallback (بالا) قرار دارد. امضای این
           تابع عمداً بدون تغییر باقی مانده تا نقطه‌ی فراخوانی در cli.py
           نیازی به تغییر نداشته باشد.
    English: Download a single video with a live progress bar. This is now
             just a thin Rich wrapper; the real logic lives in
             attempt_download_with_fallback (above). This function's
             signature was deliberately kept unchanged so the call site in
             cli.py doesn't need to change.
    """
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    out_template = str(out_path / "%(title)s.%(ext)s")

    log_info(f"Starting single download: {url}")

    request = DownloadRequest(
        url=url,
        out_template=out_template,
        cookies_path=cookies_path,
        quality=quality,
        sub_en=sub_en,
        sub_fa=sub_fa,
        audio_only=audio_only,
        proxy=proxy,
        extractor_args=extractor_args,
        allow_client_fallback=allow_client_fallback,
    )

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

        def on_event(evt: DownloadEvent) -> None:
            if evt.kind == "progress":
                if evt.total_bytes:
                    progress.update(task_id, total=evt.total_bytes, completed=evt.downloaded_bytes)
                if evt.title:
                    progress.update(task_id, title=evt.title[:40])
            elif evt.kind == "status":
                progress.update(task_id, title="Finalizing (merge)...")
            elif evt.kind == "retry":
                progress.update(task_id, title=f"Retrying with '{evt.client}' client...")

        if state.DEBUG:
            console.print(f"[dim]Debug: full traceback for any failure is in {c.LOG_DIR}[/dim]")

        result = attempt_download_with_fallback(request, ignore_errors=False, on_event=on_event)

        if result.ok:
            progress.update(task_id, title="[green]✔ Done[/green]")
            log_info(f"Successfully downloaded: {url}")
            return True

        suggestion = _suggestion_for_category(result.error_category or "")
        console.print("\n[red]✘ Download failed[/red]")
        console.print(f"[yellow]Reason:[/yellow] {result.error_category}")
        if len(result.tried_clients) > 1:
            console.print(f"[yellow]Tried clients:[/yellow] {', '.join(result.tried_clients)}")
        if suggestion:
            console.print(f"[cyan]Suggestion:[/cyan] {suggestion}")
        log_download_error(url, f"[{result.error_category}] {result.error_message}")
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
