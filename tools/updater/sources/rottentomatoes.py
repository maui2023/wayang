"""Rotten Tomatoes public browse adapter for popular and in-theater movies."""
import json
import os
import re
import socket
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

socket.setdefaulttimeout(30)

BASE_CNAPI = 'https://www.rottentomatoes.com/cnapi/browse'
LICENSE = 'https://www.rottentomatoes.com/help_faq'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'application/json'
}

CATEGORIES = [
    'movies_in_theaters/sort:popular',
    'movies_at_home/sort:popular',
    'movies_at_home/sort:top_box_office',
    'movies_at_home/sort:audience_highest'
]


def parse_rt_date(text):
    if not text:
        return None, None
    m = re.search(r'([A-Za-z]{3}\s+\d{1,2},\s+(\d{4}))', text)
    if m:
        try:
            dt = datetime.strptime(m.group(1), '%b %d, %Y')
            return dt.strftime('%Y-%m-%d'), int(m.group(2))
        except ValueError:
            pass
    m_year = re.search(r'\b(19\d{2}|20\d{2})\b', text)
    if m_year:
        return None, int(m_year.group(1))
    return None, None


def normalize_item(item):
    title = (item.get('title') or '').strip()
    if not title:
        return None

    media_url = item.get('mediaUrl') or ''
    slug_match = re.search(r'/m/([^/?#]+)', media_url)
    slug = slug_match.group(1) if slug_match else re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
    clean_slug = re.sub(r'[^a-z0-9-]+', '-', slug.lower()).strip('-')
    if not clean_slug:
        return None

    ident = f'movie-rt-{clean_slug}'
    release_date, year = parse_rt_date(item.get('releaseDateText'))

    # Calculate rating on a 10-point scale from criticsScore or audienceScore
    critics = item.get('criticsScore') or {}
    audience = item.get('audienceScore') or {}
    score_val = critics.get('score') or audience.get('score')
    rating = None
    if score_val and str(score_val).isdigit():
        val = round(int(score_val) / 10.0, 1)
        if 0 <= val <= 10:
            rating = {
                'value': val,
                'scale': 10,
                'votes': None,
                'source': 'Rotten Tomatoes'
            }

    poster_uri = item.get('posterUri')
    poster = None
    if poster_uri and poster_uri.startswith('https://'):
        poster = {
            'url': poster_uri,
            'original_url': poster_uri,
            'source': 'rottentomatoes'
        }

    url = f'https://www.rottentomatoes.com{media_url}' if media_url.startswith('/') else 'https://www.rottentomatoes.com/'

    now_iso = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    return {
        'schema_version': 1,
        'id': ident,
        'type': 'movie',
        'title': title,
        'original_title': None,
        'aliases': [],
        'year': year,
        'release_date': release_date,
        'overview': '',
        'genres': [],
        'poster': poster,
        'backdrop': None,
        'rating': rating,
        'popularity': None,
        'runtime_minutes': None,
        'series': None,
        'status': 'Released',
        'countries': ['US'],
        'broadcast_countries': [],
        'languages': ['en'],
        'external_ids': {'rottentomatoes': clean_slug},
        'trailer': None,
        'sources': [{
            'provider': 'rottentomatoes',
            'provider_id': clean_slug,
            'url': url,
            'license': 'Proprietary / Promotional',
            'license_url': LICENSE
        }],
        'updated_at': now_iso
    }


def fetch(cache_dir, max_pages=3):
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    seen_ids = set()
    records = []

    for cat in CATEGORIES:
        cat_slug = re.sub(r'[^a-z0-9]+', '-', cat.lower()).strip('-')
        cursor = None
        for page in range(max_pages):
            page_file = cache_dir / f'{cat_slug}-page-{page:02}.json'
            data = None
            if page_file.exists() and time.time() - page_file.stat().st_mtime < 86400:
                try:
                    data = json.loads(page_file.read_text())
                except Exception:
                    data = None

            if data is None:
                url = f'{BASE_CNAPI}/{cat}' + (f'?after={cursor}' if cursor else '')
                req = Request(url, headers=HEADERS)
                try:
                    with urlopen(req, timeout=15) as resp:
                        data = json.load(resp)
                    tmp_file = page_file.with_name(f'{page_file.stem}.{os.getpid()}.tmp')
                    try:
                        tmp_file.write_text(json.dumps(data, ensure_ascii=False))
                        tmp_file.replace(page_file)
                    except Exception:
                        if tmp_file.exists():
                            tmp_file.unlink(missing_ok=True)
                    time.sleep(0.3)
                except (HTTPError, URLError, TimeoutError, OSError) as err:
                    print(f'Rotten Tomatoes request failed for {cat} p{page}: {err}', flush=True)
                    break

            items = data.get('grid', {}).get('list', []) if isinstance(data, dict) else []
            for item in items:
                rec = normalize_item(item)
                if rec and rec['id'] not in seen_ids:
                    seen_ids.add(rec['id'])
                    records.append(rec)

            page_info = data.get('pageInfo', {}) if isinstance(data, dict) else {}
            if not page_info.get('hasNextPage'):
                break
            cursor = page_info.get('endCursor')
            if not cursor:
                break

    print(f'Rotten Tomatoes index: {len(records)} movies retrieved', flush=True)
    return records
