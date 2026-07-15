# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A static, single-owner marketing/reference site (Korean, `lang="ko"`) cataloguing Bacha Coffee's bean lineup — not affiliated with Bacha Coffee (see the disclaimer notice on every detail page). It is a plain HTML/CSS/JS site with no build step, no package manager, and no test suite, deployed via GitHub Pages at `https://youngsic1236.github.io/bacha-coffee-guide-/`.

## Development workflow

There is no build, lint, or test tooling in this repo (no `package.json`, no CI config). Development is:

- Edit the HTML files directly.
- Preview locally by opening `index.html` in a browser, or serving the directory (e.g. `python3 -m http.server`) so relative links (`coffee/...`, `images/...`) resolve.
- Commit and push; GitHub Pages serves directly from the repo.

When changing anything visual or interactive, actually open the page in a browser and click through it (filters, search, quiz, modal) — there's no automated test to catch regressions.

## Structure

- `index.html` — the entire home page: inline `<style>`, all 46 coffee `<article class="card">` entries, and inline `<script>` blocks implementing every interactive feature. This one file is ~2,600 lines and is the primary surface for most changes.
- `coffee/*.html` — one static detail page per coffee (46 files, matching the 46 cards in `index.html`), each a self-contained page with its own inline styles and JSON-LD structured data. Linked from each card via `coffee/<slug>.html`.
- `images/` — product photos, organized into subfolders that mirror the product categories (`single origin/`, `Decaffeinated/`, `Nomad WB/`, `Fine Flavoured Coffee Drip bag (12p)/`, `Drip Bag Gift Box/`). Folder and file names contain spaces and are referenced with `%20`-encoded, full raw-GitHub URLs (`https://raw.githubusercontent.com/youngsic1236/bacha-coffee-guide-/main/images/...`) rather than relative paths — this is intentional so Open Graph/social-card scrapers (which don't run relative to the page) can resolve images.
- `sitemap.xml`, `robots.txt` — SEO plumbing; `sitemap.xml` lists every `coffee/*.html` URL and must stay in sync with the `coffee/` directory.

## Coffee data is triplicated — the key gotcha

Each coffee's data exists in **three independent places** that must be kept in sync by hand whenever a coffee is added, removed, or edited:

1. The `<article class="card" data-cat="..." data-acidity="..." data-strength="...">` block in `index.html` (name, origin, roast badge, flavor tags, description, strength/acidity meters, image URL, link to the detail page).
2. The corresponding `coffee/<slug>.html` detail page (same info restated in a full page with JSON-LD `additionalProperty` metadata).
3. The `QUIZ_DATA` JS array inline in `index.html` (a JSON-like array of `{kr, en, origin, flag, tags, acidity, cat}` objects used to generate quiz questions).

There's also `sitemap.xml`, which needs a new `<url>` entry for any new detail page. There is no shared data source or generator script — treat any coffee-data edit as a 4-way find-and-replace across `index.html`'s card, `index.html`'s `QUIZ_DATA` entry, the matching `coffee/*.html` file, and `sitemap.xml`.

## `index.html` architecture (front page)

All logic lives in inline `<script>` tags in a fairly linear, non-modular style (global functions and variables, no framework, no modules). Key pieces, in the order they appear:

- **Supabase-backed quiz leaderboard**: `SUPA_URL`/`SUPA_KEY` (anon key, intentionally public per Supabase's client-side model) hit a `quiz_rankings` table directly via REST (`submitRanking`, `loadLeaderboard`). Scores are grouped/averaged client-side.
- **Filter bar + search** (`applyFilters`, `isNaturalLanguageQuery`, `parseTextInput`): cards are filtered by category (`data-cat`), acidity (`data-acidity`), and strength (`data-strength`) chips, plus a free-text search box that also tries to parse natural-language preference sentences (Korean signal words like "산미", "고소", "진한") into filter criteria.
- **Recommendation flow** (`toggleRecommend`, `rec-*` elements): a short guided-choice quiz that scores cards against user answers and shows top matches.
- **Trivia quiz** (`startQuiz`, `renderQuizQuestion`, `renderMatchQuestion`, `QUIZ_DATA`): multiple question types (multiple-choice, matching) generated from `QUIZ_DATA`; feeds into the Supabase leaderboard above.
- **Detail modal** (`#detail-modal-overlay`, `closeDetailModal`): clicking a card opens an in-page modal with story/aroma/pairing/reviews sections, populated from the clicked card's DOM plus additional embedded content — an alternative to navigating to the `coffee/*.html` page.
- **Price tags** (`renderPriceTags`, `getPriceInfo`, `PRICE_BY_CAT`, `PREMIUM_NAMES`): prices are derived at render time from category and a hardcoded premium-name list, not stored per-card.

## Conventions to follow when adding a coffee

- Pick a `data-cat` from the existing set: `single`, `flavoured`, `decaf`, `wb` (whole bean), `gift`.
- `data-search` on each card is a hand-maintained space-separated bag of Korean/English keywords (name, origin, flavor notes) used by the search box — keep it populated for new cards.
- Detail page filenames are kebab-case English slugs (e.g. `sidamo-mountain.html`); whole-bean variants of an existing coffee use a `-wb` suffix (e.g. `blue-danube-wb.html`) rather than a new slug.
- Match the existing meta tag / Open Graph / JSON-LD boilerplate in other `coffee/*.html` files when creating a new one — canonical URL, `og:*`, `twitter:*`, and the breadcrumb `application/ld+json` block all follow the same template.
- Every detail page ends with the non-affiliation disclaimer `<div class="notice">` — keep it on any new page.
