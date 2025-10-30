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
import pathlib

# Try to import ELSEVIER_API_KEY from config.py or environment
try:
    from backend.config import ELSEVIER_API_KEY
except ImportError:
    ELSEVIER_API_KEY = os.getenv('ELSEVIER_API_KEY', '')
    if not ELSEVIER_API_KEY:
        logger.warning("ELSEVIER_API_KEY not found in config.py or environment; ScienceDirect search will be skipped")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

def arxiv_search(query='6G', max_results=20):
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
        for result in results:
            authors = ', '.join([author.name for author in result.authors])
            if len(authors) > 1000:
                authors = authors[:950] + ' ... et al.'
            articles.append({
                'title': result.title or 'No title available',
                'authors': authors,
                'publish_date': result.published.date() if result.published else None,
                'link': f"http://arxiv.org/abs/{result.entry_id.split('/')[-1]}",
                'full_text': result.summary or ''
            })
        logger.info(f"arXiv fetched {len(articles)} articles for query '{query}'")
        return articles
    except Exception as e:
        logger.error(f"arXiv error for query '{query}': {e}")
        return []

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10), retry=retry_if_exception_type(requests.exceptions.HTTPError))
def semantic_search(query='6G wireless communication', max_results=20):
    url = 'https://api.semanticscholar.org/graph/v1/paper/search'
    params = {'query': urllib.parse.quote(query), 'limit': max_results, 'fields': 'title,authors,publicationDate,url,abstract', 'sort': 'relevance'}
    try:
        response = requests.get(url, params=params, timeout=10, headers=headers)
        if response.status_code == 429:
            logger.warning(f"Semantic Scholar rate limit (429) for query '{query}', returning empty list")
            return []
        response.raise_for_status()
        data = response.json()
        articles = []
        for p in data.get('data', []):
            authors = ', '.join(a['name'] for a in p.get('authors', []))
            if len(authors) > 1000:
                authors = authors[:950] + ' ... et al.'
            articles.append({
                'title': p['title'] or 'No title available',
                'authors': authors,
                'publish_date': datetime.strptime(p['publicationDate'], '%Y-%m-%d').date() if p.get('publicationDate') else None,
                'link': p['url'] or 'https://semanticscholar.org',
                'full_text': p['abstract'] or ''
            })
        logger.info(f"Semantic Scholar fetched {len(articles)} articles for query '{query}'")
        return articles
    except requests.exceptions.HTTPError as e:
        if response.status_code == 429:
            logger.warning(f"Semantic Scholar rate limit (429) for query '{query}', returning empty list")
            return []
        logger.error(f"Semantic Scholar error for query '{query}': {e}")
        raise
    except Exception as e:
        logger.error(f"Semantic Scholar error for query '{query}': {e}")
        return []

def openalex_search(query='6G wireless communication', max_results=20):
    logger.info(f"Skipping OpenAlex for query '{query}' due to persistent 403 errors")
    return []

def scholarly_search(query='6G wireless communication', max_results=20):
    try:
        search_query = scholarly.search_pubs(query)
        articles = []
        for i, result in enumerate(search_query):
            if i >= max_results:
                break
            try:
                authors = ', '.join(result['bib']['author'] or [])
                if len(authors) > 1000:
                    authors = authors[:950] + ' ... et al.'
                title = result['bib']['title'] or 'No title available'
                pub_year = result['bib'].get('pub_year')
                publish_date = datetime.strptime(pub_year, '%Y').date() if pub_year else None
                link = result.get('eprinturl', result.get('pub_url', ''))
                full_text = result.get('abstract', '') or ''
                articles.append({
                    'title': title,
                    'authors': authors,
                    'publish_date': publish_date,
                    'link': link or 'https://scholar.google.com',
                    'full_text': full_text
                })
            except Exception as e:
                logger.warning(f"Skipping invalid Google Scholar result for query '{query}': {e}")
                continue
            time.sleep(1)  # Avoid rate limits
        logger.info(f"Google Scholar fetched {len(articles)} articles for query '{query}'")
        return articles
    except Exception as e:
        logger.error(f"Google Scholar error for query '{query}': {e}")
        return []

