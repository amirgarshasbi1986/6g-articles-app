import os
import pathlib
from dotenv import load_dotenv
from backend.db import Base, session
from backend.models import Article
from backend.searcher import weekly_search
from backend.summarizer import generate_summary
from datetime import datetime, timedelta
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_weekly_job():
    logger.info("Starting weekly job")
    now = datetime.now()
    week = now.isocalendar()[1]
    year = now.year
    week_str = f"{year}-{week:02d}"
    logger.info(f"Computed week: {week_str}")

    # Step 1: Get top 50 most relevant articles (last 12 months)
    candidates = weekly_search()
    logger.info(f"Received {len(candidates)} candidate articles from searcher")

    # Step 2: Select up to 8 NEW articles (not in DB)
    selected_articles = []
    for article in candidates:
        if len(selected_articles) >= 8:
            break

        title = article['title']
        link = article['link']
        logger.info(f"Checking article: {title[:60]}...")

        # Skip if already in DB
        existing = session.query(Article).filter_by(link=link).first()
        if existing:
            logger.info(f"Skipping duplicate: {title[:60]} (Link: {link})")
            continue

        # Generate summary
        try:
            summary_data = generate_summary(article['full_text'])
            logger.info(f"Summary generated for: {title[:60]}")
        except Exception as e:
            logger.error(f"Summary failed for {title[:60]}: {e}")
            continue

        # Truncate fields
        authors = (article['authors'] or '')[:500]
        new_article = Article(
            title=article['title'][:500],
            authors=authors,
            publish_date=article['publish_date'],
            link=link,
            summary=summary_data['summary'],
            key_points=json.dumps(summary_data['key_points']),
            week=week_str,
            created_at=now
        )
        session.add(new_article)
        selected_articles.append(new_article)

    # Step 3: Commit to DB
    if selected_articles:
        session.commit()
        logger.info(f"Saved {len(selected_articles)} new articles to DB for week {week_str}")
    else:
        logger.info("No new articles to save this week")

    # Step 4: Export ONLY the selected articles to JSON
    json_file = f"articles_week_{week_str}.json"
    json_data = [a.to_dict() for a in selected_articles]
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, indent=2, default=str)
    logger.info(f"Exported {len(json_data)} articles to {json_file}")

if __name__ == '__main__':
    Base.metadata.create_all(bind=session.bind)
    run_weekly_job()
    session.close()
