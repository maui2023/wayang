#!/usr/bin/env python3
"""Generate validated static catalogs from TVmaze or local fixtures."""
import argparse
import hashlib
import json
import re
import shutil
import sys
import tempfile
from collections import defaultdict, Counter
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
UPDATER_DIR = Path(__file__).resolve().parent
if str(UPDATER_DIR) not in sys.path:
    sys.path.insert(0, str(UPDATER_DIR))

TYPES = ('movie', 'tv', 'anime')
CHUNK_SIZE = 100


def validate(records):
    if not isinstance(records, list) or not records:
        raise ValueError('Catalog must be a nonempty array')
    ids, external = set(), set()
    for item in records:
        for key in ('schema_version', 'id', 'type', 'title', 'sources', 'updated_at'):
            if key not in item:
                raise ValueError(f'Missing required field: {key}')
        if item['schema_version'] != 1 or item['type'] not in TYPES:
            raise ValueError('Unsupported schema/type')
        if not isinstance(item['title'], str) or not item['title'].strip():
            raise ValueError('Empty title')
        if not re.fullmatch(r'[a-z0-9-]+', item['id']) or item['id'] in ids:
            raise ValueError('Invalid or duplicate ID')
        ids.add(item['id'])
        datetime.fromisoformat(item['updated_at'].replace('Z', '+00:00'))
        if item.get('release_date'):
            date.fromisoformat(item['release_date'])
        if not item['sources'] or any(not s.get('provider') or not s.get('provider_id') for s in item['sources']):
            raise ValueError('Missing provenance')
        rating = item.get('rating')
        if rating and not (0 < rating['scale'] and 0 <= rating['value'] <= rating['scale']):
            raise ValueError('Rating outside declared scale')
        for source in item['sources']:
            for key in ('url', 'license_url'):
                if source.get(key) and not (urlsplit(source[key]).scheme == 'https' and urlsplit(source[key]).netloc):
                    raise ValueError('Unsafe source URL')
        for key in ('poster', 'backdrop'):
            value = item.get(key)
            if value:
                url = value['url']
                if value.get('original_url') and not (urlsplit(value['original_url']).scheme == 'https' and urlsplit(value['original_url']).netloc):
                    raise ValueError('Unsafe original image URL')
                parts = urlsplit(url)
                if not ((parts.scheme == 'https' and parts.netloc) or (url.startswith('assets/img/') and '..' not in url)):
                    raise ValueError('Unsafe image URL')
        trailer = item.get('trailer')
        if trailer and (trailer.get('provider') != 'youtube' or trailer.get('official') is not True or not re.fullmatch(r'[A-Za-z0-9_-]{11}', trailer.get('video_id', ''))):
            raise ValueError('Invalid official trailer')
        for provider, identity in item.get('external_ids', {}).items():
            identity_key = (item['type'], provider, identity)
            if identity_key in external:
                raise ValueError('Duplicate external identity requires review')
            external.add(identity_key)
    def check_keys(value):
        if isinstance(value,dict):
            for key,child in value.items():
                if re.fullmatch(r'(?i)(api[_-]?key|access[_-]?token|password|secret)',key):
                    raise ValueError('Possible credential field in catalog')
                check_keys(child)
        elif isinstance(value,list):
            for child in value: check_keys(child)
    check_keys(records)


def deduplicate(records):
    """Collapse exact repeats only. Conflicting identities must be reviewed."""
    by_id = {}
    for item in records:
        previous = by_id.get(item['id'])
        if previous is not None and previous != item:
            raise ValueError('Conflicting records with same ID')
        by_id[item['id']] = item
    return sorted(by_id.values(), key=lambda item: item['id'])


def normalize_title_for_merge(title):
    return re.sub(r'[^a-z0-9]+', '', (title or '').lower())


