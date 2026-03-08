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

from .models import Analysis, Article, Source, ConsensusInsight, db
from .scraper import scrape_source, validate_scrape, discover_links
from .analyzer import analyze_article, run_consensus_insights, compute_consensus

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

        results = scrape_source(source)

        new_articles = []
        duplicates = 0
        first_error = None

        for result in results:
            if not result['success']:
                if first_error is None:
                    first_error = result['error']
                continue

            existing = Article.query.filter_by(content_hash=result['content_hash']).first()
            if existing:
                existing.scraped_at = datetime.utcnow()  # mark as recently verified
                duplicates += 1
                continue

            article = Article(
                source_id=source.id,
                url=result['url'],
                title=result['title'],
                raw_content=result['content'],
                content_hash=result['content_hash'],
                published_at=result['published_at'],
            )
            db.session.add(article)
            new_articles.append((article, result))

        if new_articles:
            source.last_scraped = datetime.utcnow()
            source.last_scrape_status = 'success'
        elif duplicates:
            # Retry sooner than the full cadence — source may just be slow to update
            source.last_scraped = source.duplicate_retry_last_scraped()
            source.last_scrape_status = 'duplicate'
        else:
            source.last_scrape_status = 'failed'

        db.session.commit()

        if new_articles:
            first_article, first_result = new_articles[0]
            extra = f', {duplicates} duplicate(s)' if duplicates else ''
            return jsonify({
                'success': True,
                'article_id': first_article.id,
                'title': first_article.title,
                'word_count': first_result['word_count'],
                'message': f'Scraped {len(new_articles)} new article(s){extra}.',
            })
        elif first_error and not duplicates:
            return jsonify({'success': False, 'error': first_error})
        else:
            retry_h = source._RETRY_HOURS.get(source.frequency, 48)
            return jsonify({'success': True, 'duplicate': True,
                            'message': f'Content unchanged ({duplicates} duplicate(s)). '
                                       f'Will check again in ~{retry_h}h.'})
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


@admin_bp.route('/articles/<int:article_id>/set-date', methods=['POST'])
@require_admin
def set_article_date(article_id):
    try:
        article = db.session.get(Article, article_id)
        if not article:
            return jsonify({'success': False, 'error': 'Article not found'}), 404
        data = request.get_json() or {}
        date_str = (data.get('published_at') or '').strip()
        if date_str:
            try:
                article.published_at = datetime.strptime(date_str, '%Y-%m-%d')
            except ValueError:
                return jsonify({'success': False, 'error': 'Invalid date — use YYYY-MM-DD'})
        else:
            article.published_at = None
        db.session.commit()
        display = article.published_at.strftime('%b %d, %Y') if article.published_at else ''
        return jsonify({'success': True, 'published_at_display': display})
    except Exception as e:
        logger.error('set_article_date error for article %s: %s', article_id, e)
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/articles/<int:article_id>/delete', methods=['POST'])
@require_admin
def delete_article(article_id):
    try:
        article = db.session.get(Article, article_id)
        if not article:
            return jsonify({'success': False, 'error': 'Article not found'}), 404
        source_id = article.source_id
        db.session.delete(article)
        db.session.flush()
        # If no articles remain, reset last_scraped so the next scrape triggers archive mode
        remaining = Article.query.filter_by(source_id=source_id).count()
        if remaining == 0:
            source = db.session.get(Source, source_id)
            if source:
                source.last_scraped = None
                source.last_scrape_status = None
        db.session.commit()
        return jsonify({'success': True, 'source_id': source_id})
    except Exception as e:
        logger.error('delete_article error for article %s: %s', article_id, e)
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


@admin_bp.route('/run-consensus-insights', methods=['POST'])
@require_admin
def run_consensus_insights_now():
    """Manually trigger the second-pass consensus insight analysis."""
    try:
        analyses = (Analysis.query
                    .join(Article)
                    .join(Source)
                    .filter(Source.active == True)
                    .all())
        if not analyses:
            return jsonify({'success': False, 'error': 'No analyses available'}), 400

        insights = run_consensus_insights(analyses)
        if insights is None:
            return jsonify({'success': False, 'error': 'Claude API call failed — check server logs'}), 500

        consensus = compute_consensus(analyses) or {}
        record = ConsensusInsight(
            source_count=len({a.article.source_id for a in analyses if a.article}),
            insights=insights,
            consensus_outlook=consensus.get('market_outlook'),
            consensus_sentiment=consensus.get('avg_sentiment'),
        )
        db.session.add(record)
        db.session.commit()
        return jsonify({'success': True, 'divergent_count': len(insights)})
    except Exception as e:
        logger.error('run_consensus_insights_now error: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500
