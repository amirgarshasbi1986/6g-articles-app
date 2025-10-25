import requests
import feedparser
from scholarly import scholarly
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from datetime import datetime, timedelta
import logging
import time
import urllib.parse
import arxiv
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

G6_KEYWORDS = [
    '6G wireless communication',
    '6G terahertz communication',
    '6G ultra-massive MIMO',
    '6G integrated sensing and communication',
    '6G quantum communication',
    '6G dynamic spectrum sharing',
    '6G AI-native networks',
    '6G holographic connectivity',
    '6G ubiquitous connectivity',
    '6G deep connectivity',
    '6G intelligent connectivity',
    '6G THz bands',
    '6G in-band full-duplex',
    '6G visible light communication',
    '6G orbital angular momentum',
    '6G energy efficiency',
    '6G ultra-reliable low latency',
    '6G ultra-high reliability',
    '6G spectral efficiency',
    '6G machine learning',
    '6G edge computing',
    '6G quantum key distribution',
    '6G backscatter communications',
    '6G multiuser MIMO',
    '6G post-quantum security'
]

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1'
}

def arxiv_search(query='6G', max_results=10):
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
def semantic_search(query='6G wireless communication', max_results=10):
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

def openalex_search(query='6G wireless communication', max_results=10):
    logger.info(f"Skipping OpenAlex for query '{query}' due to persistent 403 errors")
    return []

def scholarly_search(query='6G wireless communication', max_results=10):
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

def flexible_scrape_sciencedirect(query='6G wireless communication', max_results=10):
    try:
        search_url = f"https://www.sciencedirect.com/search?qs={urllib.parse.quote(query)}"
        response = requests.get(search_url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        results = soup.find_all('li', class_='js-result-item', limit=max_results)
        articles = []
        for result in results:
            title_elem = result.find('a', class_='js-article-title')
            title = title_elem.text.strip() if title_elem else 'No title'
            link = 'https://www.sciencedirect.com' + title_elem['href'] if title_elem else 'No link'
            authors_elem = result.find('ol', class_='Authors')
            authors = ', '.join(span.text for span in authors_elem.find_all('span', class_='content')) if authors_elem else 'No authors'
            date_elem = result.find('span', class_='js-publication-year')
            date = date_elem.text.strip() if date_elem else 'No date'
            abstract_elem = result.find('p', class_='js-abstract-truncated-text')
            abstract = abstract_elem.text.strip() if abstract_elem else 'No abstract'

            # To get full abstract, fetch article page
            if link != 'No link':
                try:
                    article_response = requests.get(link, headers=headers, timeout=10)
                    article_soup = BeautifulSoup(article_response.text, 'html.parser')
                    full_abstract_elem = article_soup.find('div', class_='Abstracts u-font-serif')
                    full_abstract = full_abstract_elem.text.strip() if full_abstract_elem else abstract
                except Exception as e:
                    logger.warning(f"Failed to fetch full abstract for '{title}': {e}")
                    full_abstract = abstract
            else:
                full_abstract = abstract

            articles.append({
                'title': title,
                'authors': authors,
                'publish_date': date,
                'link': link,
                'full_text': full_abstract
            })
        logger.info(f"ScienceDirect scraped {len(articles)} articles for query '{query}'")
        return articles
    except Exception as e:
        logger.error(f"ScienceDirect scrape error for query '{query}': {e}")
        return []

def weekly_search():
    all_articles = []
    selected_keywords = G6_KEYWORDS
    for keyword in selected_keywords:
        all_articles += arxiv_search(keyword)
        all_articles += semantic_search(keyword)
        all_articles += flexible_scrape_sciencedirect(keyword)
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
