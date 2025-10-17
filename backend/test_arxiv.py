import arxiv
import logging

logging.basicConfig(level=logging.INFO)

# Construct the default API client
client = arxiv.Client()

# Search for "6G wireless communication", max 5 results, sorted by submitted date
search = arxiv.Search(
    query="6G wireless communication",
    max_results=5,
    sort_by=arxiv.SortCriterion.SubmittedDate,
    sort_order=arxiv.SortOrder.Descending
)

# Fetch and print results
results = list(client.results(search))
print(f'Entries: {len(results)}')
for result in results:
    print(f'Title: {result.title}')
    print(f'Authors: {result.authors}')
    print(f'Published: {result.published}')
    print(f'Link: {result.entry_id}')
    print('---')