def merge_records(records):
    """Merge records referring to the same title (e.g. across Wikidata and Rotten Tomatoes)."""
    merged = []
    lookup = {}

    for item in records:
        norm_title = normalize_title_for_merge(item.get('title'))
        year = item.get('year')
        kind = item.get('type')
        imdb_id = item.get('external_ids', {}).get('imdb')
        rt_id = item.get('external_ids', {}).get('rottentomatoes')
        wiki_id = item.get('external_ids', {}).get('wikidata')
        tvmaze_id = item.get('external_ids', {}).get('tvmaze')

        match = None
        if imdb_id:
            match = lookup.get((kind, 'imdb', imdb_id))
        if not match and rt_id:
            match = lookup.get((kind, 'rottentomatoes', rt_id))
        if not match and wiki_id:
            match = lookup.get((kind, 'wikidata', wiki_id))
        if not match and tvmaze_id:
            match = lookup.get((kind, 'tvmaze', tvmaze_id))
        if not match and norm_title and year:
            candidate = lookup.get((kind, norm_title, year))
            if candidate:
                conflict = False
                for prov in ('wikidata', 'tvmaze', 'rottentomatoes'):
                    c_id = candidate.get('external_ids', {}).get(prov)
                    i_id = item.get('external_ids', {}).get(prov)
                    if c_id and i_id and str(c_id) != str(i_id):
                        conflict = True
                        break
                if not conflict:
                    match = candidate

        if match:
            match['aliases'] = sorted(set(match.get('aliases', []) + item.get('aliases', [])))
            match['genres'] = sorted(set(match.get('genres', []) + item.get('genres', [])))
            match['countries'] = sorted(set(match.get('countries', []) + item.get('countries', [])))
            match['languages'] = sorted(set(match.get('languages', []) + item.get('languages', [])))
            for k, v in item.get('external_ids', {}).items():
                if k not in match['external_ids']:
                    match['external_ids'][k] = v
                    lookup[(kind, k, v)] = match
            existing_sources = {(s['provider'], s['provider_id']) for s in match.get('sources', [])}
            for s in item.get('sources', []):
                if (s['provider'], s['provider_id']) not in existing_sources:
                    match['sources'].append(dict(s))
            if not match.get('poster') and item.get('poster'):
                match['poster'] = item['poster']
            if not match.get('rating') and item.get('rating'):
                match['rating'] = item['rating']
            if not match.get('overview') and item.get('overview'):
                match['overview'] = item['overview']
            if not match.get('release_date') and item.get('release_date'):
                match['release_date'] = item['release_date']
        else:
            rec_copy = dict(item)
            rec_copy['aliases'] = list(item.get('aliases', []))
            rec_copy['genres'] = list(item.get('genres', []))
            rec_copy['countries'] = list(item.get('countries', []))
            rec_copy['languages'] = list(item.get('languages', []))
            rec_copy['external_ids'] = dict(item.get('external_ids', {}))
            rec_copy['sources'] = [dict(s) for s in item.get('sources', [])]
            merged.append(rec_copy)
            if imdb_id:
                lookup[(kind, 'imdb', imdb_id)] = rec_copy
            if rt_id:
                lookup[(kind, 'rottentomatoes', rt_id)] = rec_copy
            if wiki_id:
                lookup[(kind, 'wikidata', wiki_id)] = rec_copy
            if tvmaze_id:
                lookup[(kind, 'tvmaze', tvmaze_id)] = rec_copy
            if norm_title and year:
                lookup[(kind, norm_title, year)] = rec_copy

    return merged


def resolve_external_conflicts(records, primary_providers=None):
    if primary_providers is None:
        primary_providers = set(get_registered_sources().keys())
    owners=defaultdict(list)
    for row in records:
        for provider,ident in row.get('external_ids',{}).items():
            owners[(row['type'],provider,ident)].append(row)
    conflicts=[]
    for (kind,provider,ident),rows in owners.items():
        if len(rows)<2: continue
        if provider in primary_providers: raise ValueError(f'Duplicate primary provider identity: {provider}={ident}')
        conflicts.append(dict(type=kind,provider=provider,identifier=ident,ids=[row['id'] for row in rows]))
        for row in rows: del row['external_ids'][provider]
    return records,conflicts


def compact(item):
    row = {key: item.get(key) for key in ('id','type','title','original_title','aliases','year','release_date','genres','languages','countries','broadcast_countries')}
    row['poster'] = (item.get('poster') or {}).get('url')
    row['rating'] = (item.get('rating') or {}).get('value')
    return row


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n')


