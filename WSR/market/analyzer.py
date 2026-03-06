"""
Claude API integration for structured analysis of market commentary.
"""
import json
import logging
import os
import re
from collections import Counter
from datetime import datetime, timedelta

import anthropic

logger = logging.getLogger(__name__)

_MAX_WORDS = 2500

_PROMPT = """\
You are a senior financial analyst. Analyze the following market commentary and return a single JSON object.

Required fields:
- "market_outlook": exactly one of "bullish", "bearish", or "neutral"
- "sentiment_score": float from -1.0 (strongly bearish) to 1.0 (strongly bullish)
- "key_themes": array of up to 8 theme strings. IMPORTANT: use 2-3 words maximum per theme, lowercase, no filler words like "concerns", "risks", "fears", "uncertainty", "outlook". Good examples: "inflation", "rate cuts", "credit tightening", "AI disruption", "dollar strength"
- "asset_views": object mapping asset classes to their view. Cover: equities, bonds, commodities, cash, alternatives, real_estate. Each entry: {"view": "overweight"|"underweight"|"neutral", "reasoning": "one sentence"}
- "unique_insights": array of strings — opinions that are clearly contrarian or distinctive vs. mainstream consensus. Empty array if none.
- "key_risks": array of up to 5 risk strings
- "summary": 2-3 sentence plain-English summary
- "time_horizon": one of "short_term" (< 3 months), "medium_term" (3–12 months), or "long_term" (> 12 months)
- "confidence": float 0.0–1.0 reflecting the specificity and depth of the commentary

Return ONLY the JSON object. No markdown, no preamble, no explanation.

Source: {source_name}
Commentary:
{content}"""


def _extract_json(text: str):
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return None


def analyze_article(article) -> dict | None:
    """
    Call Claude to analyze an Article object.
    Returns a dict ready to unpack into Analysis(**result), or None on failure.
    """
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        logger.error('ANTHROPIC_API_KEY not set')
        return None

    source_name = article.source.name if article.source else 'Unknown'
    if not article.raw_content:
        logger.error('Article %s has no raw_content — skipping', article.id)
        return None
    words = article.raw_content.split()
    content = ' '.join(words[:_MAX_WORDS])

    # Use replace() instead of .format() — content may contain curly braces
    # (e.g. JSON snippets) that would cause a KeyError in .format()
    prompt = _PROMPT.replace('{source_name}', source_name).replace('{content}', content)

    try:
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model='claude-sonnet-4-6',
            max_tokens=1500,
            messages=[{'role': 'user', 'content': prompt}],
        )
        data = _extract_json(message.content[0].text)
        if not data or not isinstance(data, dict):
            logger.error('Could not parse JSON dict from Claude for article %s (got: %r)',
                         article.id, data)
            return None

        return {
            'market_outlook': str(data.get('market_outlook', 'neutral')).lower(),
            'sentiment_score': float(data.get('sentiment_score', 0)),
            'key_themes': data.get('key_themes') or [],
            'asset_views': data.get('asset_views') or {},
            'unique_insights': data.get('unique_insights') or [],
            'key_risks': data.get('key_risks') or [],
            'summary': str(data.get('summary', '')),
            'time_horizon': str(data.get('time_horizon', 'medium_term')),
            'confidence': float(data.get('confidence', 0.5)),
        }
    except Exception as e:
        logger.error('Claude API error for article %s: %s', article.id, e)
        return None


_THEME_NOISE_SUFFIXES = (
    ' concerns', ' concern', ' risks', ' risk', ' fears', ' fear',
    ' uncertainty', ' uncertainties', ' outlook', ' sentiment',
    ' worries', ' worry', ' pressures', ' pressure',
)


def _theme_group_key(theme: str) -> str:
    """Normalize a theme to a grouping key: lowercase, strip noise suffixes, first 2 words."""
    t = theme.lower().strip()
    for suffix in _THEME_NOISE_SUFFIXES:
        if t.endswith(suffix):
            t = t[:-len(suffix)].strip()
            break
    return ' '.join(t.split()[:2])


