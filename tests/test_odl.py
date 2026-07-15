"""
فارسی: تست‌های واحد برای بخش‌های حیاتی بسته‌ی odl — رمزنگاری کوکی، دسته‌بندی
       خطا، ساخت extractor_args، و توابع کمکی.
English: Unit tests for the critical parts of the odl package — cookie
         encryption, error classification, extractor_args construction,
         and helper functions.
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from odl import config as config_module
from odl import constants as c
from odl import cookies, downloader, playlist_state, proxy_pool
from odl.diagnostics import _parse_version_tuple
from odl.errors import CLIENT_FALLBACK_RETRYABLE_CATEGORIES, ErrorCategory, classify_error


@pytest.fixture(autouse=True)
def isolated_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(c, "CONFIG_DIR", tmp_path / ".config" / "opendl")
    monkeypatch.setattr(c, "CONFIG_FILE", tmp_path / ".config" / "opendl" / "config.json")
    monkeypatch.setattr(c, "COOKIES_DEFAULT", tmp_path / "cookies.txt")
    monkeypatch.setattr(c, "ENCRYPTED_COOKIES_FILE", tmp_path / ".config" / "opendl" / "cookies.enc")
    monkeypatch.setattr(c, "LOG_FILE", tmp_path / ".config" / "opendl" / "opendl.log")
    monkeypatch.setattr(c, "LOG_DIR", tmp_path / ".config" / "opendl" / "logs")
    monkeypatch.setattr(c, "PLAYLIST_STATE_DIR", tmp_path / ".config" / "opendl" / "playlist_state")
    monkeypatch.setattr(c, "PROXY_STATE_FILE", tmp_path / ".config" / "opendl" / "proxy_state.json")
    yield


class TestCookieEncryption:
    def test_derive_key_is_deterministic_for_same_password_and_salt(self):
        salt = os.urandom(16)
        key1 = cookies.derive_key("my-password", salt)
        key2 = cookies.derive_key("my-password", salt)
        assert key1 == key2

    def test_derive_key_differs_for_different_passwords(self):
        salt = os.urandom(16)
        key1 = cookies.derive_key("password-one", salt)
        key2 = cookies.derive_key("password-two", salt)
        assert key1 != key2

    def test_require_crypto_raises_instead_of_exiting_when_unavailable(self, monkeypatch):
        # فارسی: قبلاً این حالت مستقیم sys.exit صدا می‌زد که کل پردازه
        #        (و در آینده کل اپ GUI) را می‌بست. حالا فقط یک exception
        #        معمولی است که لایه‌ی فراخوان می‌تواند بگیرد.
        # English: This used to call sys.exit directly, killing the whole
        #          process (and, later, the whole GUI app). Now it's just
        #          a plain exception the caller can catch.
        monkeypatch.setattr(cookies, "CRYPTO_AVAILABLE", False)
        with pytest.raises(cookies.CryptoUnavailableError):
            cookies._require_crypto()

    def test_resolve_cookies_path_raises_on_corrupt_encrypted_file(self):
        c.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        c.ENCRYPTED_COOKIES_FILE.write_text("this is not valid json", encoding="utf-8")
        with pytest.raises(cookies.EncryptedCookieReadError):
            cookies.resolve_cookies_path({"cookies": str(c.COOKIES_DEFAULT)})

    def test_full_encrypt_decrypt_roundtrip_with_correct_password(self, monkeypatch):
        c.COOKIES_DEFAULT.write_text("# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t0\tTEST\tabc123\n")
        passwords = iter(["correct-horse-battery-staple", "correct-horse-battery-staple"])
        monkeypatch.setattr(cookies.getpass, "getpass", lambda prompt="": next(passwords))

        cookie_path, cleanup = cookies.secure_cookies_setup(auto=False)

        assert c.ENCRYPTED_COOKIES_FILE.exists()
        assert not c.COOKIES_DEFAULT.exists()

        oct_perm = oct(c.ENCRYPTED_COOKIES_FILE.stat().st_mode)[-3:]
        assert oct_perm == "600"

        monkeypatch.setattr(cookies.getpass, "getpass", lambda prompt="": "correct-horse-battery-staple")
        cfg = {"cookies": str(c.COOKIES_DEFAULT)}
        decrypted_path, cleanup2 = cookies.resolve_cookies_path(cfg)

        assert decrypted_path is not None
        content = Path(decrypted_path).read_text()
        assert "abc123" in content
        cleanup2()
        assert not Path(decrypted_path).exists()

    def test_wrong_password_is_rejected(self, monkeypatch):
        c.COOKIES_DEFAULT.write_text("# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t0\tTEST\tabc\n")
        passwords = iter(["right-password", "right-password"])
        monkeypatch.setattr(cookies.getpass, "getpass", lambda prompt="": next(passwords))
        cookies.secure_cookies_setup(auto=False)

        wrong_attempts = iter(["wrong-1", "wrong-2", "wrong-3"])
        monkeypatch.setattr(cookies.getpass, "getpass", lambda prompt="": next(wrong_attempts))
        monkeypatch.setattr(cookies.Confirm, "ask", staticmethod(lambda *a, **k: False))

        cfg = {"cookies": str(c.COOKIES_DEFAULT)}
        with pytest.raises(cookies.MaxPasswordAttemptsError):
            cookies.resolve_cookies_path(cfg)

    def test_auto_mode_reuses_password_without_asking_twice(self, monkeypatch):
        c.COOKIES_DEFAULT.write_text("# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t0\tTEST\tabc\n")
        prompts = []

        def fake_getpass(prompt=""):
            prompts.append(prompt)
            return "pw1"

        monkeypatch.setattr(cookies.getpass, "getpass", fake_getpass)
        cookie_path, cleanup = cookies.secure_cookies_setup(auto=True)

        assert len(prompts) == 2
        assert cookie_path is not None
        cleanup()


class TestClassifyError:
    @pytest.mark.parametrize(
        "message,expected_category",
        [
            ("The uploader has not made this video available in your country", ErrorCategory.REGION_LOCKED),
            ("This is a private video", ErrorCategory.PRIVATE_VIDEO),
            ("Video unavailable", ErrorCategory.DELETED_VIDEO),
            ("Join this channel to get access to members-only content", ErrorCategory.MEMBERS_ONLY),
            ("Sign in to confirm you're not a bot", ErrorCategory.BOT_DETECTED),
            ("Please sign in to continue", ErrorCategory.LOGIN_REQUIRED),
            ("SOCKS5 proxy connection failed", ErrorCategory.PROXY_ERROR),
            ("cookie file is invalid or expired", ErrorCategory.COOKIE_INVALID),
            ("Temporary failure in name resolution", ErrorCategory.NETWORK_ERROR),
            ("some completely unrelated error text", ErrorCategory.UNKNOWN),
        ],
    )
    def test_classify_error_categories(self, message, expected_category):
        assert classify_error(message) == expected_category

    def test_bot_detection_is_in_retryable_categories(self):
        assert ErrorCategory.BOT_DETECTED in CLIENT_FALLBACK_RETRYABLE_CATEGORIES

    def test_region_locked_is_not_retryable(self):
        assert ErrorCategory.REGION_LOCKED not in CLIENT_FALLBACK_RETRYABLE_CATEGORIES


class TestBuildExtractorArgs:
    def test_default_skips_authcheck(self):
        args = downloader.build_extractor_args({}, bypass=False)
        assert "authcheck" in args["youtubetab"]["skip"]

    def test_bypass_adds_webpage_skip_and_player_skip(self):
        args = downloader.build_extractor_args({}, bypass=True)
        assert "webpage" in args["youtubetab"]["skip"]
        assert args["youtube"]["player_skip"] == ["webpage", "configs"]

    def test_player_client_single(self):
        args = downloader.build_extractor_args({"player_client": "android"}, bypass=False)
        assert args["youtube"]["player_client"] == ["android"]

    def test_player_client_multiple_comma_separated(self):
        args = downloader.build_extractor_args({"player_client": "android, web , mweb"}, bypass=False)
        assert args["youtube"]["player_client"] == ["android", "web", "mweb"]

    def test_bypass_and_player_client_combined(self):
        args = downloader.build_extractor_args({"player_client": "android"}, bypass=True)
        assert args["youtube"]["player_skip"] == ["webpage", "configs"]
        assert args["youtube"]["player_client"] == ["android"]


class TestHelpers:
    @pytest.mark.parametrize(
        "quality,expected",
        [
            (480, "bestvideo[height<=480]+bestaudio/best[height<=480]"),
            (1080, "bestvideo[height<=1080]+bestaudio/best[height<=1080]"),
        ],
    )
    def test_build_format(self, quality, expected):
        assert downloader.build_format(quality) == expected

    @pytest.mark.parametrize(
        "url,expected",
        [
            ("https://youtu.be/abc123", True),
            ("https://www.youtube.com/watch?v=abc123", True),
            ("https://example.com/video", False),
            ("not a url at all", False),
        ],
    )
    def test_is_youtube_url(self, url, expected):
        assert downloader.is_youtube_url(url) == expected

    def test_human_size_formats_correctly(self):
        assert downloader.human_size(None) == "unknown"
        assert downloader.human_size(0) == "unknown"
        assert "KB" in downloader.human_size(2048)
        assert "MB" in downloader.human_size(5 * 1024 * 1024)

    def test_resolve_video_url_from_id(self):
        entry = {"id": "abc123"}
        assert downloader.resolve_video_url(entry) == "https://www.youtube.com/watch?v=abc123"

    def test_resolve_video_url_from_full_url(self):
        entry = {"url": "https://youtu.be/xyz"}
        assert downloader.resolve_video_url(entry) == "https://youtu.be/xyz"

    def test_resolve_video_url_prefers_webpage_url_for_non_youtube_sites(self):
        # فارسی: خیلی از extractorهای غیریوتیوب (Vimeo، Twitter/X، ...)
        #        webpage_url رو با لینک کامل پر می‌کنن؛ این باید همیشه
        #        اولویت اول باشه.
        # English: Many non-YouTube extractors (Vimeo, Twitter/X, ...)
        #          fill webpage_url with the full link; it should always
        #          be tried first.
        entry = {"id": "xyz", "webpage_url": "https://vimeo.com/xyz", "url": "xyz"}
        assert downloader.resolve_video_url(entry) == "https://vimeo.com/xyz"

    def test_resolve_video_url_uses_full_url_when_no_webpage_url(self):
        entry = {"url": "https://twitter.com/user/status/999"}
        assert downloader.resolve_video_url(entry) == "https://twitter.com/user/status/999"

    def test_resolve_video_url_returns_none_when_empty(self):
        assert downloader.resolve_video_url({}) is None

    def test_write_temp_cookie_file_permissions_and_cleanup(self):
        path, cleanup = cookies._write_temp_cookie_file(b"test-data")
        assert Path(path).exists()
        assert Path(path).read_bytes() == b"test-data"
        oct_perm = oct(Path(path).stat().st_mode)[-3:]
        assert oct_perm == "600"
        cleanup()
        assert not Path(path).exists()


class TestEnvironmentDetection:
    def _isolate(self, monkeypatch, proc_version="", proc_mounts="", os_release="", android_env_visible=False):
        """
        فارسی: هر سه منبع سیگنالی که detect_environment می‌خواند را با
               مقادیر ساختگی جایگزین می‌کند — چون این تست‌ها ممکن است
               واقعاً روی گوشی کاربر (که /proc/mounts واقعی‌اش نشونه‌های
               کرنل اندروید دارد) اجرا شوند، بدون این ایزوله‌سازی کامل،
               محیط واقعی روی نتیجه‌ی تست اثر می‌گذاشت.
        English: Replace all three signal sources detect_environment reads
                 with fake values — since these tests may actually run on
                 the user's phone (whose real /proc/mounts has Android
                 kernel signals), without this full isolation the real
                 environment would leak into the test result.
        """
        monkeypatch.setattr(c, "ANDROID_MARKER_PATHS", [Path("/nonexistent-marker-path")])
        for var in c.ANDROID_MARKER_ENV_VARS:
            monkeypatch.delenv(var, raising=False)
        if android_env_visible:
            monkeypatch.setenv("TERMUX_VERSION", "0.118")
        monkeypatch.delenv("ODL_FORCE_ENVIRONMENT", raising=False)
        monkeypatch.setattr(cookies.sys, "platform", "linux")

        fake_files = {"/proc/version": proc_version, "/proc/mounts": proc_mounts, "/etc/os-release": os_release}
        monkeypatch.setattr(cookies, "_read_text_safely", lambda path: fake_files.get(str(path), ""))

    def test_desktop_linux_true_without_android_markers(self, monkeypatch):
        self._isolate(monkeypatch, proc_mounts="/dev/sda1 / ext4 rw,relatime 0 0\n")
        assert cookies.is_desktop_linux() is True
        assert cookies.detect_environment() is cookies.Environment.DESKTOP_LINUX

    def test_desktop_linux_false_with_termux_env_var(self, monkeypatch):
        self._isolate(monkeypatch, android_env_visible=True)
        assert cookies.is_desktop_linux() is False
        assert cookies.detect_environment() is cookies.Environment.ANDROID_TERMUX

    def test_kali_nethunter_detected_via_android_kernel_mounts_and_os_release(self, monkeypatch):
        # فارسی: دقیقاً همون سیگنال‌هایی که روی گوشی واقعی کاربر مشاهده
        #        شد: binder/schedtune در mounts + ID=kali در os-release.
        # English: Exactly the signals observed on the user's real phone:
        #          binder/schedtune in mounts + ID=kali in os-release.
        self._isolate(
            monkeypatch,
            proc_mounts=(
                "binder /dev/binderfs binder rw,relatime 0 0\n"
                "none /dev/stune cgroup rw,nosuid,nodev,noexec,relatime,schedtune 0 0\n"
            ),
            os_release='PRETTY_NAME="Kali GNU/Linux Rolling"\nID=kali\nID_LIKE=debian\n',
        )
        assert cookies.detect_environment() is cookies.Environment.KALI_NETHUNTER
        assert cookies.is_desktop_linux() is False

    def test_android_kernel_chroot_with_non_kali_distro_falls_back_to_android_termux(self, monkeypatch):
        self._isolate(
            monkeypatch,
            proc_mounts="binder /dev/binderfs binder rw,relatime 0 0\n",
            os_release='PRETTY_NAME="Ubuntu"\nID=ubuntu\n',
        )
        assert cookies.detect_environment() is cookies.Environment.ANDROID_TERMUX

    def test_wsl_detected_via_proc_version(self, monkeypatch):
        self._isolate(monkeypatch, proc_version="Linux version 5.15.0 (Microsoft@Microsoft.com)\n")
        assert cookies.detect_environment() is cookies.Environment.WSL

    def test_non_linux_platform_is_other(self, monkeypatch):
        monkeypatch.delenv("ODL_FORCE_ENVIRONMENT", raising=False)
        monkeypatch.setattr(cookies.sys, "platform", "darwin")
        assert cookies.detect_environment() is cookies.Environment.OTHER

    def test_force_environment_override_wins(self, monkeypatch):
        monkeypatch.setenv("ODL_FORCE_ENVIRONMENT", "kali_nethunter")
        monkeypatch.setattr(cookies.sys, "platform", "linux")
        assert cookies.detect_environment() is cookies.Environment.KALI_NETHUNTER

    def test_invalid_force_environment_falls_back_to_auto_detect(self, monkeypatch):
        self._isolate(monkeypatch, proc_mounts="/dev/sda1 / ext4 rw,relatime 0 0\n")
        monkeypatch.setenv("ODL_FORCE_ENVIRONMENT", "not-a-real-value")
        assert cookies.detect_environment() is cookies.Environment.DESKTOP_LINUX


class TestClientFallbackScope:
    """
    فارسی: fallback بین کلاینت‌های پخش («android»، «web»، ...) یک مفهوم
           مخصوص یوتیوبه؛ این کلاس تأیید می‌کنه که برای سایت‌های دیگه
           اصلاً امتحان نمی‌شه (فقط همون یک تلاش اول)، ولی برای یوتیوب
           طبق معمول کامل امتحان می‌شه.
    English: Playback-client fallback ("android", "web", ...) is a
             YouTube-only concept; this class confirms it's never
             attempted for other sites (just the single first try), but
             still fully attempted for YouTube as before.
    """

    class _FailingYDL:
        def __init__(self, opts):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def download(self, urls):
            raise Exception("Sign in to confirm you're not a bot")

    def test_fallback_skipped_for_non_youtube_urls(self, monkeypatch):
        from odl.models import DownloadRequest

        monkeypatch.setattr(downloader.yt_dlp, "YoutubeDL", self._FailingYDL)
        request = DownloadRequest(
            url="https://vimeo.com/12345",
            out_template="%(title)s.%(ext)s",
            allow_client_fallback=True,
        )
        result = downloader.attempt_download_with_fallback(request, ignore_errors=False)
        assert result.ok is False
        assert result.tried_clients == ["default"]

    def test_fallback_attempted_for_youtube_urls(self, monkeypatch):
        from odl.models import DownloadRequest

        monkeypatch.setattr(downloader.yt_dlp, "YoutubeDL", self._FailingYDL)
        request = DownloadRequest(
            url="https://youtube.com/watch?v=abc123",
            out_template="%(title)s.%(ext)s",
            allow_client_fallback=True,
        )
        result = downloader.attempt_download_with_fallback(request, ignore_errors=False)
        assert result.ok is False
        assert len(result.tried_clients) > 1


class TestPlaylistState:
    def test_no_state_returns_empty_set(self):
        assert playlist_state.load_completed_ids("https://youtube.com/playlist?list=A") == set()

    def test_mark_and_load_completed(self):
        url = "https://youtube.com/playlist?list=B"
        playlist_state.mark_completed(url, "vid1")
        playlist_state.mark_completed(url, "vid2")
        assert playlist_state.load_completed_ids(url) == {"vid1", "vid2"}

    def test_mark_completed_ignores_none_id(self):
        url = "https://youtube.com/playlist?list=C"
        playlist_state.mark_completed(url, None)
        assert playlist_state.load_completed_ids(url) == set()

    def test_clear_state_removes_file(self):
        url = "https://youtube.com/playlist?list=D"
        playlist_state.mark_completed(url, "vid1")
        assert playlist_state.load_completed_ids(url) == {"vid1"}
        playlist_state.clear_state(url)
        assert playlist_state.load_completed_ids(url) == set()

    def test_different_playlists_have_independent_state(self):
        url_a = "https://youtube.com/playlist?list=E1"
        url_b = "https://youtube.com/playlist?list=E2"
        playlist_state.mark_completed(url_a, "vidA")
        assert playlist_state.load_completed_ids(url_b) == set()


class TestConfigSetParsing:
    def test_parse_int_setting(self):
        key, value = config_module.parse_set_argument("quality=720")
        assert key == "quality"
        assert value == 720

    def test_parse_string_setting(self):
        key, value = config_module.parse_set_argument("download_dir=/tmp/videos")
        assert key == "download_dir"
        assert value == "/tmp/videos"

    def test_parse_bool_setting_true(self):
        key, value = config_module.parse_set_argument("bypass=true")
        assert value is True

    def test_parse_bool_setting_false(self):
        key, value = config_module.parse_set_argument("bypass=false")
        assert value is False

    def test_parse_none_setting(self):
        key, value = config_module.parse_set_argument("proxy=none")
        assert value is None

    def test_unknown_key_raises(self):
        with pytest.raises(ValueError):
            config_module.parse_set_argument("nonsense=1")

    def test_missing_equals_raises(self):
        with pytest.raises(ValueError):
            config_module.parse_set_argument("quality720")

    def test_invalid_int_raises(self):
        with pytest.raises(ValueError):
            config_module.parse_set_argument("quality=notanumber")

    def test_set_and_load_roundtrip(self):
        cfg = config_module.load_config()
        cfg["quality"] = 1080
        config_module.write_config(cfg)
        reloaded = config_module.load_config()
        assert reloaded["quality"] == 1080

    def test_batch_size_zero_raises(self):
        # فارسی: بدون این چک، playlist.py با batch_size=0 روی
        #        range(0, n, 0) کرش می‌کند (ValueError).
        # English: Without this check, playlist.py crashes on
        #          range(0, n, 0) (ValueError) when batch_size=0.
        with pytest.raises(ValueError):
            config_module.parse_set_argument("batch_size=0")

    def test_batch_size_negative_raises(self):
        with pytest.raises(ValueError):
            config_module.parse_set_argument("batch_size=-3")

    def test_batch_size_positive_is_accepted(self):
        key, value = config_module.parse_set_argument("batch_size=3")
        assert key == "batch_size"
        assert value == 3

    def test_quality_not_in_allowed_list_raises(self):
        with pytest.raises(ValueError):
            config_module.parse_set_argument("quality=999")


class TestSelfUpdateVersionCompare:
    def test_simple_versions(self):
        assert _parse_version_tuple("2.1.0") == (2, 1, 0)

    def test_v_prefix_is_stripped(self):
        assert _parse_version_tuple("v2.1.0") == (2, 1, 0)

    def test_double_digit_minor_sorts_correctly(self):
        assert _parse_version_tuple("2.10.0") > _parse_version_tuple("2.9.0")

    def test_equal_versions(self):
        assert _parse_version_tuple("2.1.0") == _parse_version_tuple("2.1.0")


class TestIgnoreErrorsBehavior:
    def test_single_download_defaults_to_ignore_errors_false(self):
        opts = downloader.ydl_opts_base(
            None, 480, False, False, "%(title)s.%(ext)s", False, None, {}, ignore_errors=False
        )
        assert opts["ignoreerrors"] is False

    def test_playlist_download_uses_ignore_errors_true(self):
        opts = downloader.ydl_opts_base(
            None, 480, False, False, "%(title)s.%(ext)s", False, None, {}, ignore_errors=True
        )
        assert opts["ignoreerrors"] is True

    def test_ignore_errors_defaults_to_true_when_unspecified(self):
        opts = downloader.ydl_opts_base(None, 480, False, False, "%(title)s.%(ext)s", False, None, {})
        assert opts["ignoreerrors"] is True

    def test_retries_are_numeric_not_the_string_infinite(self):
        # فارسی: "infinite" رشته‌ای فقط از طریق CLI خود yt-dlp به
        #        float('inf') تبدیل می‌شه؛ از API پایتون رشته‌ی خام
        #        می‌مونه و توی دانلود fragment/HLS (مثلاً Vimeo)
        #        TypeError می‌داد چون شمارنده‌ی retry با یه رشته
        #        مقایسه می‌شد.
        # English: The string "infinite" is only converted to
        #          float('inf') via yt-dlp's own CLI; through the Python
        #          API it stays a raw string and caused a TypeError
        #          during fragment/HLS downloads (e.g. Vimeo) since the
        #          retry counter was compared against a string.
        opts = downloader.ydl_opts_base(None, 480, False, False, "%(title)s.%(ext)s", False, None, {})
        assert opts["retries"] == float("inf")
        assert opts["fragment_retries"] == float("inf")
        assert isinstance(opts["retries"], float)
        assert isinstance(opts["fragment_retries"], float)


class TestProxyPool:
    def test_normalize_proxy_adds_http_scheme_when_missing(self):
        assert proxy_pool._normalize_proxy("1.2.3.4:8080") == "http://1.2.3.4:8080"

    def test_normalize_proxy_keeps_existing_scheme(self):
        assert proxy_pool._normalize_proxy("socks5://1.2.3.4:1080") == "socks5://1.2.3.4:1080"

    def test_load_candidates_from_file_skips_comments_and_blanks(self, tmp_path):
        source_file = tmp_path / "proxies.txt"
        source_file.write_text(
            "# a comment\n\n1.2.3.4:8080\nsocks5://5.6.7.8:1080\n\n# another\n1.2.3.4:8080\n",
            encoding="utf-8",
        )
        candidates = proxy_pool.load_proxy_candidates(str(source_file))
        assert candidates == ["http://1.2.3.4:8080", "socks5://5.6.7.8:1080"]

    def test_load_candidates_missing_file_raises_pool_error(self, tmp_path):
        with pytest.raises(proxy_pool.ProxyPoolError):
            proxy_pool.load_proxy_candidates(str(tmp_path / "does-not-exist.txt"))

    def test_load_candidates_empty_file_raises_pool_error(self, tmp_path):
        empty_file = tmp_path / "empty.txt"
        empty_file.write_text("# nothing but comments\n", encoding="utf-8")
        with pytest.raises(proxy_pool.ProxyPoolError):
            proxy_pool.load_proxy_candidates(str(empty_file))

    def test_cache_roundtrip(self):
        assert proxy_pool.load_cached_proxy("source-a") is None
        proxy_pool.save_cached_proxy("source-a", "http://1.2.3.4:8080")
        assert proxy_pool.load_cached_proxy("source-a") == "http://1.2.3.4:8080"

    def test_cache_is_invalid_for_a_different_source(self):
        proxy_pool.save_cached_proxy("source-a", "http://1.2.3.4:8080")
        assert proxy_pool.load_cached_proxy("source-b") is None

    def test_clear_cached_proxy_removes_the_cache(self):
        proxy_pool.save_cached_proxy("source-a", "http://1.2.3.4:8080")
        proxy_pool.clear_cached_proxy()
        assert proxy_pool.load_cached_proxy("source-a") is None

    def test_resolve_reuses_still_working_cached_proxy_without_scanning_source(self, tmp_path):
        source_file = tmp_path / "proxies.txt"
        source_file.write_text("http://1.1.1.1:80\nhttp://2.2.2.2:80\n", encoding="utf-8")
        proxy_pool.save_cached_proxy(str(source_file), "http://cached.example:80")

        calls = []

        def always_ok_tester(proxy, cookies_path=None):
            calls.append(proxy)
            return downloader_test_result(proxy, ok=True)

        result = proxy_pool.resolve_working_proxy(str(source_file), tester=always_ok_tester)
        assert result == "http://cached.example:80"
        # فارسی: چون کش هنوز سالم بود، هیچ کاندیدی از فایل منبع نباید تست شده باشد.
        # English: Since the cache was still healthy, no candidate from the
        #          source file should have been tested.
        assert calls == ["http://cached.example:80"]

    def test_resolve_falls_back_to_source_when_cache_is_dead(self, tmp_path):
        source_file = tmp_path / "proxies.txt"
        source_file.write_text("http://1.1.1.1:80\nhttp://2.2.2.2:80\n", encoding="utf-8")
        proxy_pool.save_cached_proxy(str(source_file), "http://dead.example:80")

        def tester(proxy, cookies_path=None):
            ok = proxy == "http://2.2.2.2:80"
            return downloader_test_result(proxy, ok=ok)

        result = proxy_pool.resolve_working_proxy(str(source_file), tester=tester)
        assert result == "http://2.2.2.2:80"
        assert proxy_pool.load_cached_proxy(str(source_file)) == "http://2.2.2.2:80"

    def test_resolve_returns_none_when_nothing_works(self, tmp_path):
        source_file = tmp_path / "proxies.txt"
        source_file.write_text("http://1.1.1.1:80\nhttp://2.2.2.2:80\n", encoding="utf-8")

        def always_fail_tester(proxy, cookies_path=None):
            return downloader_test_result(proxy, ok=False, error="timed out")

        result = proxy_pool.resolve_working_proxy(str(source_file), tester=always_fail_tester)
        assert result is None
        assert proxy_pool.load_cached_proxy(str(source_file)) is None

    def test_force_refresh_ignores_a_still_working_cache(self, tmp_path):
        source_file = tmp_path / "proxies.txt"
        source_file.write_text("http://1.1.1.1:80\n", encoding="utf-8")
        proxy_pool.save_cached_proxy(str(source_file), "http://cached.example:80")

        calls = []

        def tester(proxy, cookies_path=None):
            calls.append(proxy)
            return downloader_test_result(proxy, ok=True)

        result = proxy_pool.resolve_working_proxy(str(source_file), force_refresh=True, tester=tester)
        assert result == "http://1.1.1.1:80"
        assert "http://cached.example:80" not in calls


def downloader_test_result(proxy, ok, error=None):
    from odl.models import ProxyCheckResult

    return ProxyCheckResult(proxy=proxy, ok=ok, latency_ms=12.3 if ok else None, error=error)
