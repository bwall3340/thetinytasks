from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class Source(db.Model):
    __tablename__ = 'sources'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    # CSS selectors for extracting content — admin-configurable per site
    content_selector = db.Column(db.String(300))
    title_selector = db.Column(db.String(200))
    date_selector = db.Column(db.String(200))
    # When the source URL is a listing page, follow the first link matching this selector
    article_link_selector = db.Column(db.String(300))
    # Optional: only follow article links whose text contains this substring (case-insensitive)
    article_link_text_filter = db.Column(db.String(200))
    frequency = db.Column(db.String(20), default='monthly')  # daily/weekly/monthly/quarterly/annual
    active = db.Column(db.Boolean, default=True)
    last_scraped = db.Column(db.DateTime)
    last_scrape_status = db.Column(db.String(20))  # success / failed / duplicate
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    articles = db.relationship(
        'Article', back_populates='source',
        cascade='all, delete-orphan',
        order_by='Article.scraped_at.desc()'
    )

    @property
    def article_count(self):
        return len(self.articles)

    @property
    def analyzed_count(self):
        return sum(1 for a in self.articles if a.analysis is not None)

    @property
    def latest_article(self):
        return self.articles[0] if self.articles else None

    @property
    def due_for_scrape(self):
        from datetime import timedelta
        if not self.active:
            return False
        if self.last_scraped is None:
            return True
        intervals = {'daily': 1, 'weekly': 7, 'monthly': 30, 'quarterly': 90, 'annual': 365}
        delta = timedelta(days=intervals.get(self.frequency, 30))
        return datetime.utcnow() - self.last_scraped > delta


class Article(db.Model):
    __tablename__ = 'articles'

    id = db.Column(db.Integer, primary_key=True)
    source_id = db.Column(db.Integer, db.ForeignKey('sources.id'), nullable=False)
    url = db.Column(db.String(500))
    title = db.Column(db.String(500))
    raw_content = db.Column(db.Text)
    content_hash = db.Column(db.String(64), unique=True, index=True)
    published_at = db.Column(db.DateTime)
    scraped_at = db.Column(db.DateTime, default=datetime.utcnow)

    source = db.relationship('Source', back_populates='articles')
    analysis = db.relationship(
        'Analysis', back_populates='article',
        uselist=False, cascade='all, delete-orphan'
    )


class Analysis(db.Model):
    __tablename__ = 'analyses'

    id = db.Column(db.Integer, primary_key=True)
    article_id = db.Column(db.Integer, db.ForeignKey('articles.id'), unique=True, nullable=False)
    market_outlook = db.Column(db.String(20))      # bullish / bearish / neutral
    sentiment_score = db.Column(db.Float)           # -1.0 to 1.0
    key_themes = db.Column(db.JSON)
    asset_views = db.Column(db.JSON)
    unique_insights = db.Column(db.JSON)
    key_risks = db.Column(db.JSON)
    summary = db.Column(db.Text)
    time_horizon = db.Column(db.String(20))         # short_term / medium_term / long_term
    confidence = db.Column(db.Float)                # 0.0 to 1.0
    processed_at = db.Column(db.DateTime, default=datetime.utcnow)

    article = db.relationship('Article', back_populates='analysis')
