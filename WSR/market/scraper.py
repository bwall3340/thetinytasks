"""
Web scraping utilities for market commentary sources.
Supports HTML pages (with configurable CSS selectors) and PDF documents
(both direct PDF URLs and PDFs linked from an HTML page).
"""
import hashlib
import io
import logging
import time
from urllib.parse import urljoin, urlparse

import pdfplumber
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

# Keywords that suggest a link points to a relevant PDF report
_PDF_LINK_KEYWORDS = {
    'download', 'pdf', 'report', 'outlook', 'commentary', 'monthly',
    'quarterly', 'annual', 'weekly', 'letter', 'insight', 'strategy',
    'perspective', 'view', 'update', 'review', 'forecast',
}

_PDF_MAX_PAGES = 30
_PDF_MAX_BYTES = 50 * 1024 * 1024  # 50 MB


# ── Fetch ─────────────────────────────────────────────────────────────────────

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


def _is_pdf_response(response) -> bool:
    content_type = response.headers.get('Content-Type', '')
    return 'pdf' in content_type or response.url.lower().endswith('.pdf')


def _is_pdf_url(url: str) -> bool:
    return urlparse(url).path.lower().endswith('.pdf')


# ── PDF extraction ────────────────────────────────────────────────────────────

def _extract_pdf_text(pdf_bytes: bytes) -> str:
    """Extract plain text from PDF bytes using pdfplumber."""
    pages = []
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages[:_PDF_MAX_PAGES]:
                text = page.extract_text()
                if text and text.strip():
                    pages.append(text.strip())
    except Exception as e:
        logger.warning('pdfplumber error: %s', e)
    return '\n\n'.join(pages)


def _title_from_pdf(pdf_bytes: bytes) -> str:
    """Try to read the PDF Title metadata field."""
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            meta = pdf.metadata or {}
            return (meta.get('Title') or '').strip()[:500]
    except Exception:
        return ''


# ── PDF link discovery ────────────────────────────────────────────────────────

def _score_pdf_link(href: str, link_text: str) -> int:
    """Score a PDF link by relevance. Higher = more likely to be the report."""
    score = 0
    combined = (href + ' ' + link_text).lower()
    for kw in _PDF_LINK_KEYWORDS:
        if kw in combined:
            score += 1
    return score


def _find_pdf_links(soup: BeautifulSoup, base_url: str) -> list:
    """
    Find PDF links on an HTML page, ranked by relevance.
    Returns a list of absolute PDF URLs (best first).
    """
    candidates = []
    for a in soup.find_all('a', href=True):
        href = a['href'].strip()
        text = a.get_text(strip=True)
        if not href or href.startswith('#') or href.startswith('mailto:'):
            continue
        abs_href = urljoin(base_url, href)
        if _is_pdf_url(abs_href):
            score = _score_pdf_link(abs_href, text)
            candidates.append((score, abs_href))

    candidates.sort(key=lambda x: x[0], reverse=True)
    return [url for _, url in candidates]


# ── Article link discovery ────────────────────────────────────────────────────

def _find_article_link(soup: BeautifulSoup, base_url: str, selector: str):
    """
    Return the absolute URL of the first link matching `selector` on a listing page.
    If the matched element is not an <a>, look for the first <a> inside it.
    Returns None (with a warning) if the selector is invalid CSS.
    """
    try:
        el = soup.select_one(selector)
    except Exception as e:
        logger.warning('Invalid article_link_selector %r: %s', selector, e)
        return None
    if not el:
        return None
    if el.name == 'a':
        href = el.get('href', '').strip()
    else:
        a = el.find('a')
        href = (a.get('href', '').strip() if a else '')
    if not href or href.startswith('#') or href.startswith('mailto:'):
        return None
    return urljoin(base_url, href)


# ── HTML extraction ───────────────────────────────────────────────────────────

def _clean_soup(soup):
    for tag in soup.find_all(['nav', 'footer', 'header', 'script', 'style',
                               'aside', 'form', 'iframe', 'noscript']):
        tag.decompose()
    return soup


def _extract_content(soup, selector=None):
    if selector:
        try:
            els = soup.select(selector)
        except Exception as e:
            logger.warning('Invalid content_selector %r: %s', selector, e)
            els = []
        if els:
            return '\n\n'.join(e.get_text(separator=' ', strip=True) for e in els)

    for sel in _CONTENT_FALLBACKS:
        els = soup.select(sel)
        if els:
            text = '\n\n'.join(e.get_text(separator=' ', strip=True) for e in els)
            if len(text.split()) >= 50:
                return text

    paras = [p.get_text(strip=True) for p in soup.find_all('p') if len(p.get_text(strip=True)) > 60]
    return '\n\n'.join(paras)


