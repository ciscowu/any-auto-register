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


if __name__ == "__main__":
    unittest.main()
