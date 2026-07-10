"""
فارسی: وضعیت مشترک و سراسری برنامه — نمونه‌ی Console و پرچم دیباگ. این‌ها
       در یک ماژول جدا نگه داشته می‌شوند تا از وابستگی چرخشی (circular
       import) بین ماژول‌های دیگر جلوگیری شود.
English: Shared, global application state — the Console instance and the
         debug flag. Kept in their own module to avoid circular imports
         between the other modules.
"""

from __future__ import annotations

from rich.console import Console

console = Console()

DEBUG: bool = False


def set_debug(value: bool) -> None:
    global DEBUG
    DEBUG = value
