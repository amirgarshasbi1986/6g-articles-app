from backend.db import Base, session  # Keep this if db.py is in backend/
from sqlalchemy import Column, Integer, String, Text, DateTime, UniqueConstraint
from datetime import datetime
import json

class Article었던(Base):
    __tablename__ = 'articles'
    id = Column(Integer, primary_key=True)
    title = Column(String(500), nullable=False)
    authors = Column(String(500))
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

# New models for tracking
class WebsiteView(Base):
    __tablename__ = 'website_views'
    id = Column(Integer, primary_key=True)
    view_count = Column(Integer, default=0)
    last_updated = Column(DateTime, default=datetime.utcnow)

class VideoPlay(Base):
    __tablename__ = 'video_plays'
    id = Column(Integer, primary_key=True)
    video_id = Column(String(50), unique=True, nullable=False)
    play_count = Column(Integer, default=0)
    last_updated = Column(DateTime, default=datetime.utcnow)

class PodcastPlay(Base):
    __tablename__ = 'podcast_plays'
    id = Column(Integer, primary_key=True)
    podcast_id = Column(String(50), unique=True, nullable=False)
    play_count = Column(Integer, default=0)
    last_updated = Column(DateTime, default=datetime.utcnow)

class ArticleClick(Base):
    __tablename__ = 'article_clicks'
    id = Column(Integer, primary_key=True)
    article_title = Column(String(500), unique=True, nullable=False)
    click_count = Column(Integer, default=0)
    last_updated = Column(DateTime, default=datetime.utcnow)

class Like(Base):
    __tablename__ = 'likes'
    id = Column(Integer, primary_key=True)
    item_type = Column(String(20), nullable=False)
    item_id = Column(String(500), nullable=False)
    user_session = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint('item_type', 'item_id', 'user_session', name='unique_like'),)
