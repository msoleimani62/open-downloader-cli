"""
فارسی: ذخیره‌سازی وضعیت پیشرفت پلی‌لیست، تا اگه سیستم وسط دانلود خاموش شد،
       دفعه‌ی بعد فقط ویدیوهای ناتمام دوباره بررسی/دانلود بشن.
English: Persist playlist download progress so that if the system is
         interrupted mid-download, the next run only re-checks/downloads
         the remaining videos.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Optional

from . import constants as c


def _state_file_for(playlist_url: str) -> Path:
    """
    فارسی: یک نام فایل پایدار و بی‌خطر بر اساس هش لینک پلی‌لیست می‌سازد.
    English: Build a stable, filesystem-safe filename based on a hash of the playlist URL.
    """
    digest = hashlib.sha256(playlist_url.encode("utf-8")).hexdigest()[:16]
    return c.PLAYLIST_STATE_DIR / f"{digest}.json"


def load_completed_ids(playlist_url: str) -> set[str]:
    """
    فارسی: مجموعه‌ی شناسه‌ی ویدیوهایی که قبلاً با موفقیت دانلود شده‌اند را برمی‌گرداند.
    English: Return the set of video IDs that were already downloaded successfully.
    """
    state_file = _state_file_for(playlist_url)
    if not state_file.exists():
        return set()
    try:
        data = json.loads(state_file.read_text(encoding="utf-8"))
        return set(data.get("completed", []))
    except Exception:
        return set()


def mark_completed(playlist_url: str, video_id: Optional[str]) -> None:
    """
    فارسی: یک ویدیو را به‌عنوان دانلودشده در فایل وضعیت ثبت می‌کند.
    English: Mark a video as downloaded in the state file.
    """
    if not video_id:
        return
    c.PLAYLIST_STATE_DIR.mkdir(parents=True, exist_ok=True)
    state_file = _state_file_for(playlist_url)
    completed = load_completed_ids(playlist_url)
    completed.add(video_id)
    state_file.write_text(
        json.dumps({"playlist_url": playlist_url, "completed": sorted(completed)}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def clear_state(playlist_url: str) -> None:
    """
    فارسی: فایل وضعیت یک پلی‌لیست را حذف می‌کند (پس از اتمام کامل و موفق دانلود).
    English: Delete a playlist's state file (after a fully successful download).
    """
    state_file = _state_file_for(playlist_url)
    if state_file.exists():
        state_file.unlink()
