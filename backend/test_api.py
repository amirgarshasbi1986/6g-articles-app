import feedparser
import urllib.parse

query = '6G wireless communication'
broad_query = f'6G OR {urllib.parse.quote(query)}'
params = {
    'search_query': broad_query,
    'start': '0',
    'max_results': '5',
    'sortBy': 'submittedDate',
    'sortOrder': 'descending'
}
url = 'http://export.arxiv.org/api/query?' + urllib.parse.urlencode(params)
feed = feedparser.parse(url)
print(f'Entries: {len(feed.entries)}')
for entry in feed.entries[:2]:
    print(f'Title: {entry.title}')
    print(f'Link: {entry.link}')
    print('---')
