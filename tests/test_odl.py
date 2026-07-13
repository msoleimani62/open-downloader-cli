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

from odl import constants as c

from odl import cookies
from odl import downloader
from odl import config as config_module
from odl import playlist_state
from odl.diagnostics import _parse_version_tuple
from odl.errors import ErrorCategory, CLIENT_FALLBACK_RETRYABLE_CATEGORIES, classify_error



@pytest.fixture(autouse=True)
def isolated_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(c, "CONFIG_DIR", tmp_path / ".config" / "opendl")
    monkeypatch.setattr(c, "CONFIG_FILE", tmp_path / ".config" / "opendl" / "config.json")
    monkeypatch.setattr(c, "COOKIES_DEFAULT", tmp_path / "cookies.txt")
    monkeypatch.setattr(c, "ENCRYPTED_COOKIES_FILE", tmp_path / ".config" / "opendl" / "cookies.enc")
    monkeypatch.setattr(c, "LOG_FILE", tmp_path / ".config" / "opendl" / "opendl.log")
    monkeypatch.setattr(c, "LOG_DIR", tmp_path / ".config" / "opendl" / "logs")
    monkeypatch.setattr(c, "PLAYLIST_STATE_DIR", tmp_path / ".config" / "opendl" / "playlist_state")
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

    def test_full_encrypt_decrypt_roundtrip_with_correct_password(self, monkeypatch):
        c.COOKIES_DEFAULT.write_text(
            "# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t0\tTEST\tabc123\n"
        )
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
        with pytest.raises(SystemExit):
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
        [(480, "bestvideo[height<=480]+bestaudio/best[height<=480]"),
         (1080, "bestvideo[height<=1080]+bestaudio/best[height<=1080]")],
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
    def test_desktop_linux_true_without_android_markers(self, monkeypatch):
        monkeypatch.setattr(c, "ANDROID_MARKER_PATHS", [Path("/nonexistent-marker-path")])
        for var in c.ANDROID_MARKER_ENV_VARS:
            monkeypatch.delenv(var, raising=False)
        monkeypatch.setattr(cookies.sys, "platform", "linux")
        assert cookies.is_desktop_linux() is True

    def test_desktop_linux_false_with_termux_env_var(self, monkeypatch):
        monkeypatch.setattr(c, "ANDROID_MARKER_PATHS", [Path("/nonexistent-marker-path")])
        monkeypatch.setenv("TERMUX_VERSION", "0.118")
        monkeypatch.setattr(cookies.sys, "platform", "linux")
        assert cookies.is_desktop_linux() is False
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
        opts = downloader.ydl_opts_base(
            None, 480, False, False, "%(title)s.%(ext)s", False, None, {}
        )
        assert opts["ignoreerrors"] is True
