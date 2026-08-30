"""
Tests for the site admin image manager and the shared admin auth.

These build a minimal Flask app rather than importing WSR/app.py, so they run
without the OpenCV / vectorizer stack.

Run with:
    cd WSR
    pytest tests/test_site_admin.py -v
"""
import io
import os
import sys

import pytest
from flask import Flask

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from common.auth import SESSION_KEY, auth_bp, init_oauth          # noqa: E402
from site_admin import sanity_client, slots                        # noqa: E402
from site_admin.admin import site_admin_bp                         # noqa: E402
from site_admin.assets import resolve as resolve_asset             # noqa: E402

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
ASSETS_DIR = os.path.join(REPO_ROOT, 'assets')
TEMPLATES = os.path.join(os.path.dirname(__file__), '..', 'templates')

# The real implementation, captured before any fixture stubs it out.
REAL_SLOT_MAP = sanity_client.slot_map

PNG_BYTES = b'\x89PNG\r\n\x1a\n' + b'\x00' * 200
JPEG_BYTES = b'\xff\xd8\xff' + b'\x00' * 200


@pytest.fixture
def site_app(monkeypatch):
    monkeypatch.setenv('ADMIN_EMAILS', 'owner@example.com')
    # Never touch the network in tests.
    monkeypatch.setattr(sanity_client, 'slot_map', lambda force=False: {})

    app = Flask(__name__, template_folder=os.path.abspath(TEMPLATES))
    app.config.update(SECRET_KEY='test', TESTING=True,
                      GOOGLE_CLIENT_ID='x', GOOGLE_CLIENT_SECRET='y',
                      MAX_CONTENT_LENGTH=16 * 1024 * 1024)
    init_oauth(app)
    app.register_blueprint(auth_bp)
    app.register_blueprint(site_admin_bp)

    @app.route('/assets/<path:filename>')
    def assets(filename):
        return resolve_asset(ASSETS_DIR, filename)

    return app


@pytest.fixture
def client(site_app):
    return site_app.test_client()


@pytest.fixture
def admin_client(client):
    with client.session_transaction() as sess:
        sess[SESSION_KEY] = {'email': 'owner@example.com', 'name': 'Owner'}
    return client


# ── Auth ──────────────────────────────────────────────────────────────────────

class TestAdminAuth:
    def test_dashboard_requires_login(self, client):
        r = client.get('/admin/')
        assert r.status_code == 302
        assert '/admin/login' in r.headers['Location']

    @pytest.mark.parametrize('path', [
        '/admin/images/hero',
        '/admin/images/hero/reset',
        '/admin/images/refresh',
    ])
    def test_write_endpoints_require_login(self, client, path):
        assert client.post(path).status_code == 302

    def test_login_page_renders(self, client):
        r = client.get('/admin/login')
        assert r.status_code == 200
        assert b'Continue with Google' in r.data

    def test_login_page_is_noindex(self, client):
        assert b'noindex' in client.get('/admin/login').data

    def test_external_next_is_rejected(self, admin_client):
        r = admin_client.get('/admin/login?next=https://evil.example.com/x')
        assert 'evil.example.com' not in r.headers['Location']

    def test_internal_next_is_honoured(self, admin_client):
        r = admin_client.get('/admin/login?next=/market/admin/dashboard')
        assert '/market/admin/dashboard' in r.headers['Location']

    def test_logout_clears_session(self, admin_client):
        admin_client.get('/admin/logout')
        assert admin_client.get('/admin/').status_code == 302


# ── Dashboard ─────────────────────────────────────────────────────────────────

class TestDashboard:
    def test_renders_for_admin(self, admin_client):
        assert admin_client.get('/admin/').status_code == 200

    def test_every_registered_slot_appears(self, admin_client):
        body = admin_client.get('/admin/').data.decode()
        for slot_id in slots.SLOTS:
            assert f'data-slot="{slot_id}"' in body

    def test_warns_when_uploads_are_disabled(self, admin_client, monkeypatch):
        monkeypatch.delenv('SANITY_API_TOKEN', raising=False)
        assert b'Uploads are disabled' in admin_client.get('/admin/').data


