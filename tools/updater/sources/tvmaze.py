"""TVmaze public API adapter. See ../README.md for attribution and scope."""
import json
import time
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE = 'https://api.tvmaze.com'
LICENSE = 'https://creativecommons.org/licenses/by-sa/4.0/'
LANGUAGES = {'English':'en','Japanese':'ja','Korean':'ko','Malay':'ms','German':'de','Spanish':'es','French':'fr','Chinese':'zh','Indonesian':'id','Thai':'th'}

class PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0
    def handle_starttag(self, tag, attrs):
        if tag in ('script','style'): self.hidden += 1
        if tag in ('p','br','div'): self.parts.append(' ')
    def handle_endtag(self, tag):
        if tag in ('script','style'): self.hidden = max(0, self.hidden-1)
        if tag in ('p','div'): self.parts.append(' ')
    def handle_data(self, data):
        if not self.hidden: self.parts.append(data)


def plain_text(value):
    parser = PlainText(); parser.feed(value or '')
    return ' '.join(''.join(parser.parts).split())


class Client:
    def __init__(self, opener=urlopen, sleep=time.sleep):
        self.opener, self.sleep = opener, sleep
        self.last_request = 0
    def get(self, path, allow_not_found=False):
        for attempt in range(4):
            self.sleep(max(0, .6 - (time.monotonic()-self.last_request)))
            self.last_request = time.monotonic()
            request = Request(BASE+path, headers={'User-Agent':'MovieHub-offline-updater/1.0', 'Accept':'application/json'})
            try:
                with self.opener(request, timeout=30) as response:
                    return json.load(response)
            except HTTPError as error:
                if error.code == 404 and allow_not_found:
                    return None
                if error.code not in (429,500,502,503,504) or attempt == 3:
                    raise ValueError(f'TVmaze request failed: {path} (HTTP {error.code})') from None
                delay = error.headers.get('Retry-After', '') if error.headers else ''
                self.sleep(min(30, max(2**(attempt+1), int(delay) if delay.isdigit() else 0)))
            except (URLError, TimeoutError, OSError):
                if attempt == 3: raise ValueError(f'TVmaze request failed after retries: {path}') from None
                self.sleep(2**(attempt+1))


def normalize(show, kind, akas=None, images=None, seasons=None):
    if kind not in ('tv','anime'):
        raise ValueError('TVmaze selection must be tv or anime')
    if kind == 'anime' and show.get('type') != 'Animation':
        raise ValueError('Explicit anime selection must match an Animation record')
    ident = str(show['id'])
    poster = show.get('image') or {}
    backgrounds = [img for img in images or [] if img.get('type') == 'background']
    background = next((img for img in backgrounds if img.get('main')), next(iter(backgrounds), None))
    background_url = ((background or {}).get('resolutions') or {}).get('original', {}).get('url')
    premiere = show.get('premiered')
    rating = (show.get('rating') or {}).get('average')
    aliases = sorted({item['name'] for item in akas or [] if item.get('name') and item['name'] != show['name']})
    language = show.get('language')
    external = {key:str(value) for key,value in (show.get('externals') or {}).items() if value is not None}
    external['tvmaze'] = ident
    # A network's country is not necessarily a show's production country.
    counts = [season.get('episodeOrder') for season in seasons or []]
    episodes = sum(counts) if counts and all(isinstance(n,int) and n >= 0 for n in counts) else None
    return dict(schema_version=1, id=f'{kind}-tvmaze-{ident}', type=kind,
        title=show['name'], original_title=None, aliases=aliases,
        year=int(premiere[:4]) if premiere else None, release_date=premiere,
        overview=plain_text(show.get('summary')), genres=sorted({re.sub(r'[^a-z0-9]+','-',genre.lower()).strip('-') for genre in show.get('genres',[])}),
        poster={'url':poster.get('medium') or poster.get('original'),'original_url':poster.get('original'),'source':'tvmaze'} if poster else None,
        backdrop={'url':background_url,'source':'tvmaze'} if background_url else None,
        rating={'value':rating,'scale':10,'votes':None,'source':'TVmaze'} if rating is not None else None,
        popularity=None, runtime_minutes=None,
        series={'seasons':len(seasons) if seasons else None,'episodes':episodes,'episode_runtime_minutes':show.get('averageRuntime') or show.get('runtime')},
        status=show.get('status'), countries=[], broadcast_countries=sorted({country for outlet in [show.get('network'),show.get('webChannel')] if outlet for country in [(outlet.get('country') or {}).get('code')] if country}), languages=[LANGUAGES.get(language,language)] if language else [],
        external_ids=external, trailer=None,
        sources=[{'provider':'tvmaze','provider_id':ident,'url':show['url'],'license':'CC BY-SA 4.0','license_url':LICENSE}],
        updated_at=datetime.fromtimestamp(show['updated'], timezone.utc).isoformat().replace('+00:00','Z'))


def fetch(config, client=None):
    client = client or Client()
    records = []
    seen = set()
    for selection in config['shows']:
        ident, kind = selection['id'], selection['type']
        if not isinstance(ident,int) or ident <= 0 or ident in seen:
            raise ValueError('TVmaze config contains an invalid or repeated ID')
        seen.add(ident)
        show = client.get(f'/shows/{ident}')
        if show.get('id') != ident:
            raise ValueError('TVmaze returned an unexpected identity')
        records.append(normalize(show, kind, client.get(f'/shows/{ident}/akas'), client.get(f'/shows/{ident}/images'), client.get(f'/shows/{ident}/seasons')))
        print(f'TVmaze: {show["name"]}', flush=True)
    return records


def fetch_all(config, cache_dir, client=None):
    """Walk the official show index until its documented terminal 404."""
    from pathlib import Path
    client = client or Client()
    cache_dir = Path(cache_dir); cache_dir.mkdir(parents=True, exist_ok=True)
    anime_ids = {item['id'] for item in config['shows'] if item['type'] == 'anime'}
    records = []
    page = 0
    while True:
        path = cache_dir / f'page-{page:04}.json'
        if path.exists() and time.time() - path.stat().st_mtime < 86400:
            shows = json.loads(path.read_text())
        else:
            shows = client.get(f'/shows?page={page}', allow_not_found=True)
            if shows is not None:
                import os
                temporary = path.with_name(f'{path.stem}.{os.getpid()}.tmp')
                try:
                    temporary.write_text(json.dumps(shows, ensure_ascii=False))
                    temporary.replace(path)
                except Exception:
                    if temporary.exists():
                        temporary.unlink(missing_ok=True)
                    if path.exists():
                        shows = json.loads(path.read_text())
                    else:
                        raise
        if shows is None:
            break
        if not isinstance(shows,list):
            raise ValueError(f'Unexpected TVmaze index page {page}')
        for show in shows:
            kind = 'anime' if show.get('type') == 'Animation' else 'tv'
            records.append(normalize(show,kind))
        if page % 10 == 0:
            print(f'TVmaze index: page {page}, {len(records):,} titles', flush=True)
        page += 1
    print(f'TVmaze index complete: {page} pages, {len(records):,} titles', flush=True)
    return records