def generate(records, target):
    validate(records)
    digest = hashlib.sha256(('catalog-v2:' + json.dumps(records, sort_keys=True)).encode()).hexdigest()[:16]
    manifest = dict(schema_version=1, dataset_version=digest,
                    generated_at=max(row['updated_at'] for row in records), counts={}, chunks={},
                    files={key:f'data/{filename}.json' for key,filename in [('genres','genres'),('featured','featured'),('search_index','search-index')]})
    providers = sorted({source['provider'] for row in records for source in row['sources']})
    manifest['is_demo'] = providers == ['original-fixture']
    manifest['providers'] = providers
    manifest['attributions'] = []
    if 'tvmaze' in providers:
        manifest['attributions'].append(dict(name='TVmaze', url='https://www.tvmaze.com/', license='CC BY-SA 4.0', license_url='https://creativecommons.org/licenses/by-sa/4.0/', changes='Metadata normalized; summaries converted to plain text; selected anime classified by MovieHub.'))
    collections = []
    for kind in TYPES:
        subset = [row for row in records if row['type'] == kind]
        manifest['counts'][kind] = len(subset)
        manifest['chunks'][kind] = []
        for offset in range(0, len(subset), CHUNK_SIZE):
            chunk = subset[offset:offset+CHUNK_SIZE]
            path = f'{kind}/{offset//CHUNK_SIZE+1:04}.json'
            write(target/path, chunk)
            manifest['chunks'][kind].append(dict(path=f'data/{path}',count=len(chunk),first_id=chunk[0]['id'],last_id=chunk[-1]['id'],bytes=(target/path).stat().st_size))
        if not subset:
            continue
        collections.append(dict(type=kind,title={'movie':'Filem pilihan','tv':'Siri untuk diikuti','anime':'Dunia animasi'}[kind],items=[compact(row) for row in sorted(subset,key=lambda r: -((r.get('rating') or {}).get('value',0)))[:6]]))
    # Card/search shards are partitioned by type and one primary region, sorted by rating.
    # Region unions in metadata include coproductions and broadcast country separately.
    buckets = defaultdict(list)
    for row in records:
        region = next(iter(row.get('countries') or row.get('broadcast_countries') or []), 'other')
        buckets[(row['type'],region)].append(compact(row))
    shards = []
    for (kind,region), rows in sorted(buckets.items()):
        rows.sort(key=lambda row: (-(row['rating'] if row['rating'] is not None else -1), row['title'].casefold(), row['id']))
        for offset in range(0,len(rows),500):
            batch = rows[offset:offset+500]
            path = f'indexes/{kind}-{region}-{offset//500:04}.json'
            write(target/path,batch)
            facets = {key:sorted({v for row in batch for v in (row.get(key) or [])}) for key in ('genres','languages','countries','broadcast_countries')}
            facets['years'] = sorted({row['year'] for row in batch if row.get('year') is not None})
            shards.append(dict(path='data/'+path,type=kind,count=len(batch),max_rating=batch[0]['rating'] if batch[0]['rating'] is not None else -1,facets=facets,bytes=(target/path).stat().st_size))
    search = dict(schema_version=2,shards=shards,facets={key:sorted({v for shard in shards for v in shard['facets'][key]}) for key in ('genres','languages','countries','broadcast_countries','years')})
    write(target/'search-index.json', search)
    manifest['regional_counts'] = {country:{kind:sum(row['type']==kind and country in set((row.get('countries') or [])+(row.get('broadcast_countries') or [])) for row in records) for kind in TYPES} for country in ('MY','ID','TH')}
    manifest['index_shards'] = len(shards)
    write(target/'genres.json', sorted({genre for row in records for genre in row.get('genres', [])}))
    for country,name in [('MY','Malaysia'),('ID','Indonesia'),('TH','Thailand')]:
        subset = [row for row in records if country in set((row.get('countries') or []) + (row.get('broadcast_countries') or []))]
        if subset:
            subset.sort(key=lambda row:(not bool(row.get('poster')), -((row.get('rating') or {}).get('value',0)), -(row.get('year') or 0),row['id']))
            collections.append(dict(type='',country=country,title=f'Cerita dari {name}',items=[compact(row) for row in subset[:6]]))
    # Pick latest updated titles with art across movie, tv, anime for hero slider (max 10)
    by_kind = {}
    for kind in TYPES:
        candidates = [row for row in records if row['type'] == kind and (row.get('backdrop') or row.get('poster'))]
        candidates.sort(key=lambda r: (
            r.get('updated_at') or '',
            (r.get('rating') or {}).get('value') or 0,
            r.get('year') or 0,
            r['id']
        ), reverse=True)
        by_kind[kind] = candidates[:4]

    heroes = []
    for i in range(4):
        for kind in ('movie', 'tv', 'anime'):
            if i < len(by_kind.get(kind, [])) and len(heroes) < 10:
                heroes.append(by_kind[kind][i])

    if not heroes:
        heroes = [max(records, key=lambda r: (bool(r.get('backdrop')), (r.get('rating') or {}).get('value', 0)))]

    hero_items = []
    for r in heroes:
        hero_items.append({
            'id': r['id'],
            'type': r['type'],
            'title': r['title'],
            'year': r.get('year'),
            'rating': r.get('rating'),
            'genres': r.get('genres') or [],
            'runtime_minutes': r.get('runtime_minutes'),
            'overview': r.get('overview') or '',
            'backdrop': r.get('backdrop'),
            'poster': r.get('poster'),
            'updated_at': r.get('updated_at')
        })

    write(target/'featured.json', dict(
        hero=heroes[0]['id'],
        heroes=[r['id'] for r in heroes],
        hero_items=hero_items,
        collections=collections
    ))
    if 'tvmaze' in providers:
        (target/'LICENSE.txt').write_text('TVmaze metadata and MovieHub adaptations: CC BY-SA 4.0\nhttps://creativecommons.org/licenses/by-sa/4.0/\nSource: https://www.tvmaze.com/ and per-record source URLs.\nChanges: normalized schema, plain-text summaries, curated selection and anime classification.\nArtwork URLs reference the TVmaze CDN; no artwork is mirrored here.\nNo endorsement by TVmaze is implied.\n')
    if 'wikidata' in providers:
        manifest['attributions'].append(dict(name='Wikidata',url='https://www.wikidata.org/',license='CC0 1.0',license_url='https://creativecommons.org/publicdomain/zero/1.0/',changes='Film metadata selected by country of origin and normalized.'))
        with (target/'LICENSE.txt').open('a') as license_file:
            license_file.write('\nWikidata film metadata: CC0 1.0. https://creativecommons.org/publicdomain/zero/1.0/\nSources: per-record Wikidata URLs. No Commons artwork is imported.\n')
    if 'rottentomatoes' in providers:
        manifest['attributions'].append(dict(name='Rotten Tomatoes',url='https://www.rottentomatoes.com/',license='Proprietary / Promotional',license_url='https://www.rottentomatoes.com/help_faq',changes='Scores and browse metadata aggregated.'))
        with (target/'LICENSE.txt').open('a') as license_file:
            license_file.write('\nRotten Tomatoes metadata and scores: Proprietary / Promotional. https://www.rottentomatoes.com/\n')
    write(target/'manifest.json', manifest)
    check_output(target)
    return manifest