@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=4, max=60), retry=retry_if_exception_type(requests.exceptions.HTTPError))
def core_search(query='6G wireless communication', max_results=20):
    try:
        url = 'https://api.core.ac.uk/v3/search/works'
        params = {'q': query, 'limit': max_results}
        response = requests.get(url, params=params, headers=headers, timeout=10)
        if response.status_code == 429:
            logger.warning(f"CORE rate limit (429) for query '{query}', retrying after backoff")
            raise requests.exceptions.HTTPError("429")
        response.raise_for_status()
        data = response.json()
        articles = []
        for item in data.get('results', []):
            authors_list = item.get('authors', [])
            authors = ', '.join(a.get('name', '') for a in authors_list if isinstance(a, dict) and a.get('name'))
            if not authors and isinstance(authors_list, list):
                authors = ', '.join(str(a) for a in authors_list if isinstance(a, str))
            if len(authors) > 1000:
                authors = authors[:950] + ' ... et al.'
            title = item.get('title', 'No title available')
            if title == 'No title available':
                logger.warning(f"Skipping CORE item with no title for query '{query}'")
                continue
            publish_date = item.get('publishedDate')
            date_obj = None
            if publish_date:
                try:
                    date_obj = datetime.strptime(publish_date, '%Y-%m-%dT%H:%M:%S').date()
                except ValueError:
                    try:
                        date_obj = datetime.strptime(publish_date, '%Y-%m-%d').date()
                    except ValueError:
                        logger.warning(f"Invalid date format for CORE item '{title}': {publish_date}")
                        date_obj = None
            articles.append({
                'title': title,
                'authors': authors,
                'publish_date': date_obj,
                'link': item.get('downloadUrl', item.get('doi', '')) or 'https://core.ac.uk',
                'full_text': item.get('abstract', '') or ''
            })
        logger.info(f"CORE fetched {len(articles)} articles for query '{query}'")
        return articles
    except Exception as e:
        logger.error(f"CORE error for query '{query}': {e}")
        return []

@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=4, max=60), retry=retry_if_exception_type(requests.exceptions.HTTPError))
def sciencedirect_search(query='6G wireless communication', max_results=20):
    if not ELSEVIER_API_KEY:
        logger.warning(f"ScienceDirect error: No API key provided for query '{query}', skipping")
        return []
    try:
        url = 'https://api.elsevier.com/content/search/sciencedirect'
        headers_sd = headers.copy()
        headers_sd['X-ELS-APIKey'] = ELSEVIER_API_KEY
        params = {'query': query, 'count': max_results}
        response = requests.get(url, params=params, headers=headers_sd, timeout=10)
        if response.status_code == 429:
            logger.warning(f"ScienceDirect rate limit (429) for query '{query}', retrying after backoff")
            raise requests.exceptions.HTTPError("429")
        response.raise_for_status()
        data = response.json()
        articles = []
        for item in data.get('search-results', {}).get('entry', []):
            title = item.get('dc:title', 'No title available')
            if title == 'No title available':
                logger.warning(f"Skipping ScienceDirect item with no title for query '{query}'")
                continue
            authors = ', '.join(a.get('creator', '') for a in item.get('authors', {}).get('author', []))
            if len(authors) > 1000:
                authors = authors[:950] + ' ... et al.'
            publish_date = item.get('prism:coverDate', '')
            date_obj = None
            if publish_date:
                try:
                    date_obj = datetime.strptime(publish_date, '%Y-%m-%d').date()
                except ValueError:
                    logger.warning(f"Invalid date format for ScienceDirect item '{title}': {publish_date}")
                    date_obj = None
            articles.append({
                'title': title,
                'authors': authors,
                'publish_date': date_obj,
                'link': item.get('prism:doi', '') or item.get('link', [{}])[1].get('href', 'https://sciencedirect.com'),
                'full_text': item.get('dc:description', '') or ''
            })
        logger.info(f"ScienceDirect fetched {len(articles)} articles for query '{query}'")
        return articles
    except Exception as e:
        logger.error(f"ScienceDirect error for query '{query}': {e}")
        return []

