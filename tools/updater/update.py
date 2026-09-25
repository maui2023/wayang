#!/usr/bin/env python3
"""Generate validated static catalogs from TVmaze or local fixtures."""
import argparse
import hashlib
import json
import re
import shutil
import tempfile
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
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
    if re.search(r'(?i)(api[_-]?key|access[_-]?token|password|secret)\s*["\s]*:', json.dumps(records)):
        raise ValueError('Possible credential field in catalog')


def deduplicate(records):
    """Collapse exact repeats only. Conflicting identities must be reviewed."""
    by_id = {}
    for item in records:
        previous = by_id.get(item['id'])
        if previous is not None and previous != item:
            raise ValueError('Conflicting records with same ID')
        by_id[item['id']] = item
    return sorted(by_id.values(), key=lambda item: item['id'])


def compact(item):
    row = {key: item.get(key) for key in ('id','type','title','original_title','aliases','year','release_date','genres','languages','popularity')}
    row['poster'] = (item.get('poster') or {}).get('url')
    row['rating'] = (item.get('rating') or {}).get('value')
    return row


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + '\n')


def generate(records, target):
    validate(records)
    digest = hashlib.sha256(json.dumps(records, sort_keys=True).encode()).hexdigest()[:16]
    manifest = dict(schema_version=1, dataset_version=digest,
                    generated_at=max(row['updated_at'] for row in records), counts={}, chunks={},
                    files={key:f'data/{filename}.json' for key,filename in [('genres','genres'),('featured','featured'),('search_index','search-index')]})
    providers = sorted({source['provider'] for row in records for source in row['sources']})
    manifest['is_demo'] = providers == ['original-fixture']
    manifest['providers'] = providers
    manifest['attributions'] = ([dict(name='TVmaze', url='https://www.tvmaze.com/', license='CC BY-SA 4.0', license_url='https://creativecommons.org/licenses/by-sa/4.0/', changes='Metadata normalized; summaries converted to plain text; selected anime classified by MovieHub.')] if 'tvmaze' in providers else [])
    collections = []
    for kind in TYPES:
        subset = [row for row in records if row['type'] == kind]
        manifest['counts'][kind] = len(subset)
        manifest['chunks'][kind] = []
        for offset in range(0, len(subset), CHUNK_SIZE):
            chunk = subset[offset:offset+CHUNK_SIZE]
            path = f'{kind}/{offset//CHUNK_SIZE+1:04}.json'
            write(target/path, chunk)
            manifest['chunks'][kind].append(dict(path=f'data/{path}',count=len(chunk),ids=[row['id'] for row in chunk],bytes=(target/path).stat().st_size))
        if not subset:
            continue
        collections.append(dict(type=kind,title={'movie':'Filem pilihan','tv':'Siri untuk diikuti','anime':'Dunia animasi'}[kind],items=[compact(row) for row in sorted(subset,key=lambda r: -((r.get('rating') or {}).get('value',0)))[:6]]))
    write(target/'search-index.json', [compact(row) for row in records])
    write(target/'genres.json', sorted({genre for row in records for genre in row.get('genres', [])}))
    write(target/'featured.json', dict(hero=max(records,key=lambda r:(bool(r.get('backdrop')), (r.get('rating') or {}).get('value',0)))['id'],collections=collections))
    if 'tvmaze' in providers:
        (target/'LICENSE.txt').write_text('TVmaze metadata and MovieHub adaptations: CC BY-SA 4.0\nhttps://creativecommons.org/licenses/by-sa/4.0/\nSource: https://www.tvmaze.com/ and per-record source URLs.\nChanges: normalized schema, plain-text summaries, curated selection and anime classification.\nArtwork URLs reference the TVmaze CDN; no artwork is mirrored here.\nNo endorsement by TVmaze is implied.\n')
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
            if len(items) != chunk['count'] or [row['id'] for row in items] != chunk['ids'] or any(row['type'] != kind for row in items):
                raise ValueError('Chunk consistency failure')
            rows.extend(items); count += len(items)
        if count != manifest['counts'][kind]:
            raise ValueError('Manifest count mismatch')
    validate(rows)
    index = json.loads((target/'search-index.json').read_text())
    if index != [compact(row) for row in sorted(rows,key=lambda r:r['id'])]:
        raise ValueError('Search index mismatch')
    featured = json.loads((target/'featured.json').read_text())
    known = {row['id'] for row in rows}
    if featured['hero'] not in known or any(row['id'] not in known for c in featured['collections'] for row in c['items']):
        raise ValueError('Featured IDs do not resolve')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', choices=('tvmaze','fixture'), default='tvmaze')
    parser.add_argument('--config', type=Path, default=Path(__file__).parent/'config/tvmaze.json')
    parser.add_argument('--input', type=Path, help='Canonical fixture input (requires --source fixture)')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    if args.input and args.source != 'fixture':
        parser.error('--input requires --source fixture')
    if args.source == 'tvmaze':
        from sources.tvmaze import fetch
        records = deduplicate(fetch(json.loads(args.config.read_text())))
    else:
        records = deduplicate(json.loads((args.input or Path(__file__).with_name('fixtures.json')).read_text()))
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
