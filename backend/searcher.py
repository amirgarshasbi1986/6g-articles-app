import requests
import feedparser
from scholarly import scholarly
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from datetime import datetime, timedelta
import logging
import time
import urllib.parse
import arxiv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Reduced to top 10 keywords to avoid Semantic Scholar rate limit
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
                'title': result.title,
                'authors': authors,
                'publish_date': result.published.date() if result.published else None,
                'link': f"http://arxiv.org/abs/{result.entry_id.split('/')[-1]}",
                'full_text': result.summary
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
                'title': p['title'],
                'authors': authors,
                'publish_date': datetime.strptime(p['publicationDate'], '%Y-%m-%d').date() if p.get('publicationDate') else None,
                'link': p['url'],
                'full_text': p['abstract']
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
            authors = ', '.join(result['bib']['author'] or [])
            if len(authors) > 1000:
                authors = authors[:950] + ' ... et al.'
            articles.append({
                'title': result['bib']['title'],
                'authors': authors,
                'publish_date': datetime.strptime(result['bib']['pub_year'], '%Y').date() if result['bib'].get('pub_year') else None,
                'link': result.get('eprinturl', result['pub_url']),
                'full_text': result.get('abstract', '')
            })
            time.sleep(1)
        logger.info(f"Google Scholar fetched {len(articles)} articles for query '{query}'")
        return articles
    except Exception as e:
        logger.error(f"Google Scholar error for query '{query}': {e}")
        return []

def core_search(query='6G wireless communication', max_results=20):
    try:
        url = 'https://api.core.ac.uk/v3/search/works'
        params = {'q': query, 'limit': max_results}
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        articles = []
        for item in data.get('results', []):
            # Handle authors as list of dicts
            authors_list = item.get('authors', [])
            authors = ', '.join(a.get('name', '') for a in authors_list if isinstance(a, dict) and a.get('name'))
            if not authors and isinstance(authors_list, list):
                authors = ', '.join(str(a) for a in authors_list if isinstance(a, str))  # Fallback for string list
            if len(authors) > 1000:
                authors = authors[:950] + ' ... et al.'
            title = item.get('title', 'No title available')
            if not title:
                logger.warning(f"Skipping CORE item with no title for query '{query}'")
                continue
            articles.append({
                'title': title,
                'authors': authors,
                'publish_date': datetime.strptime(item['publishedDate'], '%Y-%m-%d').date() if item.get('publishedDate') else None,
                'link': item.get('downloadUrl', item.get('doi', '')) or 'https://core.ac.uk',
                'full_text': item.get('abstract', '')
            })
        logger.info(f"CORE fetched {len(articles)} articles for query '{query}'")
        return articles
    except Exception as e:
        logger.error(f"CORE error for query '{query}': {e}")
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
                'full_text': item.get('abstract', '')
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
    title = article['title'].lower()
    full_text = article['full_text'].lower()
    text = title + ' ' + full_text
    score = 0
    for kw in G6_KEYWORDS:
        if kw.lower() in text:
            score += 1
    return score

def weekly_search():
    all_articles = []
    selected_keywords = G6_KEYWORDS  # Now 10 keywords
    for keyword in selected_keywords:
        all_articles += arxiv_search(keyword)
        all_articles += semantic_search(keyword)
        all_articles += core_search(keyword)
        all_articles += crossref_search(keyword)
        time.sleep(5)

    all_articles += scholarly_search(G6_KEYWORDS[0])

    seen = set()
    unique = []
    one_month_ago = datetime.now() - timedelta(days=30)
    for a in all_articles:
        key = (a['title'], a.get('link', ''))
        if key not in seen:
            seen.add(key)
            a['relevance_score'] = calculate_relevance(a)
            unique.append(a)

    unique = sorted(unique, key=lambda x: x['relevance_score'], reverse=True)
    recent = [a for a in unique if a.get('publish_date') and a['publish_date'] >= one_month_ago.date()]
    if len(recent) < 10:
        additional = [a for a in unique if a.get('publish_date') and a['publish_date'] < one_month_ago.date()][:10 - len(recent)]
        recent += additional
    else:
        recent = recent[:10]

    recent = unpaywall_enrich(recent)
    logger.info(f"Fetched {len(all_articles)} total articles, {len(unique)} unique after dedup. Filtered to {len(recent)} recent/relevant articles")
    return recent
