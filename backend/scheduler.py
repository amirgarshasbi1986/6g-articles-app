from apscheduler.schedulers.background import BackgroundScheduler
from .searcher import weekly_search
from .summarizer import generate_summary
from .models import Article
from .db import db
from datetime import datetime
import json
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_weekly_job():
    logger.info("Starting weekly job")
    week = datetime.now().strftime('%Y-%W')
    articles = weekly_search()
    saved_count = 0
    for article in articles:
        logger.info(f"Processing article: {article['title'][:50]}...")
        with db.session.no_autoflush:  # Prevent autoflush during duplicate check
            if Article.query.filter_by(link=article['link']).first():
                logger.info(f"Skipping duplicate: {article['title'][:50]}")
                continue
        summary_data = generate_summary(article['full_text'])
        logger.info(f"Summary for {article['title'][:50]}: summary={summary_data['summary'][:100]}..., key_points={summary_data['key_points']}")
        new_article = Article(
            title=article['title'],
            authors=article['authors'],
            publish_date=article['publish_date'],
            link=article['link'],
            summary=summary_data['summary'],
            key_points=json.dumps(summary_data['key_points']),
            week=week
        )
        db.session.add(new_article)
        saved_count += 1
    db.session.commit()
    logger.info(f"Saved {saved_count} articles for week {week}")

    # Export current week's articles to JSON
    current_week_articles = Article.query.filter_by(week=week).all()
    json_data = [a.to_dict() for a in current_week_articles]
    json_file = f"articles_week_{week}.json"
    with open(json_file, 'w') as f:
        json.dump(json_data, f, indent=2)
    logger.info(f"Exported {len(json_data)} articles to {json_file}")

def init_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(run_weekly_job, 'cron', day_of_week='mon', hour=0)
    scheduler.start()
    logger.info("Scheduler initialized")
