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

load_dotenv()

def run_weekly_job():
    logger.info("Starting weekly job")
    current_date = datetime.now()
    week = datetime.now().isocalendar()[1]
    year = datetime.now().year
    week_str = f"{year}-{week:02d}"
    logger.info(f"Computed week: {week_str}")
    articles = weekly_search()  # Fetch up to 10 articles
    saved_count = 0
    one_month_ago = current_date - timedelta(days=30)  # Filter to recent articles
    for article in articles[:10]:
        if 'publish_date' in article and article['publish_date'] and article['publish_date'] < one_month_ago.date():
            logger.info(f"Skipping old article: {article['title'][:50]}")
            continue
        logger.info(f"Processing article: {article['title'][:50]}...")
        # Check for duplicates globally by link (ignore week)
        with session.no_autoflush:  # Fixed: Removed parentheses
            existing = session.query(Article).filter_by(link=article['link']).first()
        if existing:
            logger.info(f"Skipping duplicate article (already exists from previous week): {article['title'][:50]} (Link: {article['link']})")
            continue
        summary_data = generate_summary(article['full_text'])
        logger.info(f"Summary for {article['title'][:50]}: summary={summary_data['summary'][:100]}..., key_points={summary_data['key_points']}")
        # Truncate fields to avoid database errors
        authors = article['authors'][:500] if article['authors'] else None
        new_article = Article(
            title=article['title'][:500],
            authors=authors,
            publish_date=article['publish_date'],
            link=article['link'],
            summary=summary_data['summary'],
            key_points=json.dumps(summary_data['key_points']),
            week=week_str,
            created_at=datetime.now()
        )
        session.add(new_article)
        saved_count += 1
    session.commit()
    logger.info(f"Saved {saved_count} new articles for week {week_str}")

    # Export to JSON
    current_week_articles = session.query(Article).filter_by(week=week_str).order_by(Article.created_at.desc()).limit(10).all()
    json_data = [a.to_dict() for a in current_week_articles]
    json_file = f"articles_week_{week_str}.json"
    with open(json_file, 'w') as f:
        json.dump(json_data, f, indent=2)
    logger.info(f"Exported {len(json_data)} articles to {json_file}")

if __name__ == '__main__':
    Base.metadata.create_all(bind=session.bind)  # Create tables if needed
    run_weekly_job()
    session.close()
