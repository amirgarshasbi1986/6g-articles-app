# backend/searcher.py
import requests
import feedparser
from scholarly import scholarly
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from datetime import datetime, timedelta
import logging
import time
import urllib.parse
import arxiv
import os
import json
import pathlib   # <-- pathlib is back for the backup folder

# ----------------------------------------------------------------------
# API keys – try config.py first, then environment variables
# ----------------------------------------------------------------------
try:
    from backend.config import CORE_API_KEY, ELSEVIER_API_KEY
except ImportError:
    CORE_API_KEY = os.getenv('CORE_API_KEY', '')
    ELSEVIER_API_KEY = os.getenv('ELSEVIER_API_KEY', '')
    if not CORE_API_KEY:
        logging.getLogger(__name__).warning("CORE_API_KEY not set – CORE will be rate-limited")
    if not ELSEVIER_API_KEY:
        logging.getLogger(__name__).warning("ELSEVIER_API_KEY not set – ScienceDirect will be skipped")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------
# 6G keyword list
# ----------------------------------------------------------------------
G6_KEYWORDS = [
    '6G wireless communication',
    '6G terahertz communication',
    '6G ultra-massive MIMO',
    '6G integrated sensing and communication',
    '6G quantum communication',
    '6G AI-native networks',
    '6G holographic connectivity',
    '6G ultra-reliable low latency',
    '6G machine learning',
    '6G edge computing'
]

headers = {
    'User-Agent': '6G-Articles-App/1.0 (mailto:amir.gr86@gmail.com)',
    'Accept': 'application/json'
}

# ----------------------------------------------------------------------
# Helper – safe string conversion
# ----------------------------------------------------------------------
def _safe_str(val):
    return '' if val is None else str(val)

# ----------------------------------------------------------------------
# Search functions (unchanged except for safe strings & CORE key)
# ----------------------------------------------------------------------
def arxiv_search(query='6G', max_results=30):
    try:
        client = arxiv.Client()
        search = arxiv.Search(
            query=query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.Relevance,
            sort_order=arxiv.SortOrder.Descending
        )
        results = list(client.results(search))
        articles = []
        for r in results:
            authors = ', '.join([a.name for a in r.authors])
            if len(authors) > 1000:
                authors = authors[:950] + ' ... et al.'
            articles.append({
                'title': _safe_str(r.title),
                'authors': authors,
                'publish_date': r.published.date() if r.published else None,
                'link': f"http://arxiv.org/abs/{r.entry_id.split('/')[-1]}",
                'full_text': _safe_str(r.summary)
            })
        logger.info(f"arXiv fetched {len(articles)} articles for query '{query}'")
        return articles
    except Exception as e:
        logger.error(f"arXiv error for query '{query}': {e}")
        return []

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10),
       retry=retry_if_exception_type(requests.exceptions.HTTPError))
def semantic_search(query='6G wireless communication', max_results=30):
    url = 'https://api.semanticscholar.org/graph/v1/paper/search'
    params = {
        'query': urllib.parse.quote(query),
        'limit': max_results,
        'fields': 'title,authors,publicationDate,url,abstract',
        'sort': 'relevance'
    }
    try:
        resp = requests.get(url, params=params, timeout=10, headers=headers)
        if resp.status_code == 429:
            logger.warning(f"Semantic Scholar rate limit (429) for query '{query}'")
            return []
        resp.raise_for_status()
        data = resp.json()
        articles = []
        for p in data.get('data', []):
            authors = ', '.join(a['name'] for a in p.get('authors', []))
            if len(authors) > 1000:
                authors = authors[:950] + ' ... et al.'
            articles.append({
                'title': _safe_str(p.get('title')),
                'authors': authors,
                'publish_date': datetime.strptime(p['publicationDate'], '%Y-%m-%d').date()
                                if p.get('publicationDate') else None,
                'link': p.get('url') or '',
                'full_text': _safe_str(p.get('abstract'))
            })
        logger.info(f"Semantic Scholar fetched {len(articles)} articles for query '{query}'")
        return articles
    except Exception as e:
        logger.error(f"Semantic Scholar error for query '{query}': {e}")
        return []

def openalex_search(*_):
    logger.info("OpenAlex is disabled (403).")
    return []

def scholarly_search(query='6G wireless communication', max_results=30):
    try:
        articles = []
        for i, res in enumerate(scholarly.search_pubs(query)):
            if i >= max_results:
                break
            try:
                authors = ', '.join(res['bib'].get('author', []))
                if len(authors) > 1000:
                    authors = authors[:950] + ' ... et al.'
                articles.append({
                    'title': _safe_str(res['bib'].get('title')),
                    'authors': authors,
                    'publish_date': datetime.strptime(res['bib']['pub_year'], '%Y').date()
                                    if res['bib'].get('pub_year') else None,
                    'link': res.get('eprinturl') or res.get('pub_url') or '',
                    'full_text': _safe_str(res.get('abstract'))
                })
            except Exception as sub_e:
                logger.warning(f"Skipping malformed Scholar result: {sub_e}")
                continue
            time.sleep(1)
        logger.info(f"Google Scholar fetched {len(articles)} articles for query '{query}'")
        return articles
    except Exception as e:
        logger.error(f"Google Scholar error for query '{query}': {e}")
        return []

