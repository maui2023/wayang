# MovieHub

MovieHub is a static, responsive movie/TV/anime discovery website designed to run on GitHub Pages using **HTML5, Bootstrap 5.3.x, and vanilla JavaScript only**.

The public site does not require a backend. Catalog data is generated offline by a developer-side updater, normalized into static JSON files, committed to this repository, and consumed by the frontend.

> Working title: **MovieHub**. The name, branding, and visual identity may be changed later.

## Goals

- Browse movies, TV/drama series, and anime from one responsive catalog.
- Provide title metadata, synopsis, artwork, genres, dates, ratings, external IDs, and official trailers when available.
- Use official/licensed APIs, feeds, XML, or datasets where permitted.
- Host the frontend entirely on GitHub Pages.
- Keep API secrets out of browser code and committed public files.
- Update the catalog from a developer machine, then commit/push generated JSON to GitHub.
- Make the data pipeline extensible so additional providers can be added without rewriting the frontend.

## Non-goals

MovieHub is **not** a video hosting or piracy/streaming platform. It must not provide unauthorized full-movie/episode streams, download links, or re-hosted copyrighted trailers. For YouTube trailers, store the video ID/URL metadata and use the official YouTube embed/player where permitted.

## Technology constraints

### Production website

- HTML5
- Bootstrap **5.3.x**
- Vanilla JavaScript (ES6+)
- CSS
- Static JSON
- GitHub Pages

No React, Vue, Angular, Next.js, PHP, server database, or runtime backend is required for the production site.

### Developer updater

The offline updater may use Node.js or Python because it does not run as part of GitHub Pages. Prefer a simple, reproducible CLI with environment variables for API credentials.

## High-level architecture

```text
Official APIs / feeds / datasets
            |
            v
    Developer-side updater
            |
   fetch -> normalize -> dedupe
       -> validate -> generate
            |
            v
        data/*.json
            |
       git commit/push
            |
            v
      GitHub Repository
            |
            v
        GitHub Pages
            |
            v
HTML5 + Bootstrap + Vanilla JS
```

The browser should normally read only generated repository data and public assets. It must not expose private API keys.

## Suggested repository layout

```text
moviehub/
├── index.html
├── browse.html
├── details.html
├── search.html
├── 404.html
├── README.md
├── PRD.md
├── DEVELOPER.md
├── LICENSE
├── assets/
│   ├── css/
│   │   └── app.css
│   ├── js/
│   │   ├── app.js
│   │   ├── catalog.js
│   │   ├── details.js
│   │   ├── search.js
│   │   └── trailer.js
│   └── img/
├── data/
│   ├── manifest.json
│   ├── genres.json
│   ├── featured.json
│   ├── movies/
│   ├── tv/
│   └── anime/
└── tools/
    └── updater/
```

The implementation may refine this structure, but generated catalog data must remain clearly separated from frontend source files.

## Core user experience

The home page should provide a responsive navigation bar, featured/hero title, trending/popular sections, separate movie/TV/anime discovery sections, search, filters, poster cards, and trailer actions.

A title detail view should support poster/backdrop artwork, title/original title, year/release date, content type, synopsis, genres, rating, runtime/episode information when available, countries/languages, external IDs, and an official trailer.

Trailer playback should use a responsive Bootstrap modal with a YouTube embed. Destroy/reset the iframe when the modal closes so playback stops.

## Data philosophy

Do not make one enormous `movies.json` the permanent architecture. The updater should generate a lightweight manifest/index plus chunked catalog files so the site can scale without forcing every visitor to download the complete database.

Every provider must be converted into one canonical MovieHub schema before it reaches the frontend. Provider-specific differences belong in updater adapters, not UI code.

## Security and legal requirements

- Never commit API keys, tokens, cookies, passwords, or private credentials.
- Keep secrets in environment variables / ignored local configuration.
- Respect provider API terms, attribution rules, caching limits, rate limits, image policies, and redistribution restrictions.
- Prefer official trailers/channels and official embedding mechanisms.
- Do not download and re-host YouTube trailers unless explicit rights/permission exist.
- Do not add unauthorized streaming or download sources.
- Maintain provider attribution where required.

## Getting started for Codex

Read these files in order:

1. `PRD.md` — product requirements and acceptance criteria.
2. `DEVELOPER.md` — architecture, canonical schema, updater contract, frontend conventions, and implementation phases.
3. `README.md` — project overview and constraints.

Then implement the project incrementally. Do not silently replace the static GitHub Pages architecture with a server framework.

## Definition of done for v1

A v1 is complete when the repository can be deployed to GitHub Pages and a user can browse responsive movie/TV/anime catalogs from generated JSON, search/filter titles, open a detail view, and play an available official YouTube trailer, while a developer can run an updater locally to regenerate validated JSON without exposing API secrets.

See `PRD.md` and `DEVELOPER.md` for the complete requirements.

## Current implementation — real-data trial

The static frontend uses locally bundled Bootstrap 5.3.8, HTML5, CSS, vanilla ES modules, and generated JSON. It includes Malay-language navigation, home collections, browse/search with shareable filters, sorting, incremental results, detail pages, fallback/error states, and the trailer modal lifecycle.

The public catalog now contains **20 real TVmaze titles: 12 TV series and 8 anime**. This is a curated starter selection, not a complete or trending catalog. Posters are loaded from the provider CDN; summaries retain the source language. TVmaze attribution and CC BY-SA 4.0 licensing are included. Fictional samples remain only in `tools/updater/fixtures.json` for development.

**Movies and official trailers are not yet imported.** TVmaze supplies neither in this integration. Movie browsing explains its empty state, and trailer buttons remain disabled. A subsequent permitted movie/trailer provider is still needed for full v1 coverage.

### Run locally

```sh
python3 tools/updater/update.py --source tvmaze
python3 -m http.server 8080
```

Open `http://localhost:8080/`. Existing generated data can be previewed without rerunning the updater. No API key, frontend build or package installation is required. Importing data and loading remote posters require internet access. Opening HTML directly with `file://` is unsupported.

### Validate

```sh
python3 -m unittest discover -s tests -v
python3 tools/updater/update.py --source tvmaze --dry-run
```

See [updater documentation](tools/updater/README.md) for provider documentation, fixture mode, validation, classification, rate limiting, data sizes and publication recovery.

### GitHub Pages

Publish the repository root from your chosen branch in GitHub Pages settings. Page, asset and data URLs support project subpaths such as `/wayang/`; no build is required. Set canonical URLs and deployment-specific Open Graph artwork when the final public URL is known. This implementation has not been deployed.
