# Local image library

The supplied `Apple Store/Apple Store Online - Apple` directory is preserved.
Every one of its 462 image files is mapped in `image-manifest.json` to a local,
byte-identical asset under `images/`. Four exact duplicates share a destination,
leaving 458 unique files (25,181,389 bytes). No external image host is required.

Paths in the manifest are relative to the site's root. Use them directly from
the root HTML pages, or prefix with `/` when linking from nested pages.

| Folder | Contents |
| --- | --- |
| `images/categories/` | Product-family navigation illustrations |
| `images/products/` | Product photographs, alternate views, and phone heroes |
| `images/promotions/` | Editorial cards and supplied social-preview artwork |
| `images/swatches/` | Color chips and color-selection strips |
| `images/icons/` | Saved SVG icons and the recycling icon |
| `images/support/` | Supplied specialist avatars |
| `images/reference/` | Seven unrelated portfolio/design screenshots |
| `images/utility/` | Tiny saved-page GIF/PNG utility files |

Original names are retained in URL-safe lowercase form. A supplied ` (1)` suffix
becomes `-large`. The manifest records the original path, public path, category,
type, dimensions, format, byte count, and SHA-256 digest. `duplicateOf` identifies
the source that shares the stored copy. Visually similar JPEG/WebP/PNG files are
retained separately; only byte-for-byte duplicates are merged.

## Recommended storefront assets

Prefer the supplied WebP variants where available. The clean phone heroes are
PNG files and are only 332 × 420 pixels; avoid displaying them far beyond that
size. They are suitable for product cards.

| Use | Path |
| --- | --- |
| iPhone 17 Pro product | `images/products/iphone-get-ready-iphone-17-pro-hero-202509.png` |
| iPhone 17 product | `images/products/iphone-get-ready-iphone-17-hero-202509.png` |
| iPhone Air product | `images/products/iphone-get-ready-iphone-air-hero-202509.png` |
| AirPods Pro product | `images/products/airpods-pro-3-hero-select-202509.webp` |
| AirPods Max product | `images/products/airpods-max-select-202409-midnight.webp` |
| MagSafe charger | `images/products/mgd74.webp` |
| USB-C power adapter | `images/products/mgkn4.webp` |
| Apple Pencil | `images/products/muwa3.webp` |
| iPhone category | `images/categories/store-card-13-iphone-nav-202609.webp` |
| Mac category | `images/categories/store-card-13-mac-nav-202603.webp` |
| iPad category | `images/categories/store-card-13-ipad-nav-202405.webp` |
| Watch category | `images/categories/store-card-13-watch-nav-202609.webp` |
| AirPods category | `images/categories/store-card-13-airpods-nav-202509.webp` |
| Accessories category | `images/categories/store-card-13-accessories-nav-202609.webp` |
| Generic phone close-up | `images/promotions/store-card-40-iphone-18-pro-202609.webp` |

## Content checks

- The source includes promotional filenames for newer model names. Filenames
  alone do not verify product availability or specifications. Confirm SKU data
  before using those names in product listings.
- Several `M…` images show cases, chargers, straps, or keyboards. They should not
  be presented as bare iPhones, Macs, iPads, or complete watches. No clean,
  standalone MacBook or iPad product hero is included; use category imagery until
  matching product photography is supplied.
- `reference/` contains unrelated portfolio screenshots, retained for
  completeness and excluded from storefront recommendations.
- `utility/` contains 2 × 2 GIFs and 10 × 5 PNGs from the saved page. These are
  retained for completeness and should not be used as visible product images.
- `icons/image-33.svg`, `image-34.svg`, and `image-35.svg` have unbound XML
  namespace prefixes in the supplied originals. The latter two contain
  zero-height shared SVG definitions. Their manifest records warnings; avoid
  using these files as standalone images. Originals are unchanged.
- The supplied SVG files were checked for scripts, inline event handlers, and
  external URL references. None were found by those checks.

When deploying the site, include the complete `assets/` directory. This local
organization does not publish files to a third-party storage account.
