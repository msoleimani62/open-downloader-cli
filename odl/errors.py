"""
فارسی: دسته‌بندی خطاهای دانلود بر اساس متن پیام yt-dlp.
English: Classification of download errors based on the yt-dlp error message text.
"""

from __future__ import annotations


class ErrorCategory:
    """
    فارسی: نام دسته‌های ممکن برای خطاهای دانلود (برای خلاصه‌ی بهتر و تصمیم retry).
    English: Possible categories for download errors (for a better summary and retry decisions).
    """

    REGION_LOCKED = "Region Locked"
    AGE_RESTRICTED = "Age Restricted"
    PRIVATE_VIDEO = "Private"
    DELETED_VIDEO = "Deleted/Unavailable"
    MEMBERS_ONLY = "Members Only"
    LOGIN_REQUIRED = "Login Required"
    BOT_DETECTED = "Bot Detection"
    NETWORK_ERROR = "Network Error"
    PROXY_ERROR = "Proxy Error"
    COOKIE_INVALID = "Cookie Invalid"
    UNKNOWN = "Unknown"


CLIENT_FALLBACK_RETRYABLE_CATEGORIES = {
    ErrorCategory.BOT_DETECTED,
    ErrorCategory.LOGIN_REQUIRED,
    ErrorCategory.UNKNOWN,
}


def classify_error(message: str) -> str:
    """
    فارسی: پیام خطای yt-dlp را بر اساس محتوای متنش به یک دسته‌ی قابل‌فهم
           (مثل Region Locked یا Bot Detection) طبقه‌بندی می‌کند.
    English: Classify a yt-dlp error message into a human-friendly category
             (e.g. Region Locked, Bot Detection) based on its text content.
    """
    m = message.lower()
    if "not available in your country" in m or "not made this video available" in m:
        return ErrorCategory.REGION_LOCKED
    if "age" in m and ("restrict" in m or "confirm" in m and "birthday" in m):
        return ErrorCategory.AGE_RESTRICTED
    if "private video" in m:
        return ErrorCategory.PRIVATE_VIDEO
    if "video has been removed" in m or "no longer available" in m or "video unavailable" in m:
        return ErrorCategory.DELETED_VIDEO
    if "members-only" in m or "members only" in m or "join this channel" in m:
        return ErrorCategory.MEMBERS_ONLY
    if "confirm you" in m and "not a bot" in m:
        return ErrorCategory.BOT_DETECTED
    if "sign in" in m or "login" in m:
        return ErrorCategory.LOGIN_REQUIRED
    if "proxy" in m:
        return ErrorCategory.PROXY_ERROR
    if "cookie" in m:
        return ErrorCategory.COOKIE_INVALID
    if "timed out" in m or "temporary failure in name resolution" in m or "connection" in m:
        return ErrorCategory.NETWORK_ERROR
    return ErrorCategory.UNKNOWN
