"""Browser checks for the uploaded logo motion in the fourth storefront section."""

import functools
import threading
import unittest
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
MOTION = "#features shafiee-logo-motion"


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, _format, *args):
        pass


class FeaturesAcceptance(unittest.TestCase):
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
            executable_path="/usr/bin/chromium", headless=True, args=["--no-sandbox"]
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
        self.javascript_errors = []
        self.external_requests = []
        self.failed_responses = []

    def tearDown(self):
        for context in self.contexts:
            context.close()
        self.assertEqual(self.javascript_errors, [], "Uncaught browser JavaScript error(s)")
        self.assertEqual(self.external_requests, [], "Unexpected external dependency")
        self.assertEqual(self.failed_responses, [], "Broken local document or asset")

    def open_store(self, width=1440, reduced_motion="no-preference"):
        context = self.browser.new_context(
            viewport={"width": width, "height": 1000 if width >= 768 else 844},
            reduced_motion=reduced_motion,
        )
        self.contexts.append(context)

        def local_only(route):
            parsed = urlparse(route.request.url)
            if parsed.scheme in ("data", "blob", "about") or parsed.hostname in (
                "127.0.0.1", "localhost", "::1"
            ):
                route.continue_()
            else:
                self.external_requests.append(route.request.url)
                route.abort()

        context.route("**/*", local_only)
        page = context.new_page()
        page.on("pageerror", lambda error: self.javascript_errors.append(str(error)))
        page.on(
            "response",
            lambda response: self.failed_responses.append((response.status, response.url))
            if response.status >= 400
            else None,
        )
        response = page.goto(self.base_url + "/index.html", wait_until="load")
        self.assertEqual(response.status, 200)
        page.wait_for_function("Boolean(customElements.get('shafiee-logo-motion'))")
        expect(page.locator("#product-grid .product-card[data-product-id]").first).to_be_visible()
        return page

    def test_fourth_section_is_accessible_and_fits_mobile_and_desktop(self):
        for width in (360, 390, 768, 1440):
            with self.subTest(width=width):
                page = self.open_store(width, reduced_motion="reduce")
                sections = page.locator("main > section").evaluate_all(
                    "sections => sections.map(section => section.id)"
                )
                self.assertEqual(sections[2:5], ["products", "features", "collections"])
                motion = page.locator(MOTION)
                expect(motion).to_have_attribute("role", "img")
                self.assertTrue(motion.get_attribute("aria-label"))
                expect(motion.locator(".logo")).to_have_count(1)
                expect(motion.locator("svg")).to_have_count(1)
                motion.scroll_into_view_if_needed()
                expect(motion).to_be_in_viewport(ratio=0.35)
                for node in (motion, motion.locator(".logo")):
                    bounds = node.bounding_box()
                    self.assertGreater(bounds["width"], 0)
                    self.assertGreater(bounds["height"], 0)
                    self.assertGreaterEqual(bounds["x"], -1)
                    self.assertLessEqual(bounds["x"] + bounds["width"], width + 1)
                self.assertLessEqual(
                    page.evaluate("document.documentElement.scrollWidth - innerWidth"), 1
                )
                expect(page.locator("#replay-features")).to_have_attribute("type", "button")

    def test_animation_pauses_offscreen_finishes_once_and_replays_from_button(self):
        page = self.open_store()
        motion = page.locator(MOTION)
        page.wait_for_function(
            "!document.querySelector('#features shafiee-logo-motion').running"
        )
        self.assertFalse(motion.evaluate("element => element.started"))
        motion.scroll_into_view_if_needed()
        page.wait_for_function(
            "document.querySelector('#features shafiee-logo-motion').running"
        )
        page.evaluate("window.scrollTo({top: 0, behavior: 'instant'})")
        page.wait_for_function(
            "!document.querySelector('#features shafiee-logo-motion').running"
        )
        self.assertFalse(motion.evaluate("element => element.finished"))
        motion.scroll_into_view_if_needed()
        page.wait_for_function(
            "document.querySelector('#features shafiee-logo-motion').finished", timeout=8000
        )
        self.assertFalse(motion.evaluate("element => element.running"))
        self.assertEqual(motion.locator(".logo").evaluate("node => getComputedStyle(node).opacity"), "1")

        # Returning to a completed component leaves the final logo in place.
        page.evaluate("window.scrollTo({top: 0, behavior: 'instant'})")
        page.wait_for_function(
            "!document.querySelector('#features shafiee-logo-motion').visible"
        )
        motion.scroll_into_view_if_needed()
        page.wait_for_function(
            "document.querySelector('#features shafiee-logo-motion').visible"
        )
        self.assertTrue(motion.evaluate("element => element.finished && !element.running"))
        page.locator("#replay-features").click()
        page.wait_for_function(
            """(() => {
                const motion = document.querySelector('#features shafiee-logo-motion');
                return motion.running && !motion.finished && motion.position < 2;
            })()"""
        )
        page.wait_for_function(
            "document.querySelector('#features shafiee-logo-motion').finished", timeout=8000
        )
        self.assertFalse(motion.evaluate("element => element.running"))

    def test_reduced_motion_keeps_static_logo_and_cart_still_works(self):
        page = self.open_store(width=390, reduced_motion="reduce")
        motion = page.locator(MOTION)
        motion.scroll_into_view_if_needed()
        self.assertTrue(motion.evaluate("element => element.finished && !element.running"))
        self.assertEqual(motion.locator(".logo").evaluate("node => getComputedStyle(node).opacity"), "1")
        self.assertTrue(
            motion.locator(".geometry [data-start]").evaluate_all(
                "items => items.every(node => getComputedStyle(node).opacity === '0')"
            )
        )
        page.locator("#replay-features").click()
        self.assertTrue(motion.evaluate("element => element.finished && !element.running"))
        product = page.locator("#product-grid .product-card[data-product-id]").first
        product_id = product.get_attribute("data-product-id")
        product.locator("button[data-action='add']").click()
        page.locator("#cart-button").click()
        expect(page.locator("#cart-dialog")).to_be_visible()
        expect(page.locator(f"#cart-dialog [data-cart-id='{product_id}']")).to_have_count(1)
        self.assertEqual(
            page.evaluate(
                "Object.values(JSON.parse(localStorage.getItem('shafiee-store-v1')).cart).reduce((a, b) => a + b, 0)"
            ),
            1,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
