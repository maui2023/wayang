# MovieHub offline updater

## Run

Python 3.10+ with only the standard library:

```sh
python3 tools/updater/update.py --source tvmaze --dry-run
python3 tools/updater/update.py --source tvmaze
python3 -m unittest discover -s tests -v
```

The default source is now **TVmaze**. It fetches the 20 stable provider IDs in `config/tvmaze.json`: 12 TV series and 8 explicitly selected anime. This is a curated trial, not TVmaze's full catalog or a trending chart. No API key or `.env` is required. Network access is required only when running the updater; the public frontend fetches repository JSON, with artwork loaded directly from TVmaze's image CDN.

For isolated fictional-data development, explicitly select the old fixture source:

```sh
python3 tools/updater/update.py --source fixture --dry-run
python3 tools/updater/update.py --source fixture
python3 tools/updater/update.py --source fixture --input path/to/canonical-records.json
```

The second command replaces the public catalog with fixtures; rerun the TVmaze updater to restore real records. No real and fictional records are mixed by either default mode.

## Provider contract

Official documentation and usage terms: https://www.tvmaze.com/api (reviewed 2026-09-25).

TVmaze's public API does not require authentication. Its documentation permits image CDN hotlinking and licenses API data under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). MovieHub links to TVmaze and the license in the footer and on title pages, preserves per-record source URLs, and distributes its normalized metadata adaptations under the same license in generated `data/LICENSE.txt`. This data license does not assign a license to unrelated application source. Artwork is linked, never mirrored.

The adapter uses `/shows/:id`, `/akas`, `/images` and `/seasons`. Requests are sequential, spaced at least 0.6 seconds apart, with a descriptive User-Agent. HTTP 429 and selected transient 5xx/network failures retry up to four total attempts with bounded backoff; numeric Retry-After is respected up to 30 seconds. Any unresolved fetch/parse/validation failure aborts the batch before publication. No incomplete provider batch replaces public data.

## Normalization decisions

- Identity is `<tv|anime>-tvmaze-<id>`. Treat configured type as stable; classification changes would change a public ID and need a migration.
- Anime IDs are explicitly curated in config, and must also have TVmaze type `Animation`. Language alone never classifies anime.
- Provider HTML summaries become plain text. Display titles are preserved; alternate titles feed search. Unknown original titles stay null.
- Medium posters are used on cards; original posters/backdrops on details/hero.
- Ratings retain TVmaze's ten-point scale. Vote counts and popularity are unavailable and remain null. Default ordering is rating, never fabricated popularity.
- Series episode totals represent the sum of known season `episodeOrder` values, displayed as **episod dipesan** (ordered episodes). If any season order is missing, the total is omitted. These are not claimed to be aired-episode counts. Episode runtime is kept separately from film runtime.
- Network country does not imply production country; country remains empty. Language codes are mapped for known languages; unknown provider language labels are retained.
- TVmaze does not provide movie catalog entries or official YouTube trailers here. The movie category explains its empty state; trailer actions remain disabled. No trailer IDs are guessed.

## Generation and recovery

Records are sorted by stable ID and split into 100-record chunks by type. The compact search index excludes full summaries. Home collections embed up to six compact records per populated type; the homepage fetches one full hero chunk, not the search index. The initial real catalog totals 66,445 JSON bytes; the largest file is 23,924 bytes. Revisit index partitioning at 1 MiB and partition manifest ID lookups for larger catalogs.

`dataset_version` is a deterministic content hash; `generated_at` is the latest source update timestamp, not the import wall clock. The frontend versions JSON requests with this hash. Exact identical duplicates collapse; conflicting same-ID records or repeated external identities fail for review. Similar titles never merge automatically.

Required fields, identities, dates, ratings, artwork/source URLs, trailer IDs and obvious credential fields are validated. Staging checks all manifest paths/counts, search rows and featured IDs. The old directory is renamed to `.data-backup`, then complete staging is renamed to `data`; caught publication failures restore the backup. This is a recoverable two-rename swap, not a transactional atomic exchange. Run only one updater at a time. If interrupted between renames, inspect and restore `.data-backup` before retrying. Deploy separately after reviewing generated changes.

## Browser checks

`tests/browser.cjs` uses Playwright only as a developer test dependency. With Playwright and Chromium installed and an HTTP server running:

```sh
BASE_URL=http://localhost:8080/ node tests/browser.cjs
```

Set `CHROME_PATH` for an installed Chrome binary. Repeat with a project subpath, such as `/wayang/`. Tests derive expected titles/counts from the current dataset and cover responsive navigation, alias search, filters/reset, pagination, missing data, malformed JSON, attribution and modal cleanup using a blocked test player. Real YouTube playback is not verified by these tests.