def _extract_title(soup, selector=None):
    if selector:
        try:
            el = soup.select_one(selector)
        except Exception as e:
            logger.warning('Invalid title_selector %r: %s', selector, e)
            el = None
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
    try:
        el = soup.select_one(selector)
    except Exception as e:
        logger.warning('Invalid date_selector %r: %s', selector, e)
        return None
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


# ── Hash ──────────────────────────────────────────────────────────────────────

def compute_hash(content: str) -> str:
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


# ── Internal PDF URL scraper ──────────────────────────────────────────────────

def _scrape_pdf_bytes(pdf_url: str) -> dict:
    """Download and parse a PDF URL. Returns partial result dict."""
    response = _fetch(pdf_url)
    if len(response.content) > _PDF_MAX_BYTES:
        return {'success': False, 'error': f'PDF too large (>{_PDF_MAX_BYTES // 1024 // 1024} MB)'}

    content = _extract_pdf_text(response.content)
    word_count = len(content.split()) if content else 0
    if word_count < 50:
        return {'success': False,
                'error': f'PDF extracted only {word_count} words (may be image-based or encrypted)'}

    title = _title_from_pdf(response.content)
    return {'success': True, 'content': content, 'title': title, 'word_count': word_count}


# ── Public API ────────────────────────────────────────────────────────────────

def scrape_source(source) -> dict:
    """
    Scrape a Source object. Automatically handles:
      - Direct PDF URLs
      - HTML pages that link to PDFs  (prefers PDF when it has more content)
      - Plain HTML pages

    Returns dict with keys: success, content, title, content_hash,
    published_at, url, word_count, source_type, [pdf_url], [error]
    """
    try:
        response = _fetch(source.url)

        # ── Case 1: direct PDF ────────────────────────────────────────────────
        if _is_pdf_response(response):
            content = _extract_pdf_text(response.content)
            word_count = len(content.split()) if content else 0
            if word_count < 50:
                return {'success': False,
                        'error': f'PDF extracted only {word_count} words (may be image-based or encrypted)'}
            title = _title_from_pdf(response.content)
            return {
                'success': True,
                'title': title,
                'content': content,
                'content_hash': compute_hash(content),
                'published_at': None,
                'url': source.url,
                'word_count': word_count,
                'source_type': 'pdf_direct',
            }

        # ── Cases 2 & 3: HTML page ────────────────────────────────────────────
        soup = _clean_soup(BeautifulSoup(response.text, 'lxml'))
        scraped_url = source.url

        # If the source is a listing page, follow the first article link
        article_link_selector = getattr(source, 'article_link_selector', None)
        if article_link_selector:
            article_url = _find_article_link(soup, source.url, article_link_selector)
            if article_url:
                try:
                    article_resp = _fetch(article_url)
                    if _is_pdf_response(article_resp):
                        content = _extract_pdf_text(article_resp.content)
                        word_count = len(content.split()) if content else 0
                        if word_count < 50:
                            return {'success': False,
                                    'error': f'PDF at article link extracted only {word_count} words'}
                        title = _title_from_pdf(article_resp.content)
                        return {
                            'success': True, 'title': title, 'content': content,
                            'content_hash': compute_hash(content), 'published_at': None,
                            'url': article_url, 'word_count': word_count,
                            'source_type': 'pdf_direct',
                        }
                    soup = _clean_soup(BeautifulSoup(article_resp.text, 'lxml'))
                    scraped_url = article_url
                except Exception as e:
                    logger.warning('Failed to follow article link %s: %s', article_url, e)

        pdf_links = _find_pdf_links(soup, scraped_url)

        # Try linked PDFs (top 3 ranked candidates)
        pdf_result = None
        used_pdf_url = None
        for pdf_url in pdf_links[:3]:
            try:
                r = _scrape_pdf_bytes(pdf_url)
                if r['success']:
                    pdf_result = r
                    used_pdf_url = pdf_url
                    break
            except Exception as e:
                logger.debug('PDF link %s failed: %s', pdf_url, e)

        html_content = _extract_content(soup, source.content_selector)
        html_title = _extract_title(soup, source.title_selector)
        published_at = _extract_date(soup, source.date_selector)

        html_words = len(html_content.split()) if html_content else 0
        pdf_words = pdf_result['word_count'] if pdf_result else 0

        # Prefer PDF when it has more content
        if pdf_result and pdf_words >= html_words:
            content = pdf_result['content']
            title = pdf_result['title'] or html_title
            source_type = 'pdf_linked'
        else:
            content = html_content
            title = html_title
            source_type = 'html'

        word_count = len(content.split()) if content else 0
        if word_count < 50:
            detail = f'HTML: {html_words} words'
            if pdf_links:
                detail += f', {len(pdf_links)} PDF link(s) found'
                if pdf_result is None:
                    detail += ' but none parsed successfully'
            return {'success': False,
                    'error': f'Only {word_count} words extracted. {detail}. Try adjusting the content selector.'}

        result = {
            'success': True,
            'title': title,
            'content': content,
            'content_hash': compute_hash(content),
            'published_at': published_at,
            'url': scraped_url,
            'word_count': word_count,
            'source_type': source_type,
        }
        if used_pdf_url:
            result['pdf_url'] = used_pdf_url
        return result

    except Exception as e:
        logger.error('Error scraping %s: %s', source.url, e)
        return {'success': False, 'error': str(e)}