# ── Asset resolution ──────────────────────────────────────────────────────────

class TestAssetResolution:
    def test_committed_file_is_served(self, client):
        r = client.get('/assets/hero.jpg')
        assert r.status_code == 200
        assert r.content_type.startswith('image/jpeg')

    def test_empty_slot_returns_transparent_pixel(self, client):
        """A slot with no upload and no committed file must not 404 — the CSS
        placeholder should show through instead of a broken-image icon."""
        r = client.get('/assets/portrait.jpg')
        assert r.status_code == 200
        assert r.content_type == 'image/png'
        assert len(r.data) < 200

    def test_unmanaged_missing_file_still_404s(self, client):
        assert client.get('/assets/no-such-image.jpg').status_code == 404

    def test_uploaded_slot_redirects_to_cdn(self, client, monkeypatch):
        url = 'https://cdn.sanity.io/images/p/production/abc-2400x1200.jpg'
        monkeypatch.setattr(sanity_client, 'slot_map', lambda force=False: {
            'hero': {'url': url,
                     'delivery_url': url + '?' + sanity_client.DELIVERY_PARAMS,
                     'width': 2400, 'height': 1200, 'size': 1, 'alt': '',
                     'original_filename': '', 'updated_at': ''}})
        r = client.get('/assets/hero.jpg')
        # 302, not 301 — a reset must not be pinned in browser caches.
        assert r.status_code == 302
        assert 'auto=format' in r.headers['Location']

    def test_sanity_outage_falls_back_to_disk(self, client, monkeypatch):
        """With Sanity unreachable, the committed image must still be served —
        an outage cannot be allowed to break the home page."""
        monkeypatch.setattr(sanity_client, 'slot_map', REAL_SLOT_MAP)
        monkeypatch.setattr(sanity_client, '_fetch_slot_map',
                            lambda: (_ for _ in ()).throw(OSError('no network')))
        sanity_client.invalidate_cache()
        r = client.get('/assets/hero.jpg')
        assert r.status_code == 200
        assert r.content_type.startswith('image/jpeg')
        sanity_client.invalidate_cache()

    def test_slot_map_swallows_network_errors(self, monkeypatch):
        """slot_map itself must never raise — the public site depends on it."""
        monkeypatch.setattr(sanity_client, '_fetch_slot_map',
                            lambda: (_ for _ in ()).throw(OSError('no network')))
        sanity_client.invalidate_cache()
        assert sanity_client.slot_map() == {}


# ── Upload validation ─────────────────────────────────────────────────────────

class TestUploadValidation:
    def _post(self, client, slot, data, filename='x.png'):
        return client.post(f'/admin/images/{slot}',
                           data={'file': (io.BytesIO(data), filename)},
                           content_type='multipart/form-data')

    def test_unknown_slot_404s(self, admin_client):
        assert self._post(admin_client, 'nope', PNG_BYTES).status_code == 404

    def test_missing_file_400s(self, admin_client):
        r = admin_client.post('/admin/images/hero', data={},
                              content_type='multipart/form-data')
        assert r.status_code == 400

    def test_empty_file_400s(self, admin_client):
        assert self._post(admin_client, 'hero', b'').status_code == 400

    def test_unsupported_type_400s(self, admin_client):
        r = self._post(admin_client, 'hero', b'GIF89a' + b'\x00' * 100, 'x.gif')
        assert r.status_code == 400
        assert b'JPEG, PNG and WebP' in r.data

    def test_disguised_file_is_rejected(self, admin_client):
        """Content-Type and extension are attacker-controlled; magic bytes decide."""
        r = self._post(admin_client, 'hero', b'%PDF-1.4' + b'\x00' * 100, 'evil.png')
        assert r.status_code == 400

    def test_oversize_upload_400s(self, admin_client):
        big = JPEG_BYTES + b'\x00' * (slots.MAX_UPLOAD_BYTES + 1)
        r = self._post(admin_client, 'hero', big, 'big.jpg')
        assert r.status_code == 400
        assert b'the limit is' in r.data

    def test_missing_token_gives_actionable_error(self, admin_client, monkeypatch):
        monkeypatch.delenv('SANITY_API_TOKEN', raising=False)
        r = self._post(admin_client, 'hero', PNG_BYTES)
        assert r.status_code == 502
        assert b'SANITY_API_TOKEN' in r.data

    def test_refresh_is_not_parsed_as_a_slot(self, admin_client):
        """Route precedence: /admin/images/refresh must not hit <slot_id>."""
        assert admin_client.post('/admin/images/refresh').status_code == 200