def check_output(target):
    manifest = json.loads((target/'manifest.json').read_text())
    rows = []
    for path in manifest['files'].values():
        json.loads((target/Path(path).relative_to('data')).read_text())
    for kind, chunks in manifest['chunks'].items():
        count = 0
        for chunk in chunks:
            items = json.loads((target/Path(chunk['path']).relative_to('data')).read_text())
            if len(items) != chunk['count'] or items[0]['id'] != chunk['first_id'] or items[-1]['id'] != chunk['last_id'] or any(row['type'] != kind for row in items):
                raise ValueError('Chunk consistency failure')
            rows.extend(items); count += len(items)
        if count != manifest['counts'][kind]:
            raise ValueError('Manifest count mismatch')
    validate(rows)
    index = json.loads((target/'search-index.json').read_text())
    if not isinstance(index,dict) or index.get('schema_version') != 2:
        raise ValueError('Search descriptor mismatch')
    indexed = []
    for shard in index['shards']:
        batch = json.loads((target/Path(shard['path']).relative_to('data')).read_text())
        if len(batch) != shard['count']:
            raise ValueError('Search shard count mismatch')
        indexed.extend(batch)
    if sorted(indexed,key=lambda r:r['id']) != [compact(row) for row in sorted(rows,key=lambda r:r['id'])]:
        raise ValueError('Search index mismatch')
    featured = json.loads((target/'featured.json').read_text())
    known = {row['id'] for row in rows}
    if featured['hero'] not in known or any(row['id'] not in known for c in featured['collections'] for row in c['items']) or any(hid not in known for hid in featured.get('heroes', [])):
        raise ValueError('Featured IDs do not resolve')