def validate_scrape(url, content_selector=None, title_selector=None,
                    date_selector=None, article_link_selector=None) -> dict:
    """
    Dry-run scrape for the admin Validate button. Never persists anything.
    """
    try:
        response = _fetch(url, timeout=20, retries=1)

        if _is_pdf_response(response):
            content = _extract_pdf_text(response.content)
            title = _title_from_pdf(response.content)
            return {
                'success': True,
                'source_type': 'pdf_direct',
                'title': title,
                'content_preview': content[:1500],
                'word_count': len(content.split()) if content else 0,
                'status_code': response.status_code,
                'pdf_links_found': 0,
            }

        soup = _clean_soup(BeautifulSoup(response.text, 'lxml'))
        article_url_followed = None

        # If article_link_selector is configured, follow the first matching link
        if article_link_selector:
            article_url = _find_article_link(soup, url, article_link_selector)
            if article_url:
                try:
                    art_resp = _fetch(article_url, timeout=20, retries=1)
                    if _is_pdf_response(art_resp):
                        content = _extract_pdf_text(art_resp.content)
                        title = _title_from_pdf(art_resp.content)
                        return {
                            'success': True,
                            'source_type': 'pdf_direct',
                            'title': title,
                            'content_preview': content[:1500],
                            'word_count': len(content.split()) if content else 0,
                            'status_code': art_resp.status_code,
                            'pdf_links_found': 0,
                            'article_url_followed': article_url,
                        }
                    soup = _clean_soup(BeautifulSoup(art_resp.text, 'lxml'))
                    url = article_url
                    article_url_followed = article_url
                except Exception as e:
                    logger.warning('validate: failed to follow article link %s: %s', article_url, e)

        pdf_links = _find_pdf_links(soup, url)
        html_content = _extract_content(soup, content_selector)
        html_title = _extract_title(soup, title_selector)

        # Try the top PDF link for the preview
        pdf_preview = None
        pdf_url_used = None
        for pdf_url in pdf_links[:2]:
            try:
                r = _fetch(pdf_url, timeout=15, retries=1)
                text = _extract_pdf_text(r.content)
                if len(text.split()) >= 50:
                    pdf_preview = text[:1500]
                    pdf_url_used = pdf_url
                    break
            except Exception:
                pass

        html_words = len(html_content.split()) if html_content else 0
        pdf_words = len(pdf_preview.split()) if pdf_preview else 0

        if pdf_preview and pdf_words >= html_words:
            source_type = 'pdf_linked'
            content_preview = pdf_preview
            word_count = pdf_words
        else:
            source_type = 'html'
            content_preview = html_content[:1500] if html_content else ''
            word_count = html_words

        result = {
            'success': True,
            'source_type': source_type,
            'title': html_title,
            'content_preview': content_preview,
            'word_count': word_count,
            'status_code': response.status_code,
            'pdf_links_found': len(pdf_links),
            'pdf_url_used': pdf_url_used,
            'pdf_links': pdf_links[:5],
        }
        if article_url_followed:
            result['article_url_followed'] = article_url_followed
        return result

    except Exception as e:
        return {'success': False, 'error': str(e)}
