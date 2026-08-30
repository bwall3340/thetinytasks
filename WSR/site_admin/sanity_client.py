"""
Sanity HTTP client for site images.

Uploads go to the Sanity asset store; each slot is recorded as a `siteImage`
document with a deterministic _id (siteImage.<slot>) so an upload is always an
upsert and a slot can never end up with duplicate documents.

Reads are cached in-process with a short TTL.  A Sanity outage must never take
the marketing site down, so every read failure falls back to the last good
cache and, beyond that, to the committed files on disk.
"""
import logging
import os
import threading
import time
from datetime import datetime, timezone

import requests

logger = logging.getLogger(__name__)

API_VERSION = os.environ.get('SANITY_API_VERSION', '2024-01-01')
PROJECT_ID = os.environ.get('SANITY_PROJECT_ID', 'mcp0g14m')
DATASET = os.environ.get('SANITY_DATASET', 'production')

DOC_TYPE = 'siteImage'
DOC_ID_PREFIX = 'siteImage.'

CACHE_TTL_SECONDS = 300
# The app runs with a single gunicorn worker, so a slow read on a cold
# cache would stall every other request. Reads fail fast; writes may wait.
READ_TIMEOUT = 5
WRITE_TIMEOUT = 60

# Transform applied to every delivered image: cap the width, let Sanity pick
# the best modern format (WebP/AVIF) for the requesting browser.
DELIVERY_PARAMS = 'auto=format&q=80&w=2000&fit=max'


class SanityError(RuntimeError):
    """Raised when a Sanity write fails — surfaced to the admin UI verbatim."""


def api_token():
    return os.environ.get('SANITY_API_TOKEN', '')


def is_configured():
    """True when writes are possible. Reads work without a token."""
    return bool(api_token() and PROJECT_ID and DATASET)


def _write_base():
    return f'https://{PROJECT_ID}.api.sanity.io/v{API_VERSION}'


def _read_base():
    # apicdn is edge-cached; used for reads only, never for read-after-write.
    return f'https://{PROJECT_ID}.apicdn.sanity.io/v{API_VERSION}'


def _auth_headers():
    token = api_token()
    if not token:
        raise SanityError(
            'SANITY_API_TOKEN is not set — add an Editor token in Railway to enable uploads.'
        )
    return {'Authorization': f'Bearer {token}'}


def doc_id(slot_id):
    return DOC_ID_PREFIX + slot_id


# ── Cache ─────────────────────────────────────────────────────────────────────

_cache = {'data': {}, 'fetched_at': 0.0}
_cache_lock = threading.Lock()


def invalidate_cache():
    with _cache_lock:
        _cache['fetched_at'] = 0.0


# ── Reads ─────────────────────────────────────────────────────────────────────

_GROQ = (
    '*[_type=="%s"]{'
    'slot,'
    '"url":image.asset->url,'
    '"originalFilename":image.asset->originalFilename,'
    '"size":image.asset->size,'
    '"width":image.asset->metadata.dimensions.width,'
    '"height":image.asset->metadata.dimensions.height,'
    'alt,updatedAt}' % DOC_TYPE
)


def _fetch_slot_map():
    url = f'{_read_base()}/data/query/{DATASET}'
    headers = _auth_headers() if api_token() else {}
    resp = requests.get(url, params={'query': _GROQ}, headers=headers,
                        timeout=READ_TIMEOUT)
    resp.raise_for_status()
    rows = resp.json().get('result') or []

    out = {}
    for row in rows:
        slot = row.get('slot')
        if not slot or not row.get('url'):
            continue
        out[slot] = {
            'url': row['url'],
            'delivery_url': row['url'] + '?' + DELIVERY_PARAMS,
            'alt': row.get('alt') or '',
            'width': row.get('width'),
            'height': row.get('height'),
            'size': row.get('size'),
            'original_filename': row.get('originalFilename') or '',
            'updated_at': row.get('updatedAt') or '',
        }
    return out


def slot_map(force=False):
    """
    {slot_id: {...image info...}} for every slot with an image in Sanity.

    Never raises: on failure it returns the last good cache (or {}), so the
    public pages fall back to their committed images instead of erroring.
    """
    with _cache_lock:
        fresh = (time.time() - _cache['fetched_at']) < CACHE_TTL_SECONDS
        if fresh and not force:
            return _cache['data']

    try:
        data = _fetch_slot_map()
        with _cache_lock:
            _cache['data'] = data
            _cache['fetched_at'] = time.time()
        return data
    except Exception as e:
        logger.warning('Sanity slot fetch failed (%s) — using cached/fallback images', e)
        with _cache_lock:
            # Back off so a hard outage doesn't retry on every single request.
            _cache['fetched_at'] = time.time() - (CACHE_TTL_SECONDS - 30)
            return _cache['data']


# ── Writes ────────────────────────────────────────────────────────────────────

def upload_asset(file_bytes, filename, content_type):
    """Upload raw image bytes to the Sanity asset store. Returns the asset doc."""
    url = f'{_write_base()}/assets/images/{DATASET}'
    headers = _auth_headers()
    headers['Content-Type'] = content_type
    try:
        resp = requests.post(url, params={'filename': filename}, headers=headers,
                             data=file_bytes, timeout=WRITE_TIMEOUT)
    except requests.RequestException as e:
        raise SanityError(f'Could not reach Sanity: {e}') from e

    if resp.status_code >= 400:
        raise SanityError(f'Sanity rejected the upload ({resp.status_code}): {resp.text[:300]}')

    doc = (resp.json() or {}).get('document') or {}
    if not doc.get('_id'):
        raise SanityError('Sanity returned no asset id for the upload.')
    return doc


def _mutate(mutations):
    url = f'{_write_base()}/data/mutate/{DATASET}'
    headers = _auth_headers()
    headers['Content-Type'] = 'application/json'
    try:
        resp = requests.post(url, headers=headers, json={'mutations': mutations},
                             timeout=WRITE_TIMEOUT)
    except requests.RequestException as e:
        raise SanityError(f'Could not reach Sanity: {e}') from e

    if resp.status_code >= 400:
        raise SanityError(f'Sanity rejected the change ({resp.status_code}): {resp.text[:300]}')
    return resp.json()


def set_slot_image(slot_id, asset_id, alt=''):
    """Point a slot at an uploaded asset, replacing whatever was there."""
    _mutate([{
        'createOrReplace': {
            '_id': doc_id(slot_id),
            '_type': DOC_TYPE,
            'slot': slot_id,
            'alt': alt or '',
            'updatedAt': datetime.now(timezone.utc).isoformat(),
            'image': {
                '_type': 'image',
                'asset': {'_type': 'reference', '_ref': asset_id},
            },
        }
    }])
    invalidate_cache()


def clear_slot(slot_id):
    """Remove a slot's document so it reverts to the committed fallback image."""
    _mutate([{'delete': {'id': doc_id(slot_id)}}])
    invalidate_cache()
