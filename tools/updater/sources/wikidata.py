"""CC0 film metadata for MY/ID/TH, queried by declared country of origin."""
import json
import socket
import time
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

socket.setdefaulttimeout(30)

COUNTRIES = {'MY':'Q833','ID':'Q252','TH':'Q869'}
ENDPOINT = 'https://query.wikidata.org/sparql'
LICENSE = 'https://creativecommons.org/publicdomain/zero/1.0/'


def query_country(code):
    return 'SELECT DISTINCT ?item WHERE { hint:Query hint:optimizer "None". ?item wdt:P495 wd:%s. ?item wdt:P31 ?class. ?class wdt:P279* wd:Q11424. }' % COUNTRIES[code]


def request(query):
    url = ENDPOINT + '?' + urlencode({'query':query,'format':'json'})
    for attempt in range(4):
        try:
            req = Request(url,headers={'User-Agent':'MovieHub-catalog/1.0 (offline metadata updater)','Accept':'application/sparql-results+json'})
            with urlopen(req,timeout=60) as response:
                return json.load(response)['results']['bindings']
        except (HTTPError,URLError,TimeoutError,OSError) as error:
            print(f'Wikidata retry {attempt+1}: {type(error).__name__} {getattr(error, "code", "timeout/network")}',flush=True)
            if isinstance(error,HTTPError) and error.code not in (429,500,502,503,504):
                raise ValueError(f'Wikidata HTTP {error.code}') from None
            if attempt == 3: raise ValueError('Wikidata query failed after four attempts; cached pages retained') from None
            time.sleep(max(60,int(error.headers.get('Retry-After','60'))) if isinstance(error,HTTPError) and error.code==429 and error.headers.get('Retry-After','60').isdigit() else min(30,5*(attempt+1)))



# Entity API ingestion keeps date precision and avoids costly SPARQL enrichment joins.
def values(entity, prop):
    claims=[claim for claim in entity.get('claims',{}).get(prop,[]) if claim.get('rank')!='deprecated' and claim.get('mainsnak',{}).get('snaktype')=='value']
    preferred=[claim for claim in claims if claim.get('rank')=='preferred']
    return [claim['mainsnak']['datavalue']['value'] for claim in preferred or claims]


def entity_label(entity):
    labels=entity.get('labels',{})
    return next((labels[lang]['value'] for lang in ('en','ms','id','th') if lang in labels),entity['id'])


def normalize_entity(entity, references, matched_countries):
    qid=entity['id']
    originals=[v['text'] for v in values(entity,'P1476')]
    aliases=sorted(set(originals+[alias['value'] for group in entity.get('aliases',{}).values() for alias in group]+[label['value'] for label in entity.get('labels',{}).values()]))
    dates=values(entity,'P577')
    years=sorted(int(v['time'][1:5]) for v in dates if v.get('precision',0)>=9 and v['time'].startswith('+') and int(v['time'][1:5])>0)
    full_dates=[]
    for value in dates:
        if value.get('precision',0)>=11:
            candidate=value['time'].lstrip('+')[:10]
            try: date.fromisoformat(candidate)
            except ValueError: continue
            full_dates.append(candidate)
    def codes(prop,code_prop):
        return sorted({code for value in values(entity,prop) for code in values(references.get(value['id'],{}),code_prop) if isinstance(code,str)})
    descriptions=entity.get('descriptions',{})
    summary=next((descriptions[lang]['value'] for lang in ('en','ms','id','th') if lang in descriptions),'')
    imdb=values(entity,'P345')
    external={'wikidata':qid}
    if len(set(imdb))==1: external['imdb']=imdb[0]
    genres=sorted({entity_label(references[v['id']]).lower() for v in values(entity,'P136') if v['id'] in references and references[v['id']].get('labels')})
    return dict(schema_version=1,id=f'movie-wikidata-{qid.lower()}',type='movie',title=entity_label(entity),original_title=originals[0] if originals else None,
        aliases=aliases,year=years[0] if years else None,release_date=min(full_dates) if full_dates else None,
        overview=summary,genres=genres,poster=None,backdrop=None,rating=None,popularity=None,runtime_minutes=None,series=None,status=None,
        countries=sorted(set(codes('P495','P297')+matched_countries)),broadcast_countries=[],languages=codes('P364','P218'),external_ids=external,trailer=None,
        sources=[{'provider':'wikidata','provider_id':qid,'url':f'https://www.wikidata.org/wiki/{qid}','license':'CC0 1.0','license_url':LICENSE}],updated_at=entity['modified'])


def fetch(cache_dir):
    import hashlib
    cache_dir=Path(cache_dir);cache_dir.mkdir(parents=True,exist_ok=True)
    def cached(path,loader):
        if path.exists() and time.time()-path.stat().st_mtime<86400:
            return json.loads(path.read_text())
        payload = loader()
        import os
        tmp = path.with_name(f'{path.stem}.{os.getpid()}.tmp')
        try:
            tmp.write_text(json.dumps(payload, ensure_ascii=False))
            tmp.replace(path)
        except Exception:
            if tmp.exists():
                tmp.unlink(missing_ok=True)
            if not path.exists():
                raise
        return payload
    matched={}
    for code in COUNTRIES:
        payload=cached(cache_dir/f'{code}-identities.json',lambda:{'rows':request(query_country(code))})
        ids={row['item']['value'].rsplit('/',1)[-1] for row in payload['rows']}
        print(f'Wikidata {code}: {len(ids)} film identities',flush=True)
        for qid in ids: matched.setdefault(qid,[]).append(code)
    def entities(ids):
        result = {}
        for offset in range(0, len(ids), 50):
            batch = ids[offset:offset+50]
            key = hashlib.sha256('|'.join(batch).encode()).hexdigest()[:16]
            def load():
                url = 'https://www.wikidata.org/w/api.php?' + urlencode({
                    'action': 'wbgetentities',
                    'ids': '|'.join(batch),
                    'props': 'labels|descriptions|aliases|claims|info',
                    'languages': 'en|ms|id|th',
                    'format': 'json',
                    'maxlag': 5
                })
                for attempt in range(5):
                    try:
                        req = Request(url, headers={'User-Agent': 'MovieHub/1.0 (https://github.com/maui2023/wayang; bot@moviehub.local)'})
                        with urlopen(req, timeout=30) as response:
                            data = json.load(response)
                        if data.get('error'):
                            err_code = data['error'].get('code', 'unknown')
                            if err_code == 'maxlag':
                                time.sleep(5 * (attempt + 1))
                                continue
                            raise ValueError('Wikidata entity API: ' + err_code)
                        if not set(batch).issubset(data.get('entities', {})):
                            raise ValueError('Incomplete Wikidata entity batch')
                        time.sleep(0.4)
                        return data['entities']
                    except (HTTPError, URLError, TimeoutError, OSError, ValueError):
                        if attempt == 4:
                            raise
                        time.sleep(5 * (attempt + 1))
            result.update(cached(cache_dir/f'entities-{key}.json', load))
            if offset % 500 == 0:
                print(f'Wikidata entities: {min(offset+50, len(ids))}/{len(ids)}', flush=True)
        return result
    films = entities(sorted(matched))
    films = {qid: entity for qid, entity in films.items() if 'missing' not in entity}
    ref_ids = sorted({value['id'] for film in films.values() for prop in ('P136','P495','P364') for value in values(film,prop) if isinstance(value,dict) and 'id' in value})
    references = entities(ref_ids)
    return [normalize_entity(films[qid], references, matched[qid]) for qid in sorted(films)]
