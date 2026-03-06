"""
Admin Blueprint — Google OAuth login + source/article management.
All routes under /market-admin require the admin_user session key.
"""
import logging
import os
import time
import traceback
from datetime import datetime
from functools import wraps

from authlib.integrations.flask_client import OAuth
from flask import (Blueprint, flash, jsonify, redirect, render_template,
                   request, session, url_for)

from .models import Analysis, Article, Source, db
from .scraper import scrape_source, validate_scrape, discover_links
from .analyzer import analyze_article

logger = logging.getLogger(__name__)

admin_bp = Blueprint('market_admin', __name__, url_prefix='/market-admin')
_oauth = OAuth()


def init_oauth(app):
    _oauth.init_app(app)
    _oauth.register(
        name='google',
        client_id=app.config.get('GOOGLE_CLIENT_ID'),
        client_secret=app.config.get('GOOGLE_CLIENT_SECRET'),
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={'scope': 'openid email profile'},
    )


def _admin_emails():
    raw = os.environ.get('ADMIN_EMAILS', '')
    return {e.strip().lower() for e in raw.split(',') if e.strip()}


def require_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'admin_user' not in session:
            return redirect(url_for('market_admin.login'))
        return f(*args, **kwargs)
    return decorated


# ── Auth ──────────────────────────────────────────────────────────────────────

@admin_bp.route('/')
def index():
    if 'admin_user' in session:
        return redirect(url_for('market_admin.dashboard'))
    return redirect(url_for('market_admin.login'))


@admin_bp.route('/login')
def login():
    if 'admin_user' in session:
        return redirect(url_for('market_admin.dashboard'))
    return render_template('market_admin/login.html')


@admin_bp.route('/auth')
def auth():
    redirect_uri = url_for('market_admin.auth_callback', _external=True)
    return _oauth.google.authorize_redirect(redirect_uri)


@admin_bp.route('/callback')
def auth_callback():
    try:
        token = _oauth.google.authorize_access_token()
        user_info = token.get('userinfo') or {}
        email = (user_info.get('email') or '').lower()

        if email not in _admin_emails():
            flash('Access denied: your email is not authorized.', 'error')
            return redirect(url_for('market_admin.login'))

        session.permanent = True
        session['admin_user'] = {'email': email, 'name': user_info.get('name', email)}
        return redirect(url_for('market_admin.dashboard'))
    except Exception as e:
        logger.error('OAuth callback error: %s', e)
        flash('Authentication failed. Please try again.', 'error')
        return redirect(url_for('market_admin.login'))


@admin_bp.route('/logout')
def logout():
    session.pop('admin_user', None)
    return redirect(url_for('market_admin.login'))


# ── Dashboard ─────────────────────────────────────────────────────────────────

@admin_bp.route('/dashboard')
@require_admin
def dashboard():
    sources = Source.query.order_by(Source.name).all()
    return render_template(
        'market_admin/dashboard.html',
        sources=sources,
        total_articles=Article.query.count(),
        total_analyses=Analysis.query.count(),
        pending_analysis=Article.query.filter(~Article.analysis.has()).count(),
        admin_user=session['admin_user'],
    )


# ── Source CRUD ───────────────────────────────────────────────────────────────

@admin_bp.route('/sources/new', methods=['GET', 'POST'])
@require_admin
def new_source():
    if request.method == 'POST':
        source = Source(
            name=request.form['name'].strip(),
            url=request.form['url'].strip(),
            frequency=request.form.get('frequency', 'monthly'),
            article_link_selector=request.form.get('article_link_selector', '').strip() or None,
            article_link_text_filter=request.form.get('article_link_text_filter', '').strip() or None,
            content_selector=request.form.get('content_selector', '').strip() or None,
            title_selector=request.form.get('title_selector', '').strip() or None,
            date_selector=request.form.get('date_selector', '').strip() or None,
            notes=request.form.get('notes', '').strip() or None,
        )
        db.session.add(source)
        db.session.commit()
        flash(f'Source "{source.name}" added.', 'success')
        return redirect(url_for('market_admin.dashboard'))
    return render_template('market_admin/source_form.html',
                           source=None, admin_user=session['admin_user'])


@admin_bp.route('/sources/<int:source_id>/edit', methods=['GET', 'POST'])
@require_admin
def edit_source(source_id):
    source = db.session.get(Source, source_id)
    if not source:
        flash('Source not found.', 'error')
        return redirect(url_for('market_admin.dashboard'))
    if request.method == 'POST':
        source.name = request.form['name'].strip()
        source.url = request.form['url'].strip()
        source.frequency = request.form.get('frequency', 'monthly')
        source.article_link_selector = request.form.get('article_link_selector', '').strip() or None
        source.article_link_text_filter = request.form.get('article_link_text_filter', '').strip() or None
        source.content_selector = request.form.get('content_selector', '').strip() or None
        source.title_selector = request.form.get('title_selector', '').strip() or None
        source.date_selector = request.form.get('date_selector', '').strip() or None
        source.notes = request.form.get('notes', '').strip() or None
        source.active = 'active' in request.form
        db.session.commit()
        flash(f'Source "{source.name}" updated.', 'success')
        return redirect(url_for('market_admin.dashboard'))
    return render_template('market_admin/source_form.html',
                           source=source, admin_user=session['admin_user'])


@admin_bp.route('/sources/<int:source_id>/delete', methods=['POST'])
@require_admin
def delete_source(source_id):
    source = db.session.get(Source, source_id)
    if not source:
        flash('Source not found.', 'error')
        return redirect(url_for('market_admin.dashboard'))
    name = source.name
    db.session.delete(source)
    db.session.commit()
    flash(f'Source "{name}" deleted.', 'success')
    return redirect(url_for('market_admin.dashboard'))