@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=4, max=60),
       retry=retry_if_exception_type(requests.exceptions.HTTPError))
def core_search(query='6G wireless communication', max_results=30):
    try:
        url = 'https://api.core.ac.uk/v3/search/works'
        params = {'q': query, 'limit': max_results}
        if CORE_API_KEY:
            params['apiKey'] = CORE_API_KEY
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        if resp.status_code == 429:
            logger.warning(f"CORE rate limit (429) for query '{query}'")
            raise requests.exceptions.HTTPError("429")
        resp.raise_for_status()
        data = resp.json()
        articles = []
        for item in data.get('results', []):
            authors_list = item.get('authors', [])
            authors = ', '.join(
                a.get('name', '') for a in authors_list
                if isinstance(a, dict) and a.get('name')
            )
            if not authors and isinstance(authors_list, list):
                authors = ', '.join(str(a) for a in authors_list if isinstance(a, str))
            if len(authors) > 1000:
                authors = authors[:950] + ' ... et al.'
            title = item.get('title', 'No title available')
            if title == 'No title available':
                logger.warning(f"Skipping CORE item without title (query: {query})")
                continue
            pub_date = item.get('publishedDate')
            date_obj = None
            if pub_date:
                try:
                    date_obj = datetime.strptime(pub_date, '%Y-%m-%dT%H:%M:%S').date()
                except ValueError:
                    try:
                        date_obj = datetime.strptime(pub_date, '%Y-%m-%d').date()
                    except ValueError:
                        logger.warning(f"Bad date format for CORE title '{title}': {pub_date}")
            articles.append({
                'title': title,
                'authors': authors,
                'publish_date': date_obj,
                'link': item.get('downloadUrl') or item.get('doi') or 'https://core.ac.uk',
                'full_text': _safe_str(item.get('abstract'))
            })
        logger.info(f"CORE fetched {len(articles)} articles for query '{query}'")
        return articles
    except Exception as e:
        logger.error(f"CORE error for query '{query}': {e}")
        return []

@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=4, max=60),
       retry=retry_if_exception_type(requests.exceptions.HTTPError))
def sciencedirect_search(query='6G wireless communication', max_results=30):
    if not ELSEVIER_API_KEY:
        logger.warning(f"ScienceDirect skipped (no API key) for query '{query}'")
        return []
    try:
        url = 'https://api.elsevier.com/content/search/sciencedirect'
        hd = headers.copy()
        hd['X-ELS-APIKey'] = ELSEVIER_API_KEY
        params = {'query': query, 'count': max_results}
        resp = requests.get(url, params=params, headers=hd, timeout=10)
        if resp.status_code == 429:
            logger.warning(f"ScienceDirect rate limit (429) for query '{query}'")
            raise requests.exceptions.HTTPError("429")
        resp.raise_for_status()
        data = resp.json()
        articles = []
        for item in data.get('search-results', {}).get('entry', []):
            title = item.get('dc:title', 'No title available')
            if title == 'No title available':
                logger.warning(f"Skipping ScienceDirect item without title (query: {query})")
                continue
            authors = ', '.join(a.get('creator', '') for a in item.get('authors', {}).get('author', []))
            if len(authors) > 1000:
                authors = authors[:950] + ' ... et al.'
            pub_date = item.get('prism:coverDate', '')
            date_obj = None
            if pub_date:
                try:
                    date_obj = datetime.strptime(pub_date, '%Y-%m-%d').date()
                except ValueError:
                    logger.warning(f"Bad date for ScienceDirect title '{title}': {pub_date}")
            articles.append({
                'title': title,
                'authors': authors,
                'publish_date': date_obj,
                'link': item.get('prism:doi') or item.get('link', [{}])[1].get('href', 'https://sciencedirect.com'),
                'full_text': _safe_str(item.get('dc:description'))
            })
        logger.info(f"ScienceDirect fetched {len(articles)} articles for query '{query}'")
        return articles
    except Exception as e:
        logger.error(f"ScienceDirect error for query '{query}': {e}")
        return []

