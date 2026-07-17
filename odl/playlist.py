"""
فارسی: دریافت لیست ویدیوهای پلی‌لیست، تخمین حجم، دانلود دسته‌ای، و خلاصه‌ی نهایی.
       این ماژول به دو لایه تقسیم شده: توابع خالص (بدون هیچ وابستگی به Rich/
       ترمینال) که در بالای فایل قرار دارند و توسط CLI، GUI آینده، و لایه‌ی
       Android به یک شکل قابل استفاده‌اند؛ و download_playlist در پایین فایل
       که فقط یک wrapper نازک روی Rich است و همان توابع خالص را صدا می‌زند.
English: Fetching playlist video entries, size estimation, batch downloads,
         and the final summary. This module is split into two layers: pure
         functions (no dependency on Rich/the terminal) at the top of the
         file, usable identically by the CLI, a future GUI, and the Android
         layer; and download_playlist at the bottom, which is just a thin
         Rich wrapper calling those same pure functions.
"""

from __future__ import annotations

import concurrent.futures
import time
from pathlib import Path

import yt_dlp
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

from .downloader import attempt_download_with_fallback, build_format, human_size, resolve_video_url
from .logging_setup import log_download_error, log_info, log_warning
from .models import (
    DownloadEvent,
    DownloadRequest,
    PlaylistDownloadEvent,
    PlaylistEventCallback,
    PlaylistItemResult,
)
from .playlist_state import clear_state, load_completed_ids, mark_completed
from .state import console

# =============================================================================
# فارسی: لایه‌ی خالص (UI-agnostic) — بدون هیچ import از rich.console،
#        بدون Confirm.ask، بدون console.print. این توابع همان چیزی هستند
#        که دسکتاپ‌جی‌یوآی (PySide6) و لایه‌ی Chaquopy روی اندروید مستقیماً
#        صدا خواهند زد.
# English: Pure (UI-agnostic) layer — no import of rich's console, no
#          Confirm.ask, no console.print. These are the exact functions the
#          desktop GUI (PySide6) and the Android Chaquopy layer will call
#          directly.
# =============================================================================


def fetch_playlist_entries(
    url: str, cookies_path: str | None, proxy: str | None, extractor_args: dict
) -> tuple[list, str]:
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
    url: str, cookies_path: str | None, quality: int, audio_only: bool, proxy: str | None, extractor_args: dict
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
        return 0


def estimate_playlist_size(
    entries: list,
    cookies_path: str | None,
    quality: int,
    audio_only: bool,
    proxy: str | None,
    extractor_args: dict,
    on_event: PlaylistEventCallback | None = None,
) -> int:
    """
    فارسی: حجم تخمینی کل پلی‌لیست را با جمع زدن حجم تک‌تک ویدیوها محاسبه
           می‌کند. پیشرفت از طریق callback اختیاری on_event گزارش می‌شود
           (رویداد "estimate_progress") تا CLI با یک اسپینر Rich، و GUI با
           یک progress bar واقعی نمایشش دهد.
    English: Compute the playlist's estimated total size by summing each
             video's individual size. Progress is reported through the
             optional on_event callback ("estimate_progress" events) so the
             CLI can show a Rich spinner and a GUI can show a real progress
             bar.
    """
    total_size = 0
    count = len(entries)
    for i, entry in enumerate(entries):
        video_url = resolve_video_url(entry)
        if video_url:
            total_size += estimate_size(video_url, cookies_path, quality, audio_only, proxy, extractor_args)
        if on_event is not None:
            on_event(PlaylistDownloadEvent(kind="estimate_progress", checked=i + 1, total=count))
    return total_size


