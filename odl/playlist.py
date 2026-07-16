"""
فارسی: دریافت لیست ویدیوهای پلی‌لیست، تخمین حجم، دانلود دسته‌ای، و خلاصه‌ی نهایی.
English: Fetching playlist video entries, size estimation, batch downloads, and the final summary.
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
from .models import DownloadEvent, DownloadRequest
from .playlist_state import clear_state, load_completed_ids, mark_completed
from .state import console


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
    results: list[tuple[int, str, bool, str]],
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
    for idx, title, ok, category in sorted(results, key=lambda r: r[0]):
        status = "[green]✔ success[/green]" if ok else f"[red]✘ {category}[/red]"
        short_title = (title[:50] + "...") if len(title) > 50 else title
        summary.add_row(str(idx), short_title, status)
    console.print(summary)

    success_count = sum(1 for _, _, ok, _ in results if ok)
    console.print(f"\n[bold green]{success_count} of {total_count} videos downloaded successfully.[/bold green]")

    if elapsed_seconds:
        minutes, seconds = divmod(int(elapsed_seconds), 60)
        console.print(f"[cyan]Elapsed time: {minutes}m {seconds}s[/cyan]")
        if total_estimated_size:
            avg_speed = total_estimated_size / elapsed_seconds
            console.print(f"[cyan]Average speed: {human_size(avg_speed)}/s[/cyan]")

    if success_count < total_count:
        failure_counts: dict[str, int] = {}
        for _, _, ok, category in results:
            if not ok:
                failure_counts[category] = failure_counts.get(category, 0) + 1
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
    فارسی: کل پلی‌لیست را پس از تأیید کاربر، دسته‌به‌دسته (batch) دانلود می‌کند.
    English: Download an entire playlist in batches, after user confirmation.
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

    results: list[tuple[int, str, bool, str]] = []
    videos = [
        (i + 1, resolve_video_url(entry), entry.get("title") or "untitled", entry.get("id"))
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
        overall_task = progress.add_task("overall", title="[bold]Overall progress[/bold]", total=count)

        for batch_start in range(0, len(videos), batch_size):
            batch = videos[batch_start : batch_start + batch_size]
            task_ids: dict[int, int] = {}

            for idx, _video_url, title, _video_id in batch:
                short_title = (title[:35] + "...") if len(title) > 35 else title
                task_ids[idx] = progress.add_task("dl", title=f"[{idx}] {short_title}", total=None)

            def worker(
                idx: int, video_url: str | None, title: str, video_id: str | None, task_id: int
            ) -> tuple[int, str, bool, str]:
                if not video_url:
                    progress.update(task_id, title=f"[red]✘ [{idx}] invalid URL[/red]")
                    progress.update(overall_task, advance=1)
                    return idx, title, False, "Invalid URL"

                if video_id and video_id in completed_ids:
                    progress.update(task_id, title=f"[green]✔ [{idx}] {title[:35]} (resumed)[/green]")
                    progress.update(overall_task, advance=1)
                    return idx, title, True, ""

                out_template = str(out_path / f"{idx:03d} - %(title)s.%(ext)s")
                short_title = (title[:35] + "...") if len(title) > 35 else title

                def on_event(evt: DownloadEvent) -> None:
                    if evt.kind == "progress":
                        if evt.total_bytes:
                            progress.update(task_id, total=evt.total_bytes, completed=evt.downloaded_bytes)
                    elif evt.kind == "status":
                        progress.update(task_id, title=f"[{idx}] processing...")
                    elif evt.kind == "retry":
                        log_warning(f"Retrying {video_url} with player_client={evt.client}")

                # فارسی: به‌جای منطق کپی‌شده‌ی attempt/fallback، حالا از همان
                #        هسته‌ی مشترکی استفاده می‌شود که download_single هم استفاده می‌کند.
                # English: Instead of a copy-pasted attempt/fallback loop, this now
                #          uses the same shared core function that download_single uses.
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
                result = attempt_download_with_fallback(request, ignore_errors=True, on_event=on_event)

                progress.update(overall_task, advance=1)

                if result.ok:
                    progress.update(task_id, title=f"[green]✔ [{idx}] {short_title}[/green]")
                    mark_completed(url, video_id)
                    return idx, title, True, ""

                category = result.error_category or "unknown error"
                progress.update(task_id, title=f"[red]✘ [{idx}] {short_title}[/red]")
                log_download_error(video_url, f"[{category}] {result.error_message}")
                return idx, title, False, category

            with concurrent.futures.ThreadPoolExecutor(max_workers=len(batch)) as executor:
                futures = [
                    executor.submit(worker, idx, video_url, title, video_id, task_ids[idx])
                    for idx, video_url, title, video_id in batch
                ]
                for future in concurrent.futures.as_completed(futures):
                    results.append(future.result())

    elapsed = time.time() - start_time
    success_count = sum(1 for _, _, ok, _ in results if ok)
    if success_count == count:
        clear_state(url)
    _print_download_summary(results, count, elapsed, total_size if not skip_estimate else None)
