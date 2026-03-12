"""
Public Blueprint — market commentary dashboard.
"""
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, render_template, request
from sqlalchemy import func

from .analyzer import compute_consensus
from .models import Analysis, Article, ConsensusInsight, Source

market_bp = Blueprint('market', __name__, url_prefix='/market')

_LOOKBACK_DAYS = 90


def _best_date_col():
    """SQLAlchemy expression: published_at if set, else scraped_at."""
    return func.coalesce(Article.published_at, Article.scraped_at)


@market_bp.route('/')
def index():
    analyses = (Analysis.query
                .join(Article)
                .join(Source)
                .order_by(Analysis.processed_at.desc())
                .all())
    consensus = compute_consensus(analyses)
    cutoff = datetime.utcnow() - timedelta(days=_LOOKBACK_DAYS)
    recent_articles = (Article.query
                       .join(Analysis)
                       .filter(_best_date_col() >= cutoff)
                       .order_by(_best_date_col().desc())
                       .limit(50).all())
    active_sources = Source.query.filter_by(active=True).count()
    latest_ci = (ConsensusInsight.query
                 .order_by(ConsensusInsight.computed_at.desc())
                 .first())
    return render_template(
        'market/index.html',
        consensus=consensus,
        recent_articles=recent_articles,
        active_sources=active_sources,
        consensus_insights=latest_ci,
    )


@market_bp.route('/api/consensus')
def api_consensus():
    lookback = int(request.args.get('days', _LOOKBACK_DAYS))
    analyses = Analysis.query.join(Article).join(Source).all()
    return jsonify(compute_consensus(analyses, lookback_days=lookback) or {})


@market_bp.route('/api/articles')
def api_articles():
    limit = min(int(request.args.get('limit', 20)), 100)
    cutoff = datetime.utcnow() - timedelta(days=_LOOKBACK_DAYS)
    articles = (Article.query
                .join(Analysis)
                .filter(_best_date_col() >= cutoff)
                .order_by(_best_date_col().desc())
                .limit(limit).all())
    return jsonify([{
        'id': a.id,
        'title': a.title,
        'source': a.source.name if a.source else None,
        'date': (a.published_at or a.scraped_at).isoformat() if (a.published_at or a.scraped_at) else None,
        'scraped_at': a.scraped_at.isoformat() if a.scraped_at else None,
        'outlook': a.analysis.market_outlook if a.analysis else None,
        'sentiment': a.analysis.sentiment_score if a.analysis else None,
        'summary': a.analysis.summary if a.analysis else None,
    } for a in articles])
