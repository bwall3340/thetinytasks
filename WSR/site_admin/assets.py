"""
Public asset resolution for /assets/<filename>.

Resolution order for a managed slot:
  1. Sanity CDN image, if one has been uploaded  -> 302 redirect
  2. The committed fallback file on disk         -> served directly
  3. A transparent 1x1 pixel                     -> lets the CSS placeholder
                                                    show through, with no
                                                    broken-image icon

Keeping the fallback chain here means index.html, styles.css and about.html
reference plain /assets/<name> paths and never need to know where an image
actually lives.
"""
import base64
import os

from flask import Response, redirect, send_from_directory

from . import slots
from . import sanity_client

# 1x1 fully transparent PNG — the "nothing uploaded yet" response.
_TRANSPARENT_PNG = base64.b64decode(
    b'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk'
    b'YPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=='
)


def _transparent():
    resp = Response(_TRANSPARENT_PNG, mimetype='image/png')
    # Short cache: an upload should show up quickly once a slot is filled.
    resp.headers['Cache-Control'] = 'public, max-age=60'
    return resp


def resolve(assets_dir, filename):
    """Return a Flask response for one /assets/<filename> request."""
    slot = slots.by_filename(filename)

    if slot is not None:
        info = sanity_client.slot_map().get(slot.id)
        if info and info.get('delivery_url'):
            # 302 (not 301) so removing the Sanity image reverts cleanly
            # instead of being pinned in browser caches forever.
            return redirect(info['delivery_url'], code=302)

    if os.path.isfile(os.path.join(assets_dir, filename)):
        return send_from_directory(assets_dir, filename)

    if slot is not None:
        return _transparent()

    # Unmanaged filename with no file on disk — a genuine 404.
    return send_from_directory(assets_dir, filename)
