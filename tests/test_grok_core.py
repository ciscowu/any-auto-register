import sys
import types
import unittest
from unittest import mock

from platforms.grok.core import GrokRegister


class _FakeChromium:
    def __init__(self):
        self.launch_calls = []

    def launch(self, **kwargs):
        self.launch_calls.append(kwargs)
        return "browser"


class _FakePlaywright:
    def __init__(self):
        self.chromium = _FakeChromium()


class _FakeSyncPlaywrightFactory:
    def __init__(self, runtime):
        self.runtime = runtime

    def start(self):
        return self.runtime


class GrokRegisterLaunchBrowserTests(unittest.TestCase):
    def _make_patchright_modules(self, runtime):
        sync_api_module = types.ModuleType("patchright.sync_api")
        sync_api_module.sync_playwright = lambda: _FakeSyncPlaywrightFactory(runtime)

        patchright_module = types.ModuleType("patchright")
        patchright_module.sync_api = sync_api_module
        return {
            "patchright": patchright_module,
            "patchright.sync_api": sync_api_module,
        }

    def _launch_with_proxy(self, proxy):
        runtime = _FakePlaywright()
        register = GrokRegister(proxy=proxy, headless=True, log_fn=lambda *_args: None)

        with mock.patch.dict(sys.modules, self._make_patchright_modules(runtime)):
            with mock.patch(
                "platforms.grok.core.resolve_browser_headless",
                return_value=(True, "test"),
            ):
                with mock.patch(
                    "platforms.grok.core.ensure_browser_display_available"
                ):
                    playwright, browser = register._launch_browser()

        self.assertIs(playwright, runtime)
        self.assertEqual(browser, "browser")
        self.assertEqual(len(runtime.chromium.launch_calls), 1)
        return runtime.chromium.launch_calls[0]

    def test_launch_browser_normalizes_socks5h_proxy_for_playwright(self):
        launch_kwargs = self._launch_with_proxy("socks5h://warp:1080")

        self.assertEqual(
            launch_kwargs["proxy"],
            {"server": "socks5://warp:1080"},
        )

    def test_launch_browser_splits_http_proxy_credentials_for_playwright(self):
        launch_kwargs = self._launch_with_proxy(
            "http://us:6C26CDBF-69D7-49AF-A2E6-0CF7927001F2@resin:2260"
        )

        self.assertEqual(
            launch_kwargs["proxy"],
            {
                "server": "http://resin:2260",
                "username": "us",
                "password": "6C26CDBF-69D7-49AF-A2E6-0CF7927001F2",
            },
        )


class GrokRegisterTurnstileFallbackTests(unittest.TestCase):
    def test_read_turnstile_token_checks_turnstile_api_response(self):
        page = mock.Mock()

        def _fake_evaluate(script):
            if "getResponse" in script:
                return "t" * 30
            return ""

        page.evaluate.side_effect = _fake_evaluate

        token = GrokRegister._read_turnstile_token(page)

        self.assertEqual(token, "t" * 30)

    def test_native_click_returns_empty_when_platform_unsupported(self):
        register = GrokRegister(log_fn=lambda *_args: None)

        with mock.patch.object(register, "_supports_native_click", return_value=False):
            token = register._native_click_turnstile(mock.Mock(), {"x": 1, "y": 2, "height": 20}, 8)

        self.assertEqual(token, "")

    def test_solver_fallback_runs_without_native_click_on_unsupported_platform(self):
        register = GrokRegister(log_fn=lambda *_args: None)
        page = mock.Mock()
        page.mouse = mock.Mock()

        with mock.patch.object(register, "_supports_native_click", return_value=False):
            with mock.patch.object(
                register,
                "_find_turnstile_widget",
                return_value=(None, {"x": 10, "y": 20, "width": 120, "height": 40}),
            ):
                with mock.patch.object(register, "_read_turnstile_token", return_value=""):
                    with mock.patch.object(register, "_wait_turnstile_token", return_value=""):
                        with mock.patch.object(register, "_has_turnstile_error", return_value=False):
                            with mock.patch.object(
                                register, "_solve_turnstile_by_solver", return_value="t" * 30
                            ) as solve_by_solver:
                                with mock.patch.object(
                                    register, "_native_click_turnstile"
                                ) as native_click:
                                    token = register._solve_turnstile_on_page(page)

        self.assertEqual(token, "t" * 30)
        native_click.assert_not_called()
        solve_by_solver.assert_called_once_with(page)

    def test_shadow_dom_click_path_runs_before_page_mouse_click(self):
        register = GrokRegister(log_fn=lambda *_args: None)
        page = mock.Mock()
        page.mouse = mock.Mock()
        frame = mock.Mock()

        with mock.patch.object(register, "_supports_native_click", return_value=False):
            with mock.patch.object(
                register,
                "_find_turnstile_widget",
                return_value=(frame, {"x": 10, "y": 20, "width": 120, "height": 40}),
            ):
                with mock.patch.object(register, "_read_turnstile_token", return_value=""):
                    with mock.patch.object(
                        register, "_click_turnstile_challenge_button", return_value=True, create=True
                    ):
                        with mock.patch.object(
                            register, "_wait_turnstile_token", return_value="t" * 30
                        ):
                            token = register._solve_turnstile_on_page(page)

        self.assertEqual(token, "t" * 30)
        page.mouse.move.assert_not_called()


if __name__ == "__main__":
    unittest.main()
