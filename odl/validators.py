"""
فارسی: اعتبارسنجی مرکزی مقادیری که از چند مسیر مختلف وارد می‌شوند
       (فلگ خط فرمان، «--set»، یک پروفایل ذخیره‌شده). قبل از این ماژول،
       منطق «quality باید در ALLOWED_QUALITIES باشد» و «batch_size باید
       حداقل ۱ باشد» در سه جای مختلف (config.py دوبار، cli.py یک‌بار)
       تکرار شده بود — دقیقاً نوع بدهی فنی‌ای که باعث می‌شه یک‌جا فیکس
       بشه و بقیه از قلم بیفتن.
English: Centralized validation for values that arrive through several
         different paths (a CLI flag, "--set", a saved profile). Before
         this module, the "quality must be in ALLOWED_QUALITIES" and
         "batch_size must be at least 1" logic was duplicated in three
         places (twice in config.py, once in cli.py) — exactly the kind
         of technical debt where one spot gets fixed and the others get
         missed.
"""

from __future__ import annotations

from . import constants as c


def validate_quality(value: int) -> None:
    """
    فارسی: بررسی می‌کند که کیفیت داده‌شده در لیست مجاز باشد.
    English: Check that the given quality is in the allowed list.

    Raises:
        ValueError: اگر مقدار مجاز نباشد / if the value isn't allowed.
    """
    if value not in c.ALLOWED_QUALITIES:
        allowed = ", ".join(map(str, c.ALLOWED_QUALITIES))
        raise ValueError(f"'quality' must be one of: {allowed} (got {value})")


def validate_batch_size(value: int) -> None:
    """
    فارسی: بررسی می‌کند که batch_size حداقل ۱ باشد (چون batch_size<=۰
           باعث کرش downloader می‌شود).
    English: Check that batch_size is at least 1 (batch_size<=0 crashes
             the downloader).

    Raises:
        ValueError: اگر مقدار کمتر از ۱ باشد / if the value is less than 1.
    """
    if value < 1:
        raise ValueError(f"'batch_size' must be 1 or greater, got {value}")