def crossref_search(query='6G wireless communication', max_results=20):
    try:
        url = 'https://api.crossref.org/works'
        params = {'query': query, 'rows': max_results, 'sort': 'relevance'}
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        articles = []
        for item in data.get('message', {}).get('items', []):
            title = item.get('title', ['No title available'])
            if isinstance(title, list):
                title = title[0] if title else 'No title available'
            if title == 'No title available':
                logger.warning(f"Skipping Crossref item with no title for query '{query}'")
                continue
            authors = ', '.join(a.get('family', '') + ' ' + a.get('given', '') for a in item.get('author', []) if a.get('family'))
            if len(authors) > 1000:
                authors = authors[:950] + ' ... et al.'
            publish_date = item.get('published', {}).get('date-parts', [[None]])[0][0]
            articles.append({
                'title': title,
                'authors': authors,
                'publish_date': datetime.strptime(str(publish_date), '%Y').date() if publish_date else None,
                'link': item.get('URL', 'https://crossref.org'),
                'full_text': item.get('abstract', '') or ''
            })
        logger.info(f"Crossref fetched {len(articles)} articles for query '{query}'")
        return articles
    except Exception as e:
        logger.error(f"Crossref error for query '{query}': {e}")
        return []

def unpaywall_enrich(articles):
    enriched = []
    for a in articles:
        doi = a['link'].split('abs/')[-1] if 'arxiv' in a['link'] else None
        if doi:
            try:
                url = f'https://api.unpaywall.org/{doi}?email=amir.gr86@gmail.com'
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    oa_url = data.get('best_oa_location', {}).get('url_for_pdf', a['link'])
                    a['link'] = oa_url
                    logger.info(f"Unpaywall enriched link for {a['title'][:50]}")
            except Exception as e:
                logger.error(f"Unpaywall error for {a['title'][:50]}: {e}")
        enriched.append(a)
    return enriched

def calculate_relevance(article):
    title = article.get('title', '').lower() or ''
    full_text = article.get('full_text', '').lower() or ''
    text = title + ' ' + full_text
    score = 0
    for kw in G6_KEYWORDS:
        if kw.lower() in text:
            score += 1
    return score
# -----------------------------------------------------------------
# 1. Increase the “recent” window – 90 days instead of 30
# -----------------------------------------------------------------
def weekly_search():
    all_articles = []
    selected_keywords = G6_KEYWORDS
    for keyword in selected_keywords:
        all_articles += arxiv_search(keyword)
        all_articles += semantic_search(keyword)
        all_articles += core_search(keyword)
        all_articles += crossref_search(keyword)
        all_articles += sciencedirect_search(keyword)
        time.sleep(5)

    all_articles += scholarly_search(G6_KEYWORDS[0])

    # -------------------------------------------------------------
    # 2. Deduplicate + relevance score
    # -------------------------------------------------------------
    seen = set()
    unique = []
    for a in all_articles:
        key = (a.get('title', ''), a.get('link', ''))
        if key not in seen:
            seen.add(key)
            a['relevance_score'] = calculate_relevance(a)
            unique.append(a)

    # -------------------------------------------------------------
    # 3. **BACKUP** – dump *every* unique article
    # -------------------------------------------------------------
    backup_dir = pathlib.Path("backend/backup")
    backup_dir.mkdir(parents=True, exist_ok=True)

    week_str = datetime.now().isocalendar()[1]   # e.g. 44
    year     = datetime.now().year
    backup_path = backup_dir / f"allresult_week_{year}-{week_str:02d}.json"

    with open(backup_path, "w", encoding="utf-8") as f:
        json.dump(unique, f, indent=2, default=str)
    logger.info(f"BACKUP: {len(unique)} unique articles written to {backup_path}")

    # -------------------------------------------------------------
    # 4. Filter for *recent* papers (now 90 days)
    # -------------------------------------------------------------
    ninety_days_ago = datetime.now() - timedelta(days=90)   # <-- changed
    recent = [a for a in unique
              if a.get('publish_date') and a['publish_date'] >= ninety_days_ago.date()]

    # If we still have less than 10, fall back to the highest-scored older ones
    if len(recent) < 10:
        older = [a for a in unique
                 if a.get('publish_date') and a['publish_date'] < ninety_days_ago.date()]
        older = sorted(older, key=lambda x: x['relevance_score'], reverse=True)
        recent += older[:10 - len(recent)]
    else:
        recent = recent[:10]

    recent = unpaywall_enrich(recent)
    logger.info(f"Fetched {len(all_articles)} total, {len(unique)} unique. "
                f"Kept {len(recent)} recent/relevant articles for DB")
    return recent
