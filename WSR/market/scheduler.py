"""
Background scheduler for automated scraping and consensus analysis.

Scrape jobs run at 07:00 UTC (2 AM EST) and 19:00 UTC (2 PM EST), Mon–Fri only.
  - 19:00 UTC is the primary scrape window.
  - 07:00 UTC handles daily-frequency 12 h retries.
  Sources not yet due (based on frequency + retry state) are skipped each run.

Retry / block policy (no new article found):
  daily     → retry every 12 h, block after 4 misses  (≈ 2 days)
  weekly    → retry every 24 h, block after 8 misses  (≈ rest of week + Mon next week)
  monthly   → retry every 7 d,  block after 4 misses  (≈ 1 month)
  quarterly → retry every 7 d,  block after 12 misses (≈ 1 quarter)
  annual    → retry every 30 d, block after 6 misses  (≈ 6 months)

A blocked source is skipped by the scheduler until a manual scrape resets it.

Weekly (Sunday 02:00 UTC): run second-pass consensus insight analysis.
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
    from datetime import datetime

    with app.app_context():
        sources = Source.query.filter_by(active=True).all()
        for source in sources:
            if not source.due_for_scrape:
                continue

            logger.info('Scheduled scrape: %s', source.name)
            results = scrape_source(source)

            new_count = 0
            no_new_count = 0  # duplicates + failures

            for result in results:
                if not result['success']:
                    logger.warning('Scrape result failed for %s: %s',
                                   source.name, result.get('error'))
                    no_new_count += 1
                    continue

                existing = Article.query.filter_by(source_id=source.id, content_hash=result['content_hash']).first()
                if existing:
                    logger.debug('Duplicate for %s: %s', source.name, result['url'])
                    existing.scraped_at = datetime.utcnow()  # mark as recently verified
                    no_new_count += 1
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
                db.session.flush()  # assign article.id before analyzing
                new_count += 1

                if os.environ.get('ANTHROPIC_API_KEY'):
                    analysis_data = analyze_article(article)
                    if analysis_data:
                        db.session.add(Analysis(article_id=article.id, **analysis_data))
                        logger.info('Auto-analyzed: %s — %s',
                                    source.name, analysis_data['market_outlook'])

            source.last_scraped = datetime.utcnow()

            if new_count > 0:
                source.last_scrape_status = 'success'
                source.consecutive_duplicates = 0
                source.scrape_blocked = False
                logger.info('Saved %d new article(s) for %s', new_count, source.name)
            else:
                # No new content — increment retry counter and check limit
                source.consecutive_duplicates = (source.consecutive_duplicates or 0) + 1
                max_retries = source._MAX_RETRIES.get(source.frequency, 4)
                retry_h = source._RETRY_HOURS.get(source.frequency, 24)

                if source.consecutive_duplicates >= max_retries:
                    source.scrape_blocked = True
                    source.last_scrape_status = 'blocked'
                    logger.error(
                        'SOURCE BLOCKED: %s — no new content after %d attempts. '
                        'Manual scrape required to resume automation.',
                        source.name, source.consecutive_duplicates,
                    )
                else:
                    source.last_scrape_status = 'duplicate' if no_new_count else 'failed'
                    logger.info(
                        'No new content for %s — retry in %dh (attempt %d/%d)',
                        source.name, retry_h,
                        source.consecutive_duplicates, max_retries,
                    )

            db.session.commit()


def _run_consensus_insights(app):
    """Weekly job: second-pass Claude analysis to cross-validate unique insights."""
    from .models import db, Analysis, Article, Source, ConsensusInsight
    from .analyzer import run_consensus_insights, compute_consensus

    with app.app_context():
        if not os.environ.get('ANTHROPIC_API_KEY'):
            logger.warning('Skipping consensus insights — ANTHROPIC_API_KEY not set')
            return

        analyses = (Analysis.query
                    .join(Article)
                    .join(Source)
                    .filter(Source.active == True)
                    .all())
        if not analyses:
            logger.info('No analyses available for consensus insights run')
            return

        logger.info('Running weekly consensus insights (n=%d analyses)', len(analyses))
        insights = run_consensus_insights(analyses)
        if insights is None:
            logger.error('consensus_insights run failed')
            return

        # Grab lightweight consensus context to store alongside
        consensus = compute_consensus(analyses) or {}

        record = ConsensusInsight(
            source_count=len({a.article.source_id for a in analyses if a.article}),
            insights=insights,
            consensus_outlook=consensus.get('market_outlook'),
            consensus_sentiment=consensus.get('avg_sentiment'),
        )
        db.session.add(record)
        db.session.commit()
        logger.info('Consensus insights saved: %d divergent insights', len(insights))


def start_scheduler(app):
    global _scheduler
    if _scheduler and _scheduler.running:
        return
    _scheduler = BackgroundScheduler(daemon=True)

    # Primary scrape: 2 PM EST = 19:00 UTC, Mon–Fri
    _scheduler.add_job(
        func=_run_scheduled_scrape,
        args=[app],
        trigger='cron',
        day_of_week='mon-fri',
        hour=19,
        minute=0,
        id='market_scrape_pm',
        replace_existing=True,
    )
    # Early check: 2 AM EST = 07:00 UTC, Mon–Fri (handles daily 12 h retries)
    _scheduler.add_job(
        func=_run_scheduled_scrape,
        args=[app],
        trigger='cron',
        day_of_week='mon-fri',
        hour=7,
        minute=0,
        id='market_scrape_am',
        replace_existing=True,
    )
    _scheduler.add_job(
        func=_run_consensus_insights,
        args=[app],
        trigger='cron',
        day_of_week='sun',
        hour=2,
        minute=0,
        id='consensus_insights',
        replace_existing=True,
    )

    # Meal plan auto-fill: midnight UTC daily
    try:
        from meal.scheduler import run_meal_auto_fill
        _scheduler.add_job(
            func=run_meal_auto_fill,
            args=[app],
            trigger='cron',
            hour=0,
            minute=5,
            id='meal_auto_fill',
            replace_existing=True,
        )
    except ImportError:
        logger.warning('Meal scheduler not available — skipping meal auto-fill job')

    _scheduler.start()
    logger.info(
        'Scheduler started: scrape (Mon–Fri 07:00 + 19:00 UTC), '
        'consensus insights (weekly Sun 02:00 UTC), '
        'meal auto-fill (daily 00:05 UTC)'
    )


def stop_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
