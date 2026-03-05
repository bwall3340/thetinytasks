"""
Web scraping utilities for market commentary sources.
Uses requests + BeautifulSoup with configurable CSS selectors.
"""
import hashlib
import logging
import time

import requests
from bs4 import BeautifulSoup
from datetime import datetime

logger = logging.getLogger(__name__)

_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/122.0.0.0 Safari/537.36'
    ),
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate, br',
}

_DATE_FORMATS = [
    '%Y-%m-%d', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%SZ',
    '%B %d, %Y', '%b %d, %Y', '%b. %d, %Y',
    '%m/%d/%Y', '%d %B %Y', '%d %b %Y',
]

_CONTENT_FALLBACKS = [
    'article', '.article-body', '.content', '.post-content',
    '.article-content', '.entry-content', '#content', 'main',
]


def _fetch(url, timeout=30, retries=3):
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=_HEADERS, timeout=timeout)
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)


def _clean_soup(soup):
    for tag in soup.find_all(['nav', 'footer', 'header', 'script', 'style',
                               'aside', 'form', 'iframe', 'noscript']):
        tag.decompose()
    return soup


def _extract_content(soup, selector=None):
    if selector:
        els = soup.select(selector)
        if els:
            return '\n\n'.join(e.get_text(separator=' ', strip=True) for e in els)

    for sel in _CONTENT_FALLBACKS:
        els = soup.select(sel)
        if els:
            text = '\n\n'.join(e.get_text(separator=' ', strip=True) for e in els)
            if len(text.split()) >= 50:
                return text

    # Last resort: all long paragraphs
    paras = [p.get_text(strip=True) for p in soup.find_all('p') if len(p.get_text(strip=True)) > 60]
    return '\n\n'.join(paras)


def _extract_title(soup, selector=None):
    if selector:
        el = soup.select_one(selector)
        if el:
            return el.get_text(strip=True)[:500]
    for tag in ['h1', 'title']:
        el = soup.find(tag)
        if el:
            return el.get_text(strip=True)[:500]
    return ''


def _extract_date(soup, selector=None):
    if not selector:
        return None
    el = soup.select_one(selector)
    if not el:
        return None
    raw = el.get('datetime') or el.get('content') or el.get_text(strip=True)
    raw = raw[:30].strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw[:len(fmt) + 2], fmt)
        except ValueError:
            continue
    return None


def compute_hash(content: str) -> str:
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


def scrape_source(source) -> dict:
    """
    Scrape a Source object and return a result dict.
    Keys: success, content, title, content_hash, published_at, url, word_count, error
    """
    try:
        response = _fetch(source.url)
        soup = _clean_soup(BeautifulSoup(response.text, 'lxml'))

        content = _extract_content(soup, source.content_selector)
        title = _extract_title(soup, source.title_selector)
        published_at = _extract_date(soup, source.date_selector)

        word_count = len(content.split()) if content else 0
        if word_count < 50:
            return {
                'success': False,
                'error': (
                    f'Only {word_count} words extracted. '
                    'Try adjusting the content selector for this source.'
                )
            }

        return {
            'success': True,
            'title': title,
            'content': content,
            'content_hash': compute_hash(content),
            'published_at': published_at,
            'url': source.url,
            'word_count': word_count,
        }
    except Exception as e:
        logger.error('Error scraping %s: %s', source.url, e)
        return {'success': False, 'error': str(e)}


def validate_scrape(url, content_selector=None, title_selector=None, date_selector=None) -> dict:
    """
    Dry-run a scrape and return a preview without persisting anything.
    Used by the admin "Validate" button.
    """
    try:
        response = _fetch(url, timeout=20, retries=1)
        soup = _clean_soup(BeautifulSoup(response.text, 'lxml'))

        content = _extract_content(soup, content_selector)
        title = _extract_title(soup, title_selector)

        return {
            'success': True,
            'title': title,
            'content_preview': content[:1500] if content else '',
            'word_count': len(content.split()) if content else 0,
            'status_code': response.status_code,
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}
