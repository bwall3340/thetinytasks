"""
Background scheduler for automated scraping.
Runs an hourly check to scrape sources that are due based on their frequency.
"""
import logging
import os

from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)
_scheduler = None


def _run_scheduled_scrape(app):
    from .models import db, Source, Article, Analysis
    from .scraper import scrape_source
    from .analyzer import analyze_article

    with app.app_context():
        sources = Source.query.filter_by(active=True).all()
        for source in sources:
            if not source.due_for_scrape:
                continue

            logger.info('Scheduled scrape: %s', source.name)
            result = scrape_source(source)

            if not result['success']:
                source.last_scrape_status = 'failed'
                db.session.commit()
                continue

            existing = Article.query.filter_by(content_hash=result['content_hash']).first()
            if existing:
                source.last_scrape_status = 'duplicate'
                from datetime import datetime
                source.last_scraped = datetime.utcnow()
                db.session.commit()
                continue

            from datetime import datetime
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

            if os.environ.get('ANTHROPIC_API_KEY'):
                analysis_data = analyze_article(article)
                if analysis_data:
                    db.session.add(Analysis(article_id=article.id, **analysis_data))
                    db.session.commit()
                    logger.info('Auto-analyzed: %s — %s', source.name, analysis_data['market_outlook'])


def start_scheduler(app):
    global _scheduler
    if _scheduler and _scheduler.running:
        return
    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(
        func=_run_scheduled_scrape,
        args=[app],
        trigger='interval',
        hours=1,
        id='market_scrape',
        replace_existing=True,
    )
    _scheduler.start()
    logger.info('Market scrape scheduler started (hourly)')


def stop_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
