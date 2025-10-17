from backend.db import Base, session
from sqlalchemy import Column, Integer, String, Text, DateTime, UniqueConstraint
from datetime import datetime
import json

class Article(Base):
    __tablename__ = 'articles'
    id = Column(Integer, primary_key=True)
    title = Column(String(500), nullable=False)
    authors = Column(String(500))  # Increased from String(200)
    publish_date = Column(String(100))
    link = Column(String(500), unique=True)
    summary = Column(Text)
    key_points = Column(Text)
    week = Column(String(10))
    created_at = Column(DateTime, default=datetime.now)

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'authors': self.authors,
            'publish_date': self.publish_date,
            'link': self.link,
            'summary': self.summary,
            'key_points': json.loads(self.key_points) if self.key_points else [],
            'week': self.week,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

# New Models for Tracking
class WebsiteView(Base):
    __tablename__ = 'website_views'
    id = Column(Integer, primary_key=True)
    view_count = Column(Integer, default=0)
    last_updated = Column(DateTime, default=datetime.utcnow)

class VideoPlay(Base):
    __tablename__ = 'video_plays'
    id = Column(Integer, primary_key=True)
    video_id = Column(String(50), unique=True, nullable=False)  # e.g., 'video1'
    play_count = Column(Integer, default=0)
    last_updated = Column(DateTime, default=datetime.utcnow)

class PodcastPlay(Base):
    __tablename__ = 'podcast_plays'
    id = Column(Integer, primary_key=True)
    podcast_id = Column(String(50), unique=True, nullable=False)  # e.g., 'podcast1'
    play_count = Column(Integer, default=0)
    last_updated = Column(DateTime, default=datetime.utcnow)

class ArticleClick(Base):
    __tablename__ = 'article_clicks'
    id = Column(Integer, primary_key=True)
    article_title = Column(String(500), unique=True, nullable=False)  # Use title as ID (consistent with your Article model)
    click_count = Column(Integer, default=0)
    last_updated = Column(DateTime, default=datetime.utcnow)

class Like(Base):
    __tablename__ = 'likes'
    id = Column(Integer, primary_key=True)
    item_type = Column(String(20), nullable=False)  # 'video', 'podcast', 'article'
    item_id = Column(String(500), nullable=False)  # e.g., 'video1' or article title
    user_session = Column(String(100), nullable=False)  # Flask session ID or IP
    created_at = Column(DateTime, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint('item_type', 'item_id', 'user_session', name='unique_like'),)

# Create tables if not exist (run this once in a script or app startup)
# from backend.db import engine
# Base.metadata.create_all(engine)