# ── Scrape / Analyze / Validate (JSON API for admin JS) ──────────────────────

@admin_bp.route('/sources/<int:source_id>/scrape', methods=['POST'])
@require_admin
def scrape_now(source_id):
    try:
        source = db.session.get(Source, source_id)
        if not source:
            return jsonify({'success': False, 'error': 'Source not found'}), 404

        result = scrape_source(source)

        if not result['success']:
            source.last_scrape_status = 'failed'
            db.session.commit()
            return jsonify({'success': False, 'error': result['error']})

        existing = Article.query.filter_by(content_hash=result['content_hash']).first()
        if existing:
            source.last_scraped = datetime.utcnow()
            source.last_scrape_status = 'duplicate'
            db.session.commit()
            return jsonify({'success': True, 'duplicate': True,
                            'message': 'Content unchanged since last scrape.'})

        article = Article(
            source_id=source.id,
            url=result['url'],
            title=result['title'],
            raw_content=result['content'],
            content_hash=result['content_hash'],
            published_at=result['published_at'],
        )
        db.session.add(article)
        source.last_scraped = datetime.utcnow()
        source.last_scrape_status = 'success'
        db.session.commit()

        return jsonify({
            'success': True,
            'article_id': article.id,
            'title': article.title,
            'word_count': result['word_count'],
            'message': f'Scraped {result["word_count"]:,} words.',
        })
    except Exception as e:
        logger.error('scrape_now error for source %s: %s', source_id, e)
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/sources/<int:source_id>/analyze', methods=['POST'])
@require_admin
def analyze_latest(source_id):
    try:
        source = db.session.get(Source, source_id)
        if not source:
            return jsonify({'success': False, 'error': 'Source not found'}), 404

        article = (Article.query
                   .filter_by(source_id=source_id)
                   .filter(~Article.analysis.has())
                   .order_by(Article.scraped_at.desc())
                   .first())
        if not article:
            return jsonify({'success': False, 'error': 'No unanalyzed articles for this source.'})

        result = analyze_article(article)
        if not result:
            return jsonify({'success': False, 'error': 'AI analysis failed. Check ANTHROPIC_API_KEY.'})

        db.session.add(Analysis(article_id=article.id, **result))
        db.session.commit()
        return jsonify({
            'success': True,
            'market_outlook': result['market_outlook'],
            'sentiment_score': result['sentiment_score'],
            'summary': result['summary'],
            'message': f'Analysis complete: {result["market_outlook"]} outlook.',
        })
    except Exception as e:
        logger.error('analyze_latest error for source %s: %s\n%s',
                     source_id, e, traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/sources/<int:source_id>/discover-links', methods=['POST'])
@require_admin
def discover_source_links(source_id):
    try:
        source = db.session.get(Source, source_id)
        if not source:
            return jsonify({'success': False, 'error': 'Source not found'}), 404
        result = discover_links(source.url)
        return jsonify(result)
    except Exception as e:
        logger.error('discover_source_links error for source %s: %s', source_id, e)
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/sources/<int:source_id>/set-selector', methods=['POST'])
@require_admin
def set_article_selector(source_id):
    try:
        source = db.session.get(Source, source_id)
        if not source:
            return jsonify({'success': False, 'error': 'Source not found'}), 404
        data = request.get_json() or {}
        selector = data.get('selector', '').strip()
        text_filter = data.get('text_filter', '').strip()
        source.article_link_selector = selector or None
        source.article_link_text_filter = text_filter or None
        db.session.commit()
        return jsonify({'success': True, 'selector': selector, 'text_filter': text_filter})
    except Exception as e:
        logger.error('set_article_selector error for source %s: %s', source_id, e)
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/sources/<int:source_id>/validate', methods=['POST'])
@require_admin
def validate_source(source_id):
    try:
        source = db.session.get(Source, source_id)
        if not source:
            return jsonify({'success': False, 'error': 'Source not found'}), 404

        result = validate_scrape(
            source.url,
            content_selector=source.content_selector,
            title_selector=source.title_selector,
            date_selector=source.date_selector,
            article_link_selector=source.article_link_selector,
            article_link_text_filter=source.article_link_text_filter,
        )
        return jsonify(result)
    except Exception as e:
        logger.error('validate_source error for source %s: %s', source_id, e)
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/sources/<int:source_id>/articles')
@require_admin
def source_articles(source_id):
    source = db.session.get(Source, source_id)
    if not source:
        flash('Source not found.', 'error')
        return redirect(url_for('market_admin.dashboard'))
    articles = (Article.query
                .filter_by(source_id=source_id)
                .order_by(Article.scraped_at.desc())
                .limit(30).all())
    return render_template('market_admin/source_articles.html',
                           source=source, articles=articles,
                           admin_user=session['admin_user'])


@admin_bp.route('/analyze-all', methods=['POST'])
@require_admin
def analyze_all():
    """Analyze up to 20 unanalyzed articles across all sources."""
    try:
        pending = (Article.query
                   .filter(~Article.analysis.has())
                   .order_by(Article.scraped_at.desc())
                   .limit(20).all())
        results = []
        for article in pending:
            data = analyze_article(article)
            if data:
                db.session.add(Analysis(article_id=article.id, **data))
                results.append({'article_id': article.id, 'outlook': data['market_outlook']})
            time.sleep(0.5)  # respect rate limits

        db.session.commit()
        return jsonify({'success': True, 'analyzed': len(results), 'results': results})
    except Exception as e:
        logger.error('analyze_all error: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500
