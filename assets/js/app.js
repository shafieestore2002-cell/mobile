import { products, categories } from "./catalog.js";

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const number = new Intl.NumberFormat("fa-IR");
const money = (value) => number.format(value);
const icon = (name) =>
  `<svg class="icon" aria-hidden="true"><use href="#i-${name}"/></svg>`;
const escape = (text) =>
  String(text).replace(
    /[&<>"']/g,
    (char) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        char
      ],
  );
const byId = new Map(products.map((product) => [product.id, product]));
const storageKey = "shafiee-store-v1";
const pageSize = 8;
let toastTimer;
let category = "all";
let favoritesOnly = false;
let visibleCount = pageSize;
let query = "";

function sanitizeState(raw) {
  const next = { cart: {}, favorites: [] };
  if (!raw || typeof raw !== "object") return next;
  if (raw.cart && typeof raw.cart === "object" && !Array.isArray(raw.cart)) {
    for (const [id, quantity] of Object.entries(raw.cart)) {
      if (byId.has(id) && Number.isInteger(quantity) && quantity > 0)
        next.cart[id] = Math.min(quantity, 99);
    }
  }
  if (Array.isArray(raw.favorites))
    next.favorites = [...new Set(raw.favorites.filter((id) => byId.has(id)))];
  return next;
}
function readState() {
  let saved;
  try {
    saved = localStorage.getItem(storageKey);
  } catch {
    $("#storage-notice").hidden = false;
    return sanitizeState(null);
  }
  try {
    return sanitizeState(JSON.parse(saved));
  } catch {
    return sanitizeState(null);
  }
}
let state = readState();
function saveState() {
  try {
    localStorage.setItem(storageKey, JSON.stringify(state));
  } catch {
    $("#storage-notice").hidden = false;
  }
}
function normalize(text) {
  return String(text)
    .toLowerCase()
    .replace(/[۰-۹]/g, (digit) => String("۰۱۲۳۴۵۶۷۸۹".indexOf(digit)))
    .replace(/[٠-٩]/g, (digit) => String("٠١٢٣٤٥٦٧٨٩".indexOf(digit)))
    .replace(/[يى]/g, "ی")
    .replace(/ك/g, "ک")
    .replace(/[أإآ]/g, "ا")
    .replace(/[\u064b-\u065f\u0670]/g, "")
    .replace(/[\u200c\u200d]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}
function toast(message) {
  const target = $("#toast");
  clearTimeout(toastTimer);
  target.textContent = message;
  target.classList.add("is-visible");
  toastTimer = setTimeout(() => target.classList.remove("is-visible"), 3600);
}
function priceMarkup(price) {
  return `<span class="price"><span>${money(price)}</span><small>تومان</small></span>`;
}
function productCard(product) {
  const favorite = state.favorites.includes(product.id);
  const name = escape(product.name);
  return `<article class="product-card" data-product-id="${product.id}" data-category="${product.category}" data-price="${product.price}">
    <div class="product-visual">
      ${product.badge ? `<span class="product-badge ${product.badge === "انتخاب ویژه" ? "orange" : ""}">${escape(product.badge)}</span>` : ""}
      <button type="button" class="icon-button wishlist-button" data-action="favorite" data-id="${product.id}" aria-pressed="${favorite}" aria-label="${favorite ? "حذف" : "افزودن"} ${name} ${favorite ? "از" : "به"} علاقه‌مندی‌ها">${icon("heart")}</button>
      <button type="button" class="product-image-button" data-action="details" data-id="${product.id}" aria-label="جزئیات ${name}"><img src="${product.image}" alt="${name}" width="400" height="400" loading="lazy" decoding="async"></button>
    </div>
    <div class="product-info"><span class="product-overline" lang="en" dir="ltr">${escape(product.english)}</span>
      <h3 class="product-name"><button type="button" data-action="details" data-id="${product.id}">${name}</button></h3>
      <p class="product-subtitle">${escape(product.subtitle)}</p>
      <div class="product-footer">${priceMarkup(product.price)}<button type="button" class="add-button" data-action="add" data-id="${product.id}" aria-label="افزودن ${name} به سبد">${icon("plus")}</button></div>
    </div></article>`;
}
function filteredProducts() {
  const tokens = normalize(query).split(" ").filter(Boolean);
  let list = products.filter((product) => {
    const haystack = normalize(
      `${product.name} ${product.english} ${product.subtitle} ${categories[product.category]}`,
    );
    return (
      (category === "all" || category === product.category) &&
      (!favoritesOnly || state.favorites.includes(product.id)) &&
      tokens.every((token) => haystack.includes(token))
    );
  });
  const sort = $("#sort-select").value;
  if (sort === "price-asc") list.sort((a, b) => a.price - b.price);
  else if (sort === "price-desc") list.sort((a, b) => b.price - a.price);
  else if (sort === "name")
    list.sort((a, b) => a.name.localeCompare(b.name, "fa"));
  return list;
}
function renderProducts() {
  const list = filteredProducts();
  $("#product-grid").innerHTML = list
    .slice(0, visibleCount)
    .map(productCard)
    .join("");
  $("#results-count").textContent =
    `${money(list.length)} محصول${favoritesOnly ? " در علاقه‌مندی‌ها" : ""}${category !== "all" ? ` در ${categories[category]}` : ""}${query.trim() ? ` برای «${query.trim()}»` : ""}`;
  $("#empty-state").hidden = list.length !== 0;
  $("#empty-message").textContent = favoritesOnly
    ? "با زدن قلب روی محصولات، انتخاب‌های دلخواهت را اینجا جمع کن."
    : "یک عبارت دیگر یا دسته‌بندی متفاوت را امتحان کن.";
  $("#load-more").hidden = list.length <= visibleCount;
  $("#clear-favorites").hidden = !favoritesOnly;
  $$("#category-filters button").forEach((button) =>
    button.setAttribute(
      "aria-pressed",
      String(button.dataset.filter === category),
    ),
  );
}
function renderBadges() {
  const count = Object.values(state.cart).reduce(
    (sum, quantity) => sum + quantity,
    0,
  );
  $("#cart-count").textContent = money(count);
  $("#cart-button").setAttribute(
    "aria-label",
    `سبد خرید، ${money(count)} کالا`,
  );
  $("#favorites-count").textContent = money(state.favorites.length);
  $("#favorites-count").hidden = state.favorites.length === 0;
  $("#favorites-button").setAttribute("aria-pressed", String(favoritesOnly));
}
function renderCart(focusAction, focusId) {
  const entries = Object.entries(state.cart);
  $("#cart-items").innerHTML = entries.length
    ? entries
        .map(([id, quantity]) => {
          const product = byId.get(id);
          const name = escape(product.name);
          return `<article class="cart-item" data-cart-id="${id}"><img src="${product.image}" alt="${name}" width="76" height="93"><div><h3>${name}</h3>${priceMarkup(product.price)}<div class="cart-item-bottom"><div class="quantity-control" role="group" aria-label="تعداد ${name}"><button type="button" data-action="cart-decrease" data-id="${id}" aria-label="کاهش تعداد ${name}">${icon("minus")}</button><span aria-live="polite">${money(quantity)}</span><button type="button" data-action="cart-increase" data-id="${id}" aria-label="افزایش تعداد ${name}" ${quantity >= 99 ? "disabled" : ""}>${icon("plus")}</button></div><button type="button" class="remove-button" data-action="cart-remove" data-id="${id}" aria-label="حذف ${name} از سبد">حذف</button></div></div></article>`;
        })
        .join("")
    : `<div class="cart-empty">${icon("bag")}<h3>هنوز انتخابی اینجا نیست</h3><p>از فروشگاه شروع کن و چیزهایی را که دوست داری اضافه کن.</p></div>`;
  const total = entries.reduce(
    (sum, [id, quantity]) => sum + byId.get(id).price * quantity,
    0,
  );
  $("#cart-total").textContent = `${money(total)} تومان`;
  if (focusAction && $("#cart-dialog").open) {
    const replacement = $(
      `[data-action="${focusAction}"][data-id="${focusId}"]`,
      $("#cart-dialog"),
    );
    (replacement && !replacement.disabled
      ? replacement
      : $("[data-close-dialog]", $("#cart-dialog"))
    ).focus();
  }
}
function addToCart(id) {
  const current = state.cart[id] || 0;
  if (current >= 99) {
    toast("برای هر محصول حداکثر ۹۹ عدد می‌توان انتخاب کرد.");
    return;
  }
  state.cart[id] = current + 1;
  saveState();
  renderBadges();
  renderCart();
  toast(`${byId.get(id).name} به سبد اضافه شد.`);
  if ($("#product-dialog").open)
    $("#detail-feedback").textContent = "به سبد خرید اضافه شد.";
}
function toggleFavorite(id) {
  const wasFavorite = state.favorites.includes(id);
  state.favorites = wasFavorite
    ? state.favorites.filter((item) => item !== id)
    : [...state.favorites, id];
  saveState();
  renderBadges();
  if (favoritesOnly && wasFavorite) {
    const previousIndex = $$(".product-card").findIndex(
      (card) => card.dataset.productId === id,
    );
    renderProducts();
    const remaining = $$(".product-card");
    const next = remaining[Math.min(previousIndex, remaining.length - 1)];
    const focusTarget = next
      ? $('[data-action="favorite"]', next)
      : $("#reset-filters");
    focusTarget.focus({ preventScroll: true });
  } else
    $$(`[data-action="favorite"][data-id="${id}"]`).forEach((button) => {
      button.setAttribute("aria-pressed", String(!wasFavorite));
      button.setAttribute(
        "aria-label",
        `${wasFavorite ? "افزودن" : "حذف"} ${byId.get(id).name} ${wasFavorite ? "به" : "از"} علاقه‌مندی‌ها`,
      );
    });
  toast(
    wasFavorite ? "از علاقه‌مندی‌ها حذف شد." : "در علاقه‌مندی‌ها ذخیره شد.",
  );
}
const dialogOpeners = new WeakMap();
function openDialog(dialog, opener) {
  if (dialog.open) return;
  dialogOpeners.set(dialog, opener || document.activeElement);
  dialog.showModal();
  $("[data-close-dialog]", dialog)?.focus();
}
function openProduct(id, opener) {
  const product = byId.get(id);
  $("#product-detail").innerHTML =
    `<div class="product-detail-layout"><div class="detail-visual"><img src="${product.image}" alt="${escape(product.name)}" width="400" height="400"></div><div class="detail-info"><span class="product-overline" lang="en" dir="ltr">${escape(product.english)}</span><h2 id="detail-title">${escape(product.name)}</h2><p class="product-subtitle">${escape(product.subtitle)}</p><ul class="detail-specs">${product.specs.map((spec) => `<li>${escape(spec)}</li>`).join("")}</ul>${priceMarkup(product.price)}<button type="button" class="button button-orange" data-action="add" data-id="${id}">افزودن به سبد خرید ${icon("bag")}</button><p id="detail-feedback" class="detail-note" role="status" aria-live="polite"></p><p class="detail-note">قیمت نمایشی است. موجودی، مشخصات و شرایط گارانتی پیش از خرید نهایی تأیید می‌شوند.</p></div></div>`;
  openDialog($("#product-dialog"), opener);
}
function selectCategory(next) {
  category = Object.hasOwn(categories, next) ? next : "all";
  query = "";
  $("#search-input").value = "";
  favoritesOnly = false;
  visibleCount = pageSize;
  renderProducts();
  renderBadges();
}
function scrollToProducts() {
  $("#products").scrollIntoView({ block: "start" });
}
document.addEventListener("click", (event) => {
  const actionButton = event.target.closest("button[data-action]");
  if (actionButton) {
    const { action, id } = actionButton.dataset;
    if (!byId.has(id)) return;
    if (action === "add") addToCart(id);
    else if (action === "favorite") toggleFavorite(id);
    else if (action === "details") openProduct(id, actionButton);
    else if (action.startsWith("cart-")) {
      if (!state.cart[id]) return;
      if (action === "cart-increase")
        state.cart[id] = Math.min(state.cart[id] + 1, 99);
      else if (action === "cart-decrease") {
        state.cart[id] -= 1;
        if (state.cart[id] === 0) delete state.cart[id];
      } else if (action === "cart-remove") delete state.cart[id];
      saveState();
      renderBadges();
      renderCart(action, id);
    }
    return;
  }
  const categoryLink = event.target.closest("[data-category-link]");
  if (categoryLink) selectCategory(categoryLink.dataset.categoryLink);
  const closeButton = event.target.closest("[data-close-dialog]");
  if (closeButton) closeButton.closest("dialog").close();
  const cartOpener = event.target.closest("#cart-button, [data-open-cart]");
  if (cartOpener) {
    renderCart();
    openDialog($("#cart-dialog"), cartOpener);
  }
});
$("#category-filters").addEventListener("click", (event) => {
  const button = event.target.closest("[data-filter]");
  if (button) selectCategory(button.dataset.filter);
});
$("#sort-select").addEventListener("change", () => {
  visibleCount = pageSize;
  renderProducts();
});
$("#search-input").addEventListener("input", (event) => {
  query = event.target.value;
  category = "all";
  favoritesOnly = false;
  visibleCount = pageSize;
  renderProducts();
  renderBadges();
});
$("#search-form").addEventListener("submit", (event) => {
  event.preventDefault();
  scrollToProducts();
});
$("#load-more").addEventListener("click", () => {
  const previous = visibleCount;
  visibleCount += pageSize;
  renderProducts();
  const newlyShown = $$(".product-card")[previous];
  if (newlyShown)
    $('[data-action="details"]', newlyShown).focus({ preventScroll: true });
});
$("#reset-filters").addEventListener("click", () => {
  $("#sort-select").value = "featured";
  selectCategory("all");
  $("#search-input").focus({ preventScroll: true });
});
$("#favorites-button").addEventListener("click", () => {
  favoritesOnly = !favoritesOnly;
  category = "all";
  query = "";
  $("#search-input").value = "";
  visibleCount = pageSize;
  renderProducts();
  renderBadges();
  scrollToProducts();
});
$("#clear-favorites").addEventListener("click", () => {
  selectCategory("all");
  $("#favorites-button").focus({ preventScroll: true });
});
$("#replay-features").addEventListener("click", async () => {
  await customElements.whenDefined("shafiee-logo-motion");
  $("#features shafiee-logo-motion").replay();
});
function closeMenu() {
  $("#menu-button").setAttribute("aria-expanded", "false");
  $("#menu-button").setAttribute("aria-label", "باز کردن منو");
  $("#main-nav").classList.remove("is-open");
}
$("#menu-button").addEventListener("click", () => {
  const open = $("#menu-button").getAttribute("aria-expanded") !== "true";
  $("#menu-button").setAttribute("aria-expanded", String(open));
  $("#menu-button").setAttribute(
    "aria-label",
    open ? "بستن منو" : "باز کردن منو",
  );
  $("#main-nav").classList.toggle("is-open", open);
});
$("#main-nav").addEventListener("click", (event) => {
  if (event.target.closest("a")) closeMenu();
});
document.addEventListener("click", (event) => {
  if (!event.target.closest("#main-nav, #menu-button")) closeMenu();
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && $("#main-nav").classList.contains("is-open")) {
    closeMenu();
    $("#menu-button").focus();
  }
});
matchMedia("(min-width: 651px)").addEventListener("change", closeMenu);
$$("dialog").forEach((dialog) => {
  dialog.addEventListener("click", (event) => {
    if (event.target !== dialog) return;
    const rect = dialog.getBoundingClientRect();
    if (
      event.clientX < rect.left ||
      event.clientX > rect.right ||
      event.clientY < rect.top ||
      event.clientY > rect.bottom
    )
      dialog.close();
  });
  dialog.addEventListener("close", () => {
    const opener = dialogOpeners.get(dialog);
    if (opener?.isConnected) opener.focus({ preventScroll: true });
  });
  dialog.addEventListener("keydown", (event) => {
    if (event.key !== "Tab") return;
    const focusable = $$(
      'button:not([disabled]), a[href], input, select, [tabindex="0"]',
      dialog,
    ).filter((el) => el.getClientRects().length);
    const first = focusable[0],
      last = focusable.at(-1);
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  });
});
window.addEventListener("storage", (event) => {
  if (event.key !== storageKey && event.key !== null) return;
  state = readState();
  renderBadges();
  renderCart();
  renderProducts();
});
document.addEventListener(
  "error",
  (event) => {
    const image = event.target;
    if (image instanceof HTMLImageElement && !image.dataset.fallback) {
      image.dataset.fallback = "true";
      image.alt = `${image.alt || "تصویر محصول"} (تصویر در دسترس نیست)`;
      image.src = "shafiee-logo2.png";
      image.style.objectFit = "contain";
    }
  },
  true,
);
$("#copyright-year").textContent = new Intl.DateTimeFormat(
  "fa-IR-u-ca-persian",
  { year: "numeric", timeZone: "Asia/Tehran" },
).format(new Date());
renderProducts();
renderBadges();
renderCart();