def crossref_search(query='6G wireless communication', max_results=30):
    try:
        url = 'https://api.crossref.org/works'
        params = {'query': query, 'rows': max_results, 'sort': 'relevance'}
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        articles = []
        for item in data.get('message', {}).get('items', []):
            title = item.get('title', ['No title available'])
            title = title[0] if isinstance(title, list) and title else 'No title available'
            if title == 'No title available':
                logger.warning(f"Skipping Crossref item without title (query: {query})")
                continue
            authors = ', '.join(
                f"{a.get('family','')} {a.get('given','')}".strip()
                for a in item.get('author', []) if a.get('family')
            )
            if len(authors) > 1000:
                authors = authors[:950] + ' ... et al.'
            pub_year = item.get('published', {}).get('date-parts', [[None]])[0][0]
            articles.append({
                'title': title,
                'authors': authors,
                'publish_date': datetime.strptime(str(pub_year), '%Y').date() if pub_year else None,
                'link': item.get('URL', 'https://crossref.org'),
                'full_text': _safe_str(item.get('abstract'))
            })
        logger.info(f"Crossref fetched {len(articles)} articles for query '{query}'")
        return articles
    except Exception as e:
        logger.error(f"Crossref error for query '{query}': {e}")
        return []

# ----------------------------------------------------------------------
# Unpaywall enrichment (unchanged)
# ----------------------------------------------------------------------
def unpaywall_enrich(articles):
    enriched = []
    for a in articles:
        doi = a['link'].split('abs/')[-1] if 'arxiv' in a['link'] else None
        if doi:
            try:
                url = f'https://api.unpaywall.org/v2/{doi}?email=amir.gr86@gmail.com'
                r = requests.get(url, timeout=5)
                if r.status_code == 200:
                    data = r.json()
                    oa = data.get('best_oa_location', {}).get('url_for_pdf')
                    if oa:
                        a['link'] = oa
                        logger.info(f"Unpaywall enriched {a['title'][:50]}")
            except Exception as e:
                logger.error(f"Unpaywall error for {a['title'][:50]}: {e}")
        enriched.append(a)
    return enriched

# ----------------------------------------------------------------------
# Improved relevance scoring – partial keyword match + title boost
# ----------------------------------------------------------------------
def calculate_relevance(article):
    title = article.get('title', '').lower()
    full_text = article.get('full_text', '').lower()
    text = title + ' ' + full_text

    # Split each keyword into its words and count any occurrence
    score = 0
    for kw in G6_KEYWORDS:
        kw_words = kw.lower().split()
        for w in kw_words:
            if w in text:
                score += 1
                break   # count the keyword only once

    # Give a big boost if the keyword appears in the title
    for kw in G6_KEYWORDS:
        if kw.lower() in title:
            score += 3

    return score

# ----------------------------------------------------------------------
# MAIN weekly search – backup + 180-day recent window
# ----------------------------------------------------------------------
def weekly_search():
    all_articles = []
    for kw in G6_KEYWORDS:
        all_articles += arxiv_search(kw, max_results=30)
        all_articles += semantic_search(kw, max_results=30)
        all_articles += core_search(kw, max_results=30)
        all_articles += crossref_search(kw, max_results=30)
        all_articles += sciencedirect_search(kw, max_results=30)
        time.sleep(5)          # be gentle to all APIs

    all_articles += scholarly_search(G6_KEYWORDS[0], max_results=30)

    # -------------------------------------------------
    # Deduplicate
    # -------------------------------------------------
    seen = set()
    unique = []
    for a in all_articles:
        key = (a.get('title', ''), a.get('link', ''))
        if key not in seen:
            seen.add(key)
            a['relevance_score'] = calculate_relevance(a)
            unique.append(a)

    # -------------------------------------------------
    # BACKUP – all unique articles
    # -------------------------------------------------
    backup_dir = pathlib.Path("backend/backup")
    backup_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now()
    week_num = now.isocalendar()[1]
    backup_path = backup_dir / f"allresult_week_{now.year}-{week_num:02d}.json"

    with open(backup_path, "w", encoding="utf-8") as f:
        json.dump(unique, f, indent=2, default=str)
    logger.info(f"BACKUP: {len(unique)} unique articles saved to {backup_path}")

    # -------------------------------------------------
    # Filter for recent papers – 365 days
    # -------------------------------------------------
    recent_cutoff = now - timedelta(days=365)
    recent = [a for a in unique
              if a.get('publish_date') and a['publish_date'] >= recent_cutoff.date()]

    # If we have fewer than 50 recent, fill with highest-scored older ones
    if len(recent) < 50:
        older = [a for a in unique
                 if a.get('publish_date') and a['publish_date'] < recent_cutoff.date()]
        older.sort(key=lambda x: x['relevance_score'], reverse=True)
        recent += older[:50 - len(recent)]
    else:
        recent = recent[:50]

    recent = unpaywall_enrich(recent)

    logger.info(
        f"Fetched {len(all_articles)} total, {len(unique)} unique. "
        f"Kept {len(recent)} recent/relevant articles for DB."
    )
    return recent