def execute_playlist_download(
    url: str,
    entries: list,
    out_path: Path,
    cookies_path: str | None,
    quality: int,
    sub_en: bool,
    sub_fa: bool,
    audio_only: bool,
    batch_size: int,
    proxy: str | None,
    extractor_args: dict,
    allow_client_fallback: bool,
    completed_ids: set[str],
    on_event: PlaylistEventCallback | None = None,
) -> list[PlaylistItemResult]:
    """
    فارسی: هسته‌ی خالص دانلود دسته‌ای پلی‌لیست — بدون هیچ وابستگی به Rich،
           console، یا ورودی/تأیید کاربر (آن تصمیم قبلاً توسط لایه‌ی UI
           گرفته شده و اینجا فقط دانلود واقعی انجام می‌شود). دسته‌ها
           (batch) به‌صورت پشت‌سرهم پردازش می‌شوند و در هر دسته، ویدیوها
           با ThreadPoolExecutor موازی دانلود می‌شوند — دقیقاً همان
           رفتاری که قبلاً مستقیم در download_playlist بود. هر رویداد
           (شروع دسته، پیشرفت یک آیتم، تلاش مجدد، پایان یک آیتم) از طریق
           on_event گزارش می‌شود تا لایه‌ی UI (نوار پیشرفت Rich، Qt signal،
           یا callback کاتلین) خودش تصمیم بگیرد چطور نمایشش دهد.
    English: The pure playlist batch-download core — no dependency on
             Rich, console, or user confirmation (that decision was already
             made by the UI layer; this only performs the actual download).
             Batches are processed sequentially, and within each batch
             videos download concurrently via a ThreadPoolExecutor —
             exactly the behavior that used to live directly inside
             download_playlist. Every event (batch starting, a single
             item's progress, a retry, an item finishing) is reported
             through on_event so the UI layer (a Rich progress bar, a Qt
             signal, or a Kotlin callback) can decide how to display it.
    """
    results: list[PlaylistItemResult] = []
    videos = [
        (i + 1, resolve_video_url(entry), entry.get("title") or "untitled", entry.get("id"))
        for i, entry in enumerate(entries)
    ]

    for batch_start in range(0, len(videos), batch_size):
        batch = videos[batch_start : batch_start + batch_size]

        if on_event is not None:
            on_event(
                PlaylistDownloadEvent(kind="batch_start", batch=[(idx, title) for idx, _, title, _ in batch])
            )

        def worker(idx: int, video_url: str | None, title: str, video_id: str | None) -> PlaylistItemResult:
            if not video_url:
                result = PlaylistItemResult(index=idx, title=title, ok=False, error_category="Invalid URL")
                if on_event is not None:
                    on_event(PlaylistDownloadEvent(kind="item_done", index=idx, title=title, result=result))
                return result

            if video_id and video_id in completed_ids:
                result = PlaylistItemResult(index=idx, title=title, ok=True, note="resumed")
                if on_event is not None:
                    on_event(PlaylistDownloadEvent(kind="item_done", index=idx, title=title, result=result))
                return result

            out_template = str(out_path / f"{idx:03d} - %(title)s.%(ext)s")

            def on_download_event(evt: DownloadEvent) -> None:
                if on_event is None:
                    return
                if evt.kind == "progress":
                    on_event(
                        PlaylistDownloadEvent(
                            kind="item_progress",
                            index=idx,
                            title=title,
                            downloaded_bytes=evt.downloaded_bytes,
                            total_bytes=evt.total_bytes,
                        )
                    )
                elif evt.kind == "status":
                    on_event(PlaylistDownloadEvent(kind="item_status", index=idx, title=title))
                elif evt.kind == "retry":
                    # فارسی: خود attempt_download_with_fallback هم این تلاش مجدد را
                    #        در فایل لاگ ثبت می‌کند؛ اینجا فقط برای اطلاع لایه‌ی UI
                    #        (مثلاً نمایش «در حال تلاش مجدد...» روی نوار پیشرفت) است.
                    # English: attempt_download_with_fallback already logs this retry
                    #          to the log file; this is only to notify the UI layer
                    #          (e.g. showing "retrying..." on the progress bar).
                    on_event(
                        PlaylistDownloadEvent(kind="item_retry", index=idx, title=title, client=evt.client)
                    )

            request = DownloadRequest(
                url=video_url,
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
            dl_result = attempt_download_with_fallback(request, ignore_errors=True, on_event=on_download_event)

            if dl_result.ok:
                mark_completed(url, video_id)
                result = PlaylistItemResult(index=idx, title=title, ok=True)
            else:
                category = dl_result.error_category or "unknown error"
                log_download_error(video_url, f"[{category}] {dl_result.error_message}")
                result = PlaylistItemResult(index=idx, title=title, ok=False, error_category=category)

            if on_event is not None:
                on_event(PlaylistDownloadEvent(kind="item_done", index=idx, title=title, result=result))
            return result

        with concurrent.futures.ThreadPoolExecutor(max_workers=len(batch)) as executor:
            futures = [
                executor.submit(worker, idx, video_url, title, video_id)
                for idx, video_url, title, video_id in batch
            ]
            for future in concurrent.futures.as_completed(futures):
                results.append(future.result())

    return results


# =============================================================================
# فارسی: لایه‌ی CLI — فقط اینجا از Rich (console، Progress، Confirm، Table،
#        Panel) استفاده می‌شود. هر تابع این بخش صرفاً روی توابع خالص بالا
#        سوار است.
# English: CLI layer — Rich (console, Progress, Confirm, Table, Panel) is
#          only used here. Every function in this section is just a thin
#          layer on top of the pure functions above.
# =============================================================================


def _print_playlist_summary(
    playlist_title: str,
    count: int,
    quality: int,
    audio_only: bool,
    total_size: int,
    out_dir: str,
    proxy: str | None,
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


def _print_download_summary(
    results: list[PlaylistItemResult],
    total_count: int,
    elapsed_seconds: float | None = None,
    total_estimated_size: int | None = None,
) -> None:
    """
    فارسی: جدول نتیجه‌ی نهایی دانلود پلی‌لیست را به همراه زمان سپری‌شده،
           سرعت میانگین، و شکست‌ها به‌تفکیک دسته چاپ می‌کند.
    English: Print the final results table for a playlist download,
             including elapsed time, average speed, and failures broken
             down by category.
    """
    summary = Table(title="Download Summary")
    summary.add_column("#", justify="right")
    summary.add_column("Title")
    summary.add_column("Status", justify="center")
    for r in sorted(results, key=lambda r: r.index):
        status = "[green]✔ success[/green]" if r.ok else f"[red]✘ {r.error_category}[/red]"
        short_title = (r.title[:50] + "...") if len(r.title) > 50 else r.title
        summary.add_row(str(r.index), short_title, status)
    console.print(summary)

    success_count = sum(1 for r in results if r.ok)
    console.print(f"\n[bold green]{success_count} of {total_count} videos downloaded successfully.[/bold green]")

    if elapsed_seconds:
        minutes, seconds = divmod(int(elapsed_seconds), 60)
        console.print(f"[cyan]Elapsed time: {minutes}m {seconds}s[/cyan]")
        if total_estimated_size:
            avg_speed = total_estimated_size / elapsed_seconds
            console.print(f"[cyan]Average speed: {human_size(avg_speed)}/s[/cyan]")

    if success_count < total_count:
        failure_counts: dict[str, int] = {}
        for r in results:
            if not r.ok:
                failure_counts[r.error_category] = failure_counts.get(r.error_category, 0) + 1
        console.print("\n[bold yellow]Failures by category:[/bold yellow]")
        for category, cnt in sorted(failure_counts.items(), key=lambda kv: -kv[1]):
            console.print(f"  {category}: {cnt}")
        from . import constants as c

        console.print(f"\n[yellow]See this log file for error details: {c.LOG_DIR / 'errors.log'}[/yellow]")


def download_playlist(
    url: str,
    cookies_path: str | None,
    quality: int,
    sub_en: bool,
    sub_fa: bool,
    out_dir: str,
    audio_only: bool,
    batch_size: int,
    proxy: str | None,
    extractor_args: dict,
    allow_client_fallback: bool,
    skip_estimate: bool,
) -> None:
    """
    فارسی: کل پلی‌لیست را پس از تأیید کاربر، دسته‌به‌دسته (batch) دانلود
           می‌کند. این تابع اکنون فقط یک wrapper نازک روی Rich است؛ منطق
           واقعیِ تخمین حجم و دانلود در estimate_playlist_size و
           execute_playlist_download (بالای همین فایل) قرار دارد. امضای
           این تابع عمداً بدون تغییر باقی مانده تا نقطه‌ی فراخوانی در
           cli.py نیازی به تغییر نداشته باشد.
    English: Download an entire playlist in batches, after user
             confirmation. This is now just a thin Rich wrapper; the real
             size-estimation and download logic lives in
             estimate_playlist_size and execute_playlist_download (above
             in this file). This function's signature was deliberately
             kept unchanged so the call site in cli.py doesn't need to
             change.
    """
    console.print("[cyan]Fetching video list...[/cyan]")
    log_info(f"Starting playlist download: {url}")
    try:
        entries, playlist_title = fetch_playlist_entries(url, cookies_path, proxy, extractor_args)
    except Exception as e:
        console.print(f"[red]Error fetching the playlist: {e}[/red]")
        console.print("[yellow]The cookie may have expired, or the current exit node is blocked.[/yellow]")
        log_download_error(url, str(e))
        return

    if not entries:
        console.print("[red]No videos found in this playlist.[/red]")
        return

    count = len(entries)

    completed_ids = load_completed_ids(url)
    if completed_ids:
        console.print(f"[cyan]Resuming: {len(completed_ids)} video(s) already completed in a previous run.[/cyan]")

    if skip_estimate:
        console.print(f"[cyan]Size estimation skipped ({count} videos found).[/cyan]")
        total_size = 0
    else:
        console.print(f"[yellow]Estimating total size for {count} videos...[/yellow]")
        with Progress(SpinnerColumn(), TextColumn("Checking {task.completed}/{task.total}"), console=console) as p:
            check_task = p.add_task("check", total=count)

            def on_estimate_event(evt: PlaylistDownloadEvent) -> None:
                p.update(check_task, completed=evt.checked)

            total_size = estimate_playlist_size(
                entries, cookies_path, quality, audio_only, proxy, extractor_args, on_event=on_estimate_event
            )

    _print_playlist_summary(playlist_title, count, quality, audio_only, total_size, out_dir, proxy)

    if not Confirm.ask("Start the download?", default=True):
        console.print("[red]Cancelled.[/red]")
        return

    out_path = Path(out_dir) / playlist_title
    out_path.mkdir(parents=True, exist_ok=True)

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
        overall_task = progress.add_task("overall", title="[bold]Overall progress[/bold]", total=count)
        task_ids: dict[int, int] = {}

        def on_playlist_event(evt: PlaylistDownloadEvent) -> None:
            if evt.kind == "batch_start":
                for idx, title in evt.batch:
                    short_title = (title[:35] + "...") if len(title) > 35 else title
                    task_ids[idx] = progress.add_task("dl", title=f"[{idx}] {short_title}", total=None)
            elif evt.kind == "item_progress":
                if evt.total_bytes:
                    progress.update(task_ids[evt.index], total=evt.total_bytes, completed=evt.downloaded_bytes)
            elif evt.kind == "item_status":
                progress.update(task_ids[evt.index], title=f"[{evt.index}] processing...")
            elif evt.kind == "item_done":
                r = evt.result
                task_id = task_ids[r.index]
                short_title = (r.title[:35] + "...") if len(r.title) > 35 else r.title
                if r.error_category == "Invalid URL":
                    progress.update(task_id, title=f"[red]✘ [{r.index}] invalid URL[/red]")
                elif r.ok and r.note == "resumed":
                    progress.update(task_id, title=f"[green]✔ [{r.index}] {r.title[:35]} (resumed)[/green]")
                elif r.ok:
                    progress.update(task_id, title=f"[green]✔ [{r.index}] {short_title}[/green]")
                else:
                    progress.update(task_id, title=f"[red]✘ [{r.index}] {short_title}[/red]")
                progress.update(overall_task, advance=1)

        results = execute_playlist_download(
            url,
            entries,
            out_path,
            cookies_path,
            quality,
            sub_en,
            sub_fa,
            audio_only,
            batch_size,
            proxy,
            extractor_args,
            allow_client_fallback,
            completed_ids,
            on_event=on_playlist_event,
        )

    elapsed = time.time() - start_time
    success_count = sum(1 for r in results if r.ok)
    if success_count == count:
        clear_state(url)
    _print_download_summary(results, count, elapsed, total_size if not skip_estimate else None)
