"""Local Chromium checks for the standalone logo animation and its lifecycle."""

import functools
import threading
import unittest
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, _format, *args):
        pass


class LogoMotionAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(
            ("127.0.0.1", 0), functools.partial(QuietHandler, directory=str(ROOT))
        )
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(
            executable_path="/usr/bin/chromium", args=["--no-sandbox"], headless=True
        )

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        cls.server.shutdown()
        cls.server.server_close()
        cls.server_thread.join(timeout=5)

    def setUp(self):
        self.contexts = []
        self.errors = []
        self.external_requests = []

    def tearDown(self):
        for context in self.contexts:
            context.close()
        self.assertEqual(self.errors, [], "Uncaught JavaScript error(s)")
        self.assertEqual(self.external_requests, [], "Unexpected external dependency")

    def open_logo(self, width=390, reduced_motion="no-preference"):
        context = self.browser.new_context(
            viewport={"width": width, "height": 844}, reduced_motion=reduced_motion
        )
        self.contexts.append(context)

        def local_only(route):
            if urlparse(route.request.url).hostname in ("127.0.0.1", "localhost", "::1"):
                route.continue_()
            else:
                self.external_requests.append(route.request.url)
                route.abort()

        context.route("**/*", local_only)
        page = context.new_page()
        page.on("pageerror", lambda error: self.errors.append(str(error)))
        # Observe actual browser scheduling without relying on app variables.
        page.add_init_script("""(() => {
            const request = requestAnimationFrame.bind(window);
            const cancel = cancelAnimationFrame.bind(window);
            const pending = window.__pendingLogoFrames = new Set();
            window.requestAnimationFrame = callback => {
                const id = request(time => { pending.delete(id); callback(time); });
                pending.add(id);
                return id;
            };
            window.cancelAnimationFrame = id => { pending.delete(id); cancel(id); };
        })();""")
        response = page.goto(self.base_url + "/logo-motion.html", wait_until="load")
        self.assertEqual(response.status, 200)
        expect(page.get_by_role("img", name="نشان شفیعی استور", exact=True)).to_be_visible()
        return page

    def test_mobile_canvas_and_accessible_return_link(self):
        for width in (360, 390, 768, 1440):
            with self.subTest(width=width):
                page = self.open_logo(width, reduced_motion="reduce")
                bounds = page.locator(".logo-container").bounding_box()
                self.assertLessEqual(bounds["width"], 500)
                self.assertGreaterEqual(bounds["x"], 0)
                self.assertLessEqual(bounds["x"] + bounds["width"], width)
                self.assertAlmostEqual(bounds["width"] / bounds["height"], 1.25, places=2)
                self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth - innerWidth"), 1)
                back = page.get_by_role("link", name="بازگشت به فروشگاه", exact=True)
                expect(back).to_be_in_viewport()
                back.focus()
                expect(back).to_be_focused()
                if width == 390:
                    back.press("Enter")
                    page.wait_for_url("**/index.html")
                    expect(page.locator("#search-input")).to_be_visible()

    def test_reduced_motion_is_visible_static_and_emits_no_particles(self):
        page = self.open_logo(reduced_motion="reduce")
        loops = page.locator(".loop-1, .loop-2, .loop-3")
        self.assertEqual(loops.count(), 3)
        for loop in loops.all():
            self.assertEqual(loop.evaluate("node => getComputedStyle(node).strokeDashoffset"), "0px")
            self.assertEqual(loop.evaluate("node => getComputedStyle(node).opacity"), "1")
            self.assertEqual(loop.evaluate("node => getComputedStyle(node).animationName"), "none")
        self.assertEqual(page.evaluate("window.__pendingLogoFrames.size"), 0)
        page.locator(".logo-container").evaluate("""node => {
            for (let i = 0; i < 200; i++) node.dispatchEvent(new PointerEvent('pointermove', {
                pointerType: 'mouse', clientX: 150, clientY: 200, bubbles: true
            }));
        }""")
        expect(page.locator(".pointer-particle, .ambient-particle")).to_have_count(0)
        self.assertEqual(page.evaluate("document.getAnimations().filter(a => a.playState === 'running').length"), 0)

    def test_animation_stops_for_hidden_tabs_and_live_motion_preferences(self):
        page = self.open_logo(width=768)
        page.wait_for_function("window.__pendingLogoFrames.size > 0", timeout=5000)
        self.assertEqual(page.locator(".ambient-particle").count(), 20)
        for loop in page.locator(".loop-1, .loop-2, .loop-3").all():
            self.assertEqual(loop.evaluate("node => getComputedStyle(node).strokeDashoffset"), "0px")

        page.locator(".logo-container").evaluate("""node => {
            for (let i = 0; i < 500; i++) node.dispatchEvent(new PointerEvent('pointermove', {
                pointerType: 'mouse', clientX: 300, clientY: 350, bubbles: true
            }));
        }""")
        self.assertGreater(page.locator(".pointer-particle").count(), 0)
        self.assertLessEqual(page.locator(".pointer-particle").count(), 12)

        # Simulate the browser visibility signal; headless tabs need not hide.
        page.evaluate("""Object.defineProperty(document, 'hidden', { configurable: true, get: () => true });
            document.dispatchEvent(new Event('visibilitychange'));""")
        self.assertEqual(page.evaluate("window.__pendingLogoFrames.size"), 0)
        expect(page.locator(".pointer-particle")).to_have_count(0)
        self.assertEqual(page.locator(".rotate-ring").evaluate("node => getComputedStyle(node).animationPlayState"), "paused")

        page.emulate_media(reduced_motion="reduce")
        expect(page.locator(".ambient-particle")).to_have_count(0)
        page.evaluate("""Object.defineProperty(document, 'hidden', { configurable: true, get: () => false });
            document.dispatchEvent(new Event('visibilitychange'));""")
        self.assertEqual(page.evaluate("window.__pendingLogoFrames.size"), 0)
        page.emulate_media(reduced_motion="no-preference")
        page.wait_for_function("window.__pendingLogoFrames.size > 0")
        expect(page.locator(".ambient-particle")).to_have_count(20)
        page.emulate_media(reduced_motion="reduce")
        page.wait_for_function("window.__pendingLogoFrames.size === 0")
        expect(page.locator(".ambient-particle, .pointer-particle")).to_have_count(0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
