"""Browser acceptance tests for the static storefront.

Run from the repository root with:
    python -m unittest discover -s tests -p 'test_*.py' -v

The suite serves the checkout itself, uses the installed Chromium binary, and
blocks every browser request to a non-local host. No running server is needed.
"""

import functools
import re
import threading
import unittest
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
STORAGE_KEY = "shafiee-store-v1"
DIGIT_MAP = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def number(text):
    """Read a displayed Persian/Arabic/English integer, including separators."""
    return int(re.sub(r"\D", "", text.translate(DIGIT_MAP)) or "0")


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, _format, *args):
        pass


class StorefrontAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        handler = functools.partial(QuietHandler, directory=str(ROOT))
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(
            executable_path="/usr/bin/chromium",
            headless=True,
            args=["--no-sandbox"],
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
        self.blocked_requests = []
        self.failed_local_responses = []
        self.context, self.page = self.new_page()

    def tearDown(self):
        for context in self.contexts:
            context.close()
        self.assertEqual(self.javascript_errors, [], "Uncaught browser JavaScript error(s)")
        self.assertEqual(self.failed_local_responses, [], "Broken local asset or document response(s)")
        self.assertEqual(self.blocked_requests, [], "Unexpected external network dependency")

    def new_page(self, width=1440, height=1000, mobile=False, reduced_motion="no-preference"):
        context = self.browser.new_context(
            viewport={"width": width, "height": height},
            is_mobile=mobile,
            has_touch=mobile,
            reduced_motion=reduced_motion,
        )
        self.contexts.append(context)

        def local_requests_only(route):
            parsed = urlparse(route.request.url)
            if parsed.scheme in ("data", "blob", "about") or parsed.hostname in (
                "127.0.0.1", "localhost", "::1"
            ):
                route.continue_()
            else:
                self.blocked_requests.append(route.request.url)
                route.abort()

        context.route("**/*", local_requests_only)
        page = context.new_page()
        page.on("pageerror", lambda error: self.javascript_errors.append(str(error)))
        page.on(
            "response",
            lambda response: self.failed_local_responses.append((response.status, response.url))
            if response.status >= 400 and urlparse(response.url).hostname in ("127.0.0.1", "localhost", "::1")
            else None,
        )
        return context, page

    def open_store(self, page=None, path="/index.html"):
        page = page or self.page
        response = page.goto(self.base_url + path, wait_until="domcontentloaded")
        self.assertIsNotNone(response)
        self.assertEqual(response.status, 200)
        expect(page.locator("#product-grid .product-card[data-product-id]").first).to_be_visible()
        return page

    def cards(self, page=None):
        return (page or self.page).locator("#product-grid .product-card[data-product-id]")

    def ids(self, page=None):
        return self.cards(page).evaluate_all("cards => cards.map(card => card.dataset.productId)")

    def storage(self, page=None):
        return (page or self.page).evaluate(
            "key => JSON.parse(localStorage.getItem(key))", STORAGE_KEY
        )

    def cart_count(self, expected):
        expect(self.page.locator("#cart-count")).to_have_text(re.compile(r"[۰-۹٠-٩0-9]+"))
        self.assertEqual(number(self.page.locator("#cart-count").inner_text()), expected)

    def test_catalog_pagination_and_all_images_work_without_external_network(self):
        page = self.open_store()
        self.assertEqual(page.locator("html").get_attribute("lang"), "fa")
        self.assertEqual(page.locator("html").get_attribute("dir"), "rtl")
        self.assertEqual(self.cards().count(), 8)
        expect(page.locator("#load-more")).to_be_visible()
        page.locator("#load-more").click()
        self.assertGreaterEqual(self.cards().count(), 10)
        self.assertEqual(len(set(self.ids())), self.cards().count())
        self.assertGreaterEqual(number(page.locator("#results-count").inner_text()), 10)

        # Eagerly request lazy images too, so a missing below-the-fold asset fails.
        page.locator("img").evaluate_all("images => images.forEach(image => image.loading = 'eager')")
        page.wait_for_function(
            "Array.from(document.images).every(image => image.complete && image.naturalWidth > 0)"
        )
        self.assertGreater(page.locator("img").count(), 5)

    def test_categories_and_numeric_price_sort(self):
        page = self.open_store()
        for category in ("iphone", "mac", "ipad", "watch", "audio", "accessories"):
            with self.subTest(category=category):
                page.locator(f"#category-filters button[data-filter='{category}']").click()
                self.assertGreater(self.cards().count(), 0)
                self.assertEqual(
                    set(self.cards().evaluate_all("cards => cards.map(card => card.dataset.category)")),
                    {category},
                )

        page.locator("#category-filters button[data-filter='all']").click()
        for order, reverse in (("price-asc", False), ("price-desc", True)):
            with self.subTest(order=order):
                page.locator("#sort-select").select_option(order)
                prices = self.cards().evaluate_all("cards => cards.map(card => Number(card.dataset.price))")
                self.assertEqual(prices, sorted(prices, reverse=reverse))
                self.assertTrue(all(price > 0 for price in prices))

    def test_persian_arabic_and_english_search_and_empty_state_reset(self):
        page = self.open_store()
        search = page.locator("#search-input")
        matches = []
        for query in ("آیفون ۱۷", "آیفون 17", "آيفون ١٧", "iPhone 17"):
            with self.subTest(query=query):
                search.fill(query)
                expect(self.cards().first).to_be_visible()
                matches.append(set(self.ids()))
                self.assertTrue(matches[-1])
        for equivalent in matches[1:]:
            self.assertEqual(equivalent, matches[0])

        search.fill("no-such-product-785-zzzz")
        expect(self.cards()).to_have_count(0)
        expect(page.locator("#reset-filters")).to_be_visible()
        page.locator("#reset-filters").click()
        expect(search).to_have_value("")
        expect(self.cards()).to_have_count(8)

    def test_cart_quantities_totals_removal_and_reload(self):
        page = self.open_store()
        first, second = self.ids()[:2]
        prices = self.cards().evaluate_all("cards => cards.slice(0, 2).map(card => Number(card.dataset.price))")
        for product_id in (first, first, second):
            page.locator(f"#product-grid button[data-action='add'][data-id='{product_id}']").click()
        self.cart_count(3)
        page.locator("#cart-button").click()
        expect(page.locator("#cart-dialog")).to_be_visible()
        expect(page.locator("#cart-dialog [data-cart-id]")).to_have_count(2)
        self.assertEqual(number(page.locator("#cart-total").inner_text()), prices[0] * 2 + prices[1])

        page.locator(f"#cart-dialog button[data-action='cart-decrease'][data-id='{first}']").click()
        self.cart_count(2)
        self.assertEqual(self.storage()["cart"][first], 1)
        page.locator(f"#cart-dialog button[data-action='cart-increase'][data-id='{first}']").click()
        self.cart_count(3)
        page.locator(f"#cart-dialog button[data-action='cart-remove'][data-id='{second}']").click()
        self.cart_count(2)
        expect(page.locator(f"#cart-dialog [data-cart-id='{second}']")).to_have_count(0)
        self.assertEqual(number(page.locator("#cart-total").inner_text()), prices[0] * 2)
        self.assertEqual(self.storage()["cart"], {first: 2})

        page.keyboard.press("Escape")
        page.reload(wait_until="domcontentloaded")
        self.cart_count(2)
        page.locator("#cart-button").click()
        expect(page.locator(f"#cart-dialog [data-cart-id='{first}']")).to_be_visible()
        self.assertEqual(number(page.locator("#cart-total").inner_text()), prices[0] * 2)
        dialog_text = page.locator("#cart-dialog").inner_text()
        self.assertIn("خرید آنلاین", dialog_text)
        self.assertRegex(dialog_text, r"به[‌\s]*زودی")

    def test_favorite_state_is_accessible_and_persists(self):
        page = self.open_store()
        product_id = self.ids()[0]
        selector = f"#product-grid button[data-action='favorite'][data-id='{product_id}']"
        favorite = page.locator(selector)
        expect(favorite).to_have_attribute("aria-pressed", "false")
        favorite.click()
        expect(favorite).to_have_attribute("aria-pressed", "true")
        self.assertIn(product_id, self.storage()["favorites"])
        page.reload(wait_until="domcontentloaded")
        expect(page.locator(selector)).to_have_attribute("aria-pressed", "true")
        page.locator(selector).click()
        expect(page.locator(selector)).to_have_attribute("aria-pressed", "false")
        self.assertNotIn(product_id, self.storage()["favorites"])

    def test_labeled_all_products_links_reset_search_and_category(self):
        page = self.open_store()
        for selector in ("#categories .text-link", "footer a[data-category-link='all']"):
            for active_mode in ("category", "search"):
                with self.subTest(link=selector, active_mode=active_mode):
                    if active_mode == "category":
                        page.locator("#category-filters button[data-filter='audio']").click()
                        self.assertEqual(
                            set(self.cards().evaluate_all("cards => cards.map(card => card.dataset.category)")),
                            {"audio"},
                        )
                    else:
                        page.locator("#search-input").fill("آیفون ۱۷")
                        self.assertGreater(self.cards().count(), 0)
                        self.assertLess(self.cards().count(), 8)
                    page.locator(selector).click()
                    expect(page.locator("#search-input")).to_have_value("")
                    expect(self.cards()).to_have_count(8)
                    expect(page.locator("#category-filters button[data-filter='all']")).to_have_attribute(
                        "aria-pressed", "true"
                    )

    def test_unavailable_storage_keeps_cart_and_favorites_with_truthful_notice(self):
        self.context.add_init_script("""Object.defineProperty(Storage.prototype, 'setItem', {
            configurable: true,
            value() { throw new DOMException('Storage is unavailable', 'SecurityError'); }
        });""")
        page = self.open_store()
        product_id = self.ids()[0]
        page.locator(f"#product-grid button[data-action='add'][data-id='{product_id}']").click()
        self.cart_count(1)
        favorite = page.locator(f"#product-grid button[data-action='favorite'][data-id='{product_id}']")
        favorite.click()
        expect(favorite).to_have_attribute("aria-pressed", "true")
        page.locator("#cart-button").click()
        expect(page.locator(f"#cart-dialog [data-cart-id='{product_id}']")).to_be_visible()
        notice = page.locator("#storage-notice")
        expect(notice).to_be_visible()
        self.assertRegex(notice.inner_text(), r"ذخیره|حافظه")
        self.assertRegex(notice.inner_text(), r"بازدید|مرورگر")

    def test_dialog_keyboard_focus_escape_and_return_to_opener(self):
        page = self.open_store()
        product_id = self.ids()[0]
        for opener_selector, dialog_selector in (
            (f"#product-grid button[data-action='details'][data-id='{product_id}']", "#product-dialog"),
            ("#cart-button", "#cart-dialog"),
        ):
            with self.subTest(dialog=dialog_selector):
                opener = page.locator(opener_selector).first
                opener.focus()
                opener.press("Enter")
                dialog = page.locator(dialog_selector)
                expect(dialog).to_be_visible()
                self.assertTrue(dialog.evaluate("dialog => dialog.contains(document.activeElement)"))
                for key in ("Tab", "Tab", "Tab", "Tab", "Shift+Tab", "Shift+Tab"):
                    page.keyboard.press(key)
                    self.assertTrue(dialog.evaluate("dialog => dialog.contains(document.activeElement)"))
                page.keyboard.press("Escape")
                expect(dialog).not_to_be_visible()
                expect(opener).to_be_focused()

    def test_malformed_saved_state_recovers_and_remains_usable(self):
        for invalid in (
            "'{invalid JSON'",
            "'null'",
            "JSON.stringify({cart: {'unknown-product': -3}, favorites: 'invalid'})",
        ):
            with self.subTest(saved_value=invalid):
                context, page = self.new_page()
                context.add_init_script(
                    f"localStorage.setItem('shafiee-store-v1', {invalid});"
                )
                self.open_store(page)
                self.assertEqual(number(page.locator("#cart-count").inner_text()), 0)
                product_id = self.ids(page)[0]
                page.locator(f"#product-grid button[data-action='add'][data-id='{product_id}']").click()
                self.assertEqual(number(page.locator("#cart-count").inner_text()), 1)
                self.assertEqual(self.storage(page)["cart"], {product_id: 1})
                self.assertIsInstance(self.storage(page)["favorites"], list)

    def test_mobile_navigation_and_responsive_product_access(self):
        for width in (360, 390, 768, 1440):
            with self.subTest(width=width):
                _, page = self.new_page(width=width, height=844, mobile=width < 768)
                self.open_store(page)
                overflow = page.evaluate(
                    "Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - innerWidth"
                )
                self.assertLessEqual(overflow, 1, f"Horizontal page overflow at {width}px")
                last_card = self.cards(page).last
                last_card.scroll_into_view_if_needed()
                expect(last_card.locator("button[data-action='add']")).to_be_in_viewport()
                if width == 390:
                    page.evaluate("scrollTo(0, 0)")
                    toggle = page.locator("#menu-button")
                    expect(toggle).to_be_visible()
                    expect(toggle).to_have_attribute("aria-expanded", "false")
                    toggle.click()
                    expect(toggle).to_have_attribute("aria-expanded", "true")
                    expect(page.locator("#main-nav")).to_be_visible()
                    toggle.click()
                    expect(toggle).to_have_attribute("aria-expanded", "false")

    def test_reduced_motion_and_legacy_entry_remain_usable(self):
        _, page = self.new_page(width=390, height=844, mobile=True, reduced_motion="reduce")
        self.open_store(page, "/shafiee-advanced.html")
        page.wait_for_url(re.compile(r"/(?:index\.html)?(?:[?#].*)?$"))
        expect(page.locator("#search-input")).to_be_visible()
        self.assertEqual(self.cards(page).count(), 8)
        product_id = self.ids(page)[0]
        page.locator(f"#product-grid button[data-action='details'][data-id='{product_id}']").first.click()
        expect(page.locator("#product-dialog")).to_be_visible()
        page.keyboard.press("Escape")
        expect(page.locator("#product-dialog")).not_to_be_visible()

    def test_scroll_story_morphs_and_scrubs_the_local_video(self):
        page = self.open_store()
        expect(page.locator('html')).to_have_attribute('data-motion', 'full')
        stage = page.locator('#story-stage')
        original = page.locator('#story-morph').get_attribute('d')
        metrics = page.locator('#hero-story').evaluate(
            'el => ({top: el.offsetTop, travel: el.offsetHeight - document.querySelector("#story-stage").offsetHeight - 12})'
        )
        self.assertGreater(metrics['travel'], 100)
        page.evaluate('(m) => scrollTo({top: m.top + m.travel * .72 - 12, behavior: "instant"})', metrics)
        page.wait_for_function('Number(document.querySelector("#story-stage").dataset.storyProgress) > .70')
        self.assertNotEqual(page.locator('#story-morph').get_attribute('d'), original)
        expect(page.locator('#story-finale')).to_be_visible()
        self.assertFalse(page.locator('#story-finale').evaluate('el => el.inert'))
        page.wait_for_function('document.querySelector("#story-video").currentTime > 1')
        self.assertTrue(page.locator('#story-video').evaluate('el => el.paused && el.muted'))
        page.evaluate('(m) => scrollTo({top: m.top - 12, behavior: "instant"})', metrics)
        page.wait_for_function('Number(document.querySelector("#story-stage").dataset.storyProgress) < .01')
        self.assertTrue(page.locator('#story-finale').evaluate('el => el.inert'))

    def test_motion_control_persists_without_losing_the_cart(self):
        page = self.open_store()
        first = self.ids()[0]
        page.locator(f"button[data-action='add'][data-id='{first}']").click()
        page.locator('#motion-toggle').click()
        expect(page.locator('html')).to_have_attribute('data-motion', 'reduced')
        expect(page.locator('#motion-toggle')).to_have_attribute('aria-pressed', 'true')
        self.cart_count(1)
        page.reload(wait_until='networkidle')
        expect(page.locator('html')).to_have_attribute('data-motion', 'reduced')
        self.cart_count(1)
        self.assertEqual(page.locator('#story-stage').evaluate('el => getComputedStyle(el).position'), 'relative')
        self.assertEqual(page.locator('#story-video').get_attribute('src'), None)
        page.locator('#motion-toggle').click()
        expect(page.locator('html')).to_have_attribute('data-motion', 'full')

    def test_system_reduced_motion_starts_static_and_all_cards_remain_usable(self):
        _, page = self.new_page(width=390, height=844, mobile=True, reduced_motion='reduce')
        self.open_store(page)
        expect(page.locator('html')).to_have_attribute('data-motion', 'reduced')
        self.assertEqual(page.locator('#story-video').get_attribute('src'), None)
        self.assertEqual(page.locator('#story-stage').evaluate('el => getComputedStyle(el).position'), 'relative')
        # The organic card corners must not clip the wishlist touch targets.
        for favorite in self.cards(page).locator('button[data-action="favorite"]').all():
            favorite.click()
            expect(favorite).to_have_attribute('aria-pressed', 'true')
        page.locator('#motion-toggle').click()
        expect(page.locator('html')).to_have_attribute('data-motion', 'full')
        self.assertEqual(page.locator('#story-stage').evaluate('el => getComputedStyle(el).position'), 'sticky')


if __name__ == "__main__":
    unittest.main(verbosity=2)
