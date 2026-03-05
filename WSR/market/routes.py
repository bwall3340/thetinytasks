"""
Public Blueprint — market commentary dashboard.
"""
from flask import Blueprint, jsonify, render_template, request

from .analyzer import compute_consensus
from .models import Analysis, Article, Source

market_bp = Blueprint('market', __name__, url_prefix='/market')


@market_bp.route('/')
def index():
    analyses = (Analysis.query
                .join(Article)
                .join(Source)
                .order_by(Analysis.processed_at.desc())
                .all())
    consensus = compute_consensus(analyses)
    recent_articles = (Article.query
                       .join(Analysis)
                       .order_by(Article.scraped_at.desc())
                       .limit(12).all())
    active_sources = Source.query.filter_by(active=True).count()
    return render_template(
        'market/index.html',
        consensus=consensus,
        recent_articles=recent_articles,
        active_sources=active_sources,
    )


@market_bp.route('/api/consensus')
def api_consensus():
    lookback = int(request.args.get('days', 90))
    analyses = Analysis.query.join(Article).join(Source).all()
    return jsonify(compute_consensus(analyses, lookback_days=lookback) or {})


@market_bp.route('/api/articles')
def api_articles():
    limit = min(int(request.args.get('limit', 20)), 100)
    articles = (Article.query
                .join(Analysis)
                .order_by(Article.scraped_at.desc())
                .limit(limit).all())
    return jsonify([{
        'id': a.id,
        'title': a.title,
        'source': a.source.name if a.source else None,
        'scraped_at': a.scraped_at.isoformat() if a.scraped_at else None,
        'outlook': a.analysis.market_outlook if a.analysis else None,
        'sentiment': a.analysis.sentiment_score if a.analysis else None,
        'summary': a.analysis.summary if a.analysis else None,
    } for a in articles])