def _merge_themes(theme_counts: Counter) -> Counter:
    """
    Group near-duplicate themes (e.g. 'AI disruption concerns' and
    'AI disruption and megacap') by their 2-word normalized key.
    The canonical display name is whichever variant appeared most.
    """
    buckets: dict[str, tuple[str, int]] = {}  # group_key -> (canonical_name, total_count)
    # Process in descending frequency so the most-common variant wins canonical name
    for theme, count in theme_counts.most_common():
        key = _theme_group_key(theme)
        if key in buckets:
            canonical, total = buckets[key]
            buckets[key] = (canonical, total + count)
        else:
            buckets[key] = (theme, count)
    return Counter({canonical: total for canonical, total in buckets.values()})


def compute_consensus(analyses, lookback_days=90) -> dict | None:
    """
    Aggregate a list of Analysis objects into a consensus view.
    """
    if not analyses:
        return None

    cutoff = datetime.utcnow() - timedelta(days=lookback_days)
    recent = [a for a in analyses if a.processed_at and a.processed_at >= cutoff]
    if not recent:
        recent = list(analyses)  # fall back to all data

    # --- Overall outlook ---
    outlooks = [a.market_outlook for a in recent if a.market_outlook]
    outlook_counts = Counter(outlooks)
    top_outlook = outlook_counts.most_common(1)[0][0] if outlook_counts else 'neutral'
    outlook_confidence = round(outlook_counts[top_outlook] / len(outlooks) * 100, 1) if outlooks else 0

    # --- Sentiment ---
    scores = [a.sentiment_score for a in recent if a.sentiment_score is not None]
    avg_sentiment = round(sum(scores) / len(scores), 2) if scores else 0.0

    # --- Themes ---
    all_themes = []
    for a in recent:
        if a.key_themes:
            all_themes.extend(a.key_themes)
    theme_counts = Counter(all_themes)
    top_themes = [
        {'theme': t, 'count': c, 'pct': round(c / len(recent) * 100)}
        for t, c in _merge_themes(theme_counts).most_common(10)
    ]

    # --- Asset views ---
    asset_buckets: dict[str, list] = {}
    for a in recent:
        if not a.asset_views:
            continue
        for asset, vdata in a.asset_views.items():
            view = vdata.get('view') if isinstance(vdata, dict) else str(vdata)
            if view:
                asset_buckets.setdefault(asset, []).append(view.lower())

    asset_consensus = {}
    for asset, views in asset_buckets.items():
        cnts = Counter(views)
        top_view, top_cnt = cnts.most_common(1)[0]
        asset_consensus[asset] = {
            'view': top_view,
            'confidence': round(top_cnt / len(views) * 100, 1),
            'count': len(views),
            'breakdown': dict(cnts),
        }

    # --- Unique insights ---
    unique_insights = []
    for a in recent:
        if a.unique_insights and a.article:
            source_name = a.article.source.name if a.article.source else 'Unknown'
            date_str = a.processed_at.strftime('%b %d, %Y') if a.processed_at else ''
            for insight in (a.unique_insights or [])[:2]:
                unique_insights.append({
                    'insight': insight,
                    'source': source_name,
                    'date': date_str,
                    'outlook': a.market_outlook,
                })

    # --- Risks ---
    all_risks = []
    for a in recent:
        if a.key_risks:
            all_risks.extend(a.key_risks)
    top_risks = [{'risk': r, 'count': c} for r, c in _merge_themes(Counter(all_risks)).most_common(8)]

    return {
        'total_sources': len(recent),
        'lookback_days': lookback_days,
        'market_outlook': top_outlook,
        'outlook_confidence': outlook_confidence,
        'avg_sentiment': avg_sentiment,
        'outlook_breakdown': dict(outlook_counts),
        'top_themes': top_themes,
        'asset_consensus': asset_consensus,
        'unique_insights': unique_insights[:12],
        'top_risks': top_risks,
        'updated_at': datetime.utcnow().strftime('%b %d, %Y %H:%M UTC'),
    }