def get_registered_sources():
    sources = {}
    sources_dir = UPDATER_DIR / 'sources'
    import importlib
    for file in sorted(sources_dir.glob('*.py')):
        if file.name.startswith('_'):
            continue
        name = file.stem
        try:
            mod = importlib.import_module(f'sources.{name}')
            if hasattr(mod, 'fetch_all') or hasattr(mod, 'fetch'):
                def make_loader(m, source_name):
                    def loader(cache_dir, config, scope):
                        c_dir = cache_dir / source_name
                        if hasattr(m, 'fetch_all') and scope == 'full':
                            try:
                                return m.fetch_all(config, c_dir)
                            except TypeError:
                                return m.fetch_all(c_dir)
                        elif hasattr(m, 'fetch'):
                            try:
                                return m.fetch(c_dir)
                            except TypeError:
                                try:
                                    return m.fetch(config, c_dir)
                                except TypeError:
                                    return m.fetch(config)
                        raise ValueError(f'Source {source_name} has no recognized fetch function')
                    return loader
                sources[name] = make_loader(mod, name)
        except Exception as e:
            print(f'Warning: failed to load source {name}: {e}', flush=True)
    return sources


def main():
    registered_sources = get_registered_sources()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', default='all', help='Source(s) to fetch (tvmaze, wikidata, rottentomatoes, all, fixture). Default is "all".')
    parser.add_argument('--scope', choices=('curated','full'), default='full')
    parser.add_argument('--cache-dir',type=Path,default=ROOT/'.cache/updater')
    parser.add_argument('--config', type=Path, default=Path(__file__).parent/'config/tvmaze.json')
    parser.add_argument('--input', type=Path, help='Canonical fixture input (requires --source fixture)')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    if args.input and args.source != 'fixture':
        parser.error('--input requires --source fixture')
    if args.source == 'fixture':
        records = deduplicate(json.loads((args.input or Path(__file__).with_name('fixtures.json')).read_text()))
    else:
        preferred_order = ['tvmaze', 'wikidata', 'rottentomatoes']
        if args.source == 'all':
            active_sources = sorted(registered_sources.keys(), key=lambda s: preferred_order.index(s) if s in preferred_order else 99)
        else:
            requested = [s.strip() for s in args.source.split(',') if s.strip()]
            for s in requested:
                if s not in registered_sources:
                    parser.error(f'Unknown source "{s}". Available sources: {", ".join(registered_sources.keys())}')
            active_sources = requested

        records = []
        if set(active_sources) != set(registered_sources.keys()):
            for path in (ROOT/'data').glob('*/*.json'):
                if path.parent.name in TYPES:
                    records.extend(json.loads(path.read_text()))

        config = json.loads(args.config.read_text()) if args.config.exists() else {'shows': []}

        for src_name in active_sources:
            loader = registered_sources[src_name]
            fetched = loader(args.cache_dir, config, args.scope)
            if src_name == 'tvmaze':
                for path in (ROOT/'data').glob('*/*.json'):
                    if path.parent.name not in TYPES: continue
                    for previous in json.loads(path.read_text()):
                        if previous['id'] in {f"{item['type']}-tvmaze-{item['id']}" for item in config.get('shows', [])}:
                            for i,current in enumerate(fetched):
                                if current['id']==previous['id'] and current['updated_at']==previous['updated_at']:
                                    previous['broadcast_countries']=current.get('broadcast_countries',[])
                                    fetched[i]=previous;break
            records.extend(fetched)

        records, conflicts = resolve_external_conflicts(deduplicate(merge_records(records)))
        args.cache_dir.mkdir(parents=True,exist_ok=True)
        write(args.cache_dir/'identity-conflicts.json',conflicts)
        print(f'Ambiguous secondary identifiers omitted: {len(conflicts)}')
    # A complete staging directory is checked before the public dataset is touched.
    with tempfile.TemporaryDirectory(prefix='.catalog-stage-', dir=ROOT) as temp:
        staged = Path(temp)/'data'
        manifest = generate(records, staged)
        sizes = [path.stat().st_size for path in staged.rglob('*.json')]
        if not args.dry_run:
            public, backup = ROOT/'data', ROOT/'.data-backup'
            if backup.exists():
                raise ValueError('Previous backup exists; inspect it before continuing')
            had_public = public.exists()
            if had_public:
                public.rename(backup)
            try:
                staged.rename(public)
            except BaseException:
                if had_public: backup.rename(public)
                raise
            if had_public: shutil.rmtree(backup)
        print('MovieHub update ' + ('validated (dry-run)' if args.dry_run else 'complete'))
        print(json.dumps(manifest['counts']))
        print(f'Dataset: {manifest["dataset_version"]}; JSON total: {sum(sizes):,} bytes; largest file: {max(sizes):,} bytes')
        print('Providers: ' + ', '.join(manifest['providers']))

if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, TypeError, OSError) as error:
        raise SystemExit(f'Update failed; previous dataset retained: {error}')
