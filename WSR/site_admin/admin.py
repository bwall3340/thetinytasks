"""
Site admin — drag-and-drop image management for the public marketing pages.

Route:  /admin
Auth:   shared Google OAuth (common.auth), same as every other module admin.
Store:  Sanity CDN (see sanity_client), so uploads survive Railway deploys.
"""
import logging

from flask import Blueprint, jsonify, render_template, request

from common.auth import current_admin, require_admin
from . import sanity_client, slots

logger = logging.getLogger(__name__)

site_admin_bp = Blueprint('site_admin', __name__, url_prefix='/admin')

# Magic-byte signatures — a client-supplied Content-Type is not trustworthy.
_SIGNATURES = (
    (b'\xff\xd8\xff', 'image/jpeg'),
    (b'\x89PNG\r\n\x1a\n', 'image/png'),
)


def _sniff_type(data):
    """Detect the real image type from the file header, or None."""
    for prefix, mime in _SIGNATURES:
        if data.startswith(prefix):
            return mime
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        return 'image/webp'
    return None


@site_admin_bp.route('/')
@require_admin
def dashboard():
    """Image manager — every managed slot, with its current image."""
    current = sanity_client.slot_map(force=True)
    return render_template(
        'site_admin/dashboard.html',
        admin_user=current_admin(),
        grouped_slots=slots.grouped(),
        current=current,
        filled_count=sum(1 for s in slots.SLOTS if s in current),
        total_count=len(slots.SLOTS),
        sanity_ready=sanity_client.is_configured(),
        max_mb=slots.MAX_UPLOAD_BYTES // (1024 * 1024),
    )


@site_admin_bp.route('/images/<slot_id>', methods=['POST'])
@require_admin
def upload_image(slot_id):
    """Upload (or replace) the image for one slot."""
    slot = slots.get(slot_id)
    if slot is None:
        return jsonify({'success': False, 'error': f'Unknown image slot "{slot_id}".'}), 404

    file = request.files.get('file')
    if file is None or not file.filename:
        return jsonify({'success': False, 'error': 'No file was included in the upload.'}), 400

    data = file.read()
    if not data:
        return jsonify({'success': False, 'error': 'That file is empty.'}), 400

    if len(data) > slots.MAX_UPLOAD_BYTES:
        limit = slots.MAX_UPLOAD_BYTES // (1024 * 1024)
        actual = len(data) / (1024 * 1024)
        return jsonify({
            'success': False,
            'error': f'That image is {actual:.1f}MB — the limit is {limit}MB.',
        }), 400

    real_type = _sniff_type(data)
    if real_type not in slots.ALLOWED_TYPES:
        return jsonify({
            'success': False,
            'error': 'Only JPEG, PNG and WebP images are accepted.',
        }), 400

    ext = slots.ALLOWED_TYPES[real_type]
    alt = (request.form.get('alt') or slot.label).strip()

    try:
        asset = sanity_client.upload_asset(data, f'{slot.id}.{ext}', real_type)
        sanity_client.set_slot_image(slot.id, asset['_id'], alt=alt)
    except sanity_client.SanityError as e:
        logger.error('Upload failed for slot %s: %s', slot.id, e)
        return jsonify({'success': False, 'error': str(e)}), 502
    except Exception as e:
        logger.exception('Unexpected upload error for slot %s', slot.id)
        return jsonify({'success': False, 'error': f'Unexpected error: {e}'}), 500

    info = sanity_client.slot_map(force=True).get(slot.id, {})
    return jsonify({
        'success': True,
        'slot': slot.id,
        'preview_url': info.get('delivery_url') or asset.get('url', ''),
        'width': info.get('width'),
        'height': info.get('height'),
        'size': info.get('size'),
        'message': f'{slot.label} updated.',
    })


@site_admin_bp.route('/images/<slot_id>/reset', methods=['POST'])
@require_admin
def reset_image(slot_id):
    """Drop the Sanity image so the slot reverts to its committed fallback."""
    slot = slots.get(slot_id)
    if slot is None:
        return jsonify({'success': False, 'error': f'Unknown image slot "{slot_id}".'}), 404

    try:
        sanity_client.clear_slot(slot.id)
    except sanity_client.SanityError as e:
        logger.error('Reset failed for slot %s: %s', slot.id, e)
        return jsonify({'success': False, 'error': str(e)}), 502

    return jsonify({
        'success': True,
        'slot': slot.id,
        'message': f'{slot.label} reverted to the built-in image.',
    })


@site_admin_bp.route('/images/refresh', methods=['POST'])
@require_admin
def refresh_cache():
    """Force a re-read from Sanity — useful after editing in Sanity Studio."""
    current = sanity_client.slot_map(force=True)
    return jsonify({'success': True, 'count': len(current)})
