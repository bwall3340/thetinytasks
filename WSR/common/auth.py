"""
Shared admin authentication — Google OAuth + ADMIN_EMAILS whitelist.

Single source of truth for every /<module>/admin surface.  One login grants
access to every admin dashboard; a module protects its routes by decorating
them with @require_admin.

Consolidates the two near-identical implementations that previously lived in
market/admin.py and meal/admin.py, so a new module never has to re-register an
OAuth redirect URI.
"""
import logging
import os
from functools import wraps
from urllib.parse import urljoin, urlparse

from authlib.integrations.flask_client import OAuth
from flask import (Blueprint, flash, redirect, render_template, request,
                   session, url_for)

logger = logging.getLogger(__name__)

# One session key for every admin surface — log in once, access all of them.
SESSION_KEY = 'admin_user'

# Where to send the user after login when no explicit ?next= was supplied.
DEFAULT_LANDING = 'site_admin.dashboard'

auth_bp = Blueprint('admin_auth', __name__, url_prefix='/admin')

oauth = OAuth()


def init_oauth(app):
    """Register the Google provider. Call once, at app construction."""
    oauth.init_app(app)
    oauth.register(
        name='google',
        client_id=app.config.get('GOOGLE_CLIENT_ID'),
        client_secret=app.config.get('GOOGLE_CLIENT_SECRET'),
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={'scope': 'openid email profile'},
    )


def admin_emails():
    """The set of Google account emails allowed into any admin page."""
    raw = os.environ.get('ADMIN_EMAILS', '')
    return {e.strip().lower() for e in raw.split(',') if e.strip()}


def current_admin():
    """The logged-in admin dict, or None."""
    return session.get(SESSION_KEY)


def _is_safe_redirect(target):
    """True only for same-host relative targets — blocks open-redirect abuse."""
    if not target:
        return False
    host = urlparse(request.host_url).netloc
    parsed = urlparse(urljoin(request.host_url, target))
    return parsed.scheme in ('http', 'https') and parsed.netloc == host


def require_admin(f):
    """Gate a route behind an authenticated, whitelisted admin session."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if SESSION_KEY not in session:
            return redirect(url_for('admin_auth.login', next=request.path))
        return f(*args, **kwargs)
    return decorated


# ── Routes ────────────────────────────────────────────────────────────────────

@auth_bp.route('/login')
def login():
    nxt = request.args.get('next', '')
    if SESSION_KEY in session:
        return redirect(nxt if _is_safe_redirect(nxt) else url_for(DEFAULT_LANDING))
    session['admin_next'] = nxt if _is_safe_redirect(nxt) else ''
    return render_template('admin/login.html')


@auth_bp.route('/auth')
def auth():
    redirect_uri = url_for('admin_auth.auth_callback', _external=True)
    return oauth.google.authorize_redirect(redirect_uri)


@auth_bp.route('/auth/callback')
def auth_callback():
    try:
        token = oauth.google.authorize_access_token()
        user_info = token.get('userinfo') or {}
        email = (user_info.get('email') or '').lower()

        if email not in admin_emails():
            logger.warning('Admin login denied for %s', email)
            flash('Access denied: your email is not authorized.', 'error')
            return redirect(url_for('admin_auth.login'))

        session.permanent = True
        session[SESSION_KEY] = {'email': email, 'name': user_info.get('name', email)}

        nxt = session.pop('admin_next', '')
        return redirect(nxt if _is_safe_redirect(nxt) else url_for(DEFAULT_LANDING))
    except Exception as e:
        logger.error('OAuth callback error: %s', e)
        flash('Authentication failed. Please try again.', 'error')
        return redirect(url_for('admin_auth.login'))


@auth_bp.route('/logout')
def logout():
    session.pop(SESSION_KEY, None)
    session.pop('admin_next', None)
    return redirect(url_for('admin_auth.login'))