# ── Sanity write failures ─────────────────────────────────────────────────────

class _FakeResponse:
    def __init__(self, status_code, text=''):
        self.status_code = status_code
        self.text = text


class TestWriteFailures:
    """A read-only token is the most likely misconfiguration, so its error has
    to name the actual remedy rather than echo Sanity's mutationError JSON."""

    # The exact body Sanity returns for a Viewer-role token.
    FORBIDDEN_BODY = ('{"error":{"description":"transaction failed: Insufficient '
                      'permissions; permission \\"create\\" required","type":"mutationError"}}')

    @pytest.mark.parametrize('status', [401, 403])
    def test_permission_error_names_the_fix(self, status):
        with pytest.raises(sanity_client.SanityError) as exc:
            sanity_client._raise_for_status(
                _FakeResponse(status, self.FORBIDDEN_BODY), 'upload')
        msg = str(exc.value)
        assert 'Editor' in msg
        assert 'SANITY_API_TOKEN' in msg
        assert sanity_client.PROJECT_ID in msg
        # The raw mutationError must not be what the admin sees.
        assert 'mutationError' not in msg

    def test_other_errors_still_surface_the_body(self):
        with pytest.raises(sanity_client.SanityError) as exc:
            sanity_client._raise_for_status(_FakeResponse(500, 'upstream boom'), 'change')
        assert 'upstream boom' in str(exc.value)

    def test_success_does_not_raise(self):
        assert sanity_client._raise_for_status(_FakeResponse(200), 'upload') is None

    def test_upload_surfaces_permission_error_through_the_route(
            self, admin_client, monkeypatch):
        """End to end: a 403 from Sanity reaches the admin as guidance, not JSON."""
        monkeypatch.setenv('SANITY_API_TOKEN', 'sk-viewer-token')

        def forbidden(*args, **kwargs):
            return _FakeResponse(403, self.FORBIDDEN_BODY)
        monkeypatch.setattr(sanity_client.requests, 'post', forbidden)

        r = admin_client.post('/admin/images/philosophy-panel',
                              data={'file': (io.BytesIO(PNG_BYTES), 'panel.png')},
                              content_type='multipart/form-data')
        assert r.status_code == 502
        body = r.get_json()
        assert body['success'] is False
        assert 'Editor' in body['error']
        assert 'mutationError' not in body['error']


# ── Slot registry ─────────────────────────────────────────────────────────────

class TestSlotRegistry:
    def test_filenames_are_unique(self):
        names = [s.filename for s in slots.SLOTS.values()]
        assert len(names) == len(set(names))

    def test_lookup_by_filename_round_trips(self):
        for slot in slots.SLOTS.values():
            assert slots.by_filename(slot.filename) is slot

    def test_grouping_covers_every_slot(self):
        grouped = sum(len(v) for v in slots.grouped().values())
        assert grouped == len(slots.SLOTS)

    def test_committed_fallbacks_exist_on_disk(self):
        """Slots claiming a committed fallback must actually have that file."""
        for name in ['hero.jpg', 'sankey-card.jpg', 'backgroundRemoval-card.jpg',
                     'returnstream-card.png', 'marketOutlook-card.png']:
            assert slots.by_filename(name) is not None
            assert os.path.isfile(os.path.join(ASSETS_DIR, name))
