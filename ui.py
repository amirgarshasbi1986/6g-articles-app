from flask import Flask, render_template, request, send_from_directory, send_file, abort, make_response, jsonify, session, redirect, url_for
from datetime import datetime
import json
import os
import glob
import logging
from functools import wraps  # Added for wraps in decorator
from backend.models import Article, WebsiteView, VideoPlay, PodcastPlay, ArticleClick, Like
from backend.db import session as db_session

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = 'your_super_secret_key_change_me'  # Change this to a secure random value in production

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def increment_website_view(func):
    @wraps(func)  # Preserve original function name to avoid overwriting endpoint
    def wrapper(*args, **kwargs):
        if 'website_viewed' not in session:
            view = db_session.query(WebsiteView).first()
            if not view:
                view = WebsiteView(view_count=1)
                db_session.add(view)
            else:
                view.view_count += 1
            db_session.commit()
            session['website_viewed'] = True
        return func(*args, **kwargs)
    return wrapper

@app.route('/')
@increment_website_view
def dashboard():
    # Load videos from main JSON
    videos = []
    videos_file = os.path.join(BASE_DIR, 'videos/main/videos.json')
    if os.path.exists(videos_file):
        with open(videos_file, 'r') as f:
            videos = json.load(f)

    # Load podcasts from main JSON
    podcasts = []
    podcasts_file = os.path.join(BASE_DIR, 'podcasts/main/podcasts.json')
    if os.path.exists(podcasts_file):
        with open(podcasts_file, 'r') as f:
            podcasts = json.load(f)

    # Load latest week's articles
    week = request.args.get('week', get_latest_week('backend'))
    json_file = os.path.join(BASE_DIR, f"backend/articles_week_{week}.json")
    articles = []
    if os.path.exists(json_file):
        with open(json_file, 'r') as f:
            articles = json.load(f)
            articles = sorted(articles, key=lambda x: x.get('created_at', ''), reverse=True)[:4]  # 4 articles for grid
    logger.info(f"Loaded {len(articles)} articles for week {week}")

    # Fetch global views
    website_view = db_session.query(WebsiteView).first()
    total_views = website_view.view_count if website_view else 0

    # Fetch play counts
    video_plays = {vp.video_id: vp.play_count for vp in db_session.query(VideoPlay).all()}
    podcast_plays = {pp.podcast_id: pp.play_count for pp in db_session.query(PodcastPlay).all()}
    article_clicks = {ac.article_title: ac.click_count for ac in db_session.query(ArticleClick).all()}

    # User session for likes
    user_session_id = session.get('user_id', request.remote_addr)
    if 'user_id' not in session:
        session['user_id'] = user_session_id

    # Add data to videos
    for video in videos:
        video['play_count'] = video_plays.get(video['id'], 0)
        video['likes'] = db_session.query(Like).filter_by(item_type='video', item_id=video['id']).count()
        video['user_liked'] = db_session.query(Like).filter_by(item_type='video', item_id=video['id'], user_session=user_session_id).first() is not None

    # Add data to podcasts
    for podcast in podcasts:
        podcast['play_count'] = podcast_plays.get(podcast['id'], 0)
        podcast['likes'] = db_session.query(Like).filter_by(item_type='podcast', item_id=podcast['id']).count()
        podcast['user_liked'] = db_session.query(Like).filter_by(item_type='podcast', item_id=podcast['id'], user_session=user_session_id).first() is not None

    # Add data to articles
    for article in articles:
        title = article['title']
        article['click_count'] = article_clicks.get(title, 0)
        article['likes'] = db_session.query(Like).filter_by(item_type='article', item_id=title).count()
        article['user_liked'] = db_session.query(Like).filter_by(item_type='article', item_id=title, user_session=user_session_id).first() is not None

    return render_template('dashboard.html', videos=videos, podcasts=podcasts, articles=articles, selected_week=week, video_week='main', podcast_week='main', total_views=total_views)

@app.route('/videos')
@increment_website_view
def videos():
    week = request.args.get('week', get_latest_week('videos'))
    videos_file = os.path.join(BASE_DIR, f"videos/{week}/videos.json")
    media_week = week
    videos = []
    if os.path.exists(videos_file):
        with open(videos_file, 'r') as f:
            videos = json.load(f)
    # Fallback to main
    if not videos:
        media_week = 'main'
        videos_file = os.path.join(BASE_DIR, 'videos/main/videos.json')
        if os.path.exists(videos_file):
            with open(videos_file, 'r') as f:
                videos = json.load(f)
    logger.info(f"Loaded {len(videos)} videos for week {week}")
    weeks = get_weeks_from_folder('videos')
    weeks.sort(reverse=True)

    # Add play counts and likes
    video_plays = {vp.video_id: vp.play_count for vp in db_session.query(VideoPlay).all()}
    user_session_id = session.get('user_id', request.remote_addr)
    total_views = db_session.query(WebsiteView).first().view_count if db_session.query(WebsiteView).first() else 0
    for video in videos:
        video['play_count'] = video_plays.get(video['id'], 0)
        video['likes'] = db_session.query(Like).filter_by(item_type='video', item_id=video['id']).count()
        video['user_liked'] = db_session.query(Like).filter_by(item_type='video', item_id=video['id'], user_session=user_session_id).first() is not None

    return render_template('videos.html', videos=videos, selected_week=week, weeks=weeks, media_week=media_week, total_views=total_views)

@app.route('/podcasts')
@increment_website_view
def podcasts():
    week = request.args.get('week', get_latest_week('podcasts'))
    podcasts_file = os.path.join(BASE_DIR, f"podcasts/{week}/podcasts.json")
    media_week = week
    podcasts = []
    if os.path.exists(podcasts_file):
        with open(podcasts_file, 'r') as f:
            podcasts = json.load(f)
    # Fallback to main
    if not podcasts:
        media_week = 'main'
        podcasts_file = os.path.join(BASE_DIR, 'podcasts/main/podcasts.json')
        if os.path.exists(podcasts_file):
            with open(podcasts_file, 'r') as f:
                podcasts = json.load(f)
    logger.info(f"Loaded {len(podcasts)} podcasts for week {week}")
    weeks = get_weeks_from_folder('podcasts')
    weeks.sort(reverse=True)

    # Add play counts and likes
    podcast_plays = {pp.podcast_id: pp.play_count for pp in db_session.query(PodcastPlay).all()}
    user_session_id = session.get('user_id', request.remote_addr)
    total_views = db_session.query(WebsiteView).first().view_count if db_session.query(WebsiteView).first() else 0
    for podcast in podcasts:
        podcast['play_count'] = podcast_plays.get(podcast['id'], 0)
        podcast['likes'] = db_session.query(Like).filter_by(item_type='podcast', item_id=podcast['id']).count()
        podcast['user_liked'] = db_session.query(Like).filter_by(item_type='podcast', item_id=podcast['id'], user_session=user_session_id).first() is not None

    return render_template('podcasts.html', podcasts=podcasts, selected_week=week, weeks=weeks, media_week=media_week, total_views=total_views)

@app.route('/articles')
@increment_website_view
def articles():
    week = request.args.get('week', get_latest_week('backend'))
    search_term = request.args.get('search', '').lower()
    json_file = os.path.join(BASE_DIR, f"backend/articles_week_{week}.json")
    articles = []
    if os.path.exists(json_file):
        with open(json_file, 'r') as f:
            articles = json.load(f)
            articles = sorted(articles, key=lambda x: x.get('created_at', ''), reverse=True)
            if search_term:
                articles = [a for a in articles if search_term in a.get('title', '').lower() or search_term in a.get('authors', '').lower()]
    logger.info(f"Loaded {len(articles)} articles for week {week}, search '{search_term}'")
    weeks = [file.split('articles_week_')[-1].replace('.json', '') for file in glob.glob(os.path.join(BASE_DIR, 'backend/articles_week_*.json'))]
    weeks.sort(reverse=True)

    # Add click counts and likes
    article_clicks = {ac.article_title: ac.click_count for ac in db_session.query(ArticleClick).all()}
    user_session_id = session.get('user_id', request.remote_addr)
    total_views = db_session.query(WebsiteView).first().view_count if db_session.query(WebsiteView).first() else 0
    for article in articles:
        title = article['title']
        article['click_count'] = article_clicks.get(title, 0)
        article['likes'] = db_session.query(Like).filter_by(item_type='article', item_id=title).count()
        article['user_liked'] = db_session.query(Like).filter_by(item_type='article', item_id=title, user_session=user_session_id).first() is not None

    return render_template('articles.html', articles=articles, selected_week=week, weeks=weeks, search_term=search_term, total_views=total_views)

@app.route('/about')
@increment_website_view
def about():
    total_views = db_session.query(WebsiteView).first().view_count if db_session.query(WebsiteView).first() else 3
    return render_template('about.html', total_views=total_views)

@app.route('/videos/<week>/<video_id>')
@increment_website_view
def video_detail(week, video_id):
    # If it's a file request (ends with .mp4 or .pdf), serve the file
    if video_id.endswith(('.mp4', '.pdf')):
        return serve_video_file(week, video_id)

    videos_file = os.path.join(BASE_DIR, f"videos/{week}/videos.json")
    media_week = week
    videos = []
    if os.path.exists(videos_file):
        with open(videos_file, 'r') as f:
            videos = json.load(f)
    # Fallback to main
    if not videos:
        media_week = 'main'
        videos_file = os.path.join(BASE_DIR, 'videos/main/videos.json')
        if os.path.exists(videos_file):
            with open(videos_file, 'r') as f:
                videos = json.load(f)
    video = next((v for v in videos if v['id'] == video_id), None)
    if not video:
        abort(404)
    other_videos = [v for v in videos if v['id'] != video_id]

    # Add play count and likes
    play = db_session.query(VideoPlay).filter_by(video_id=video_id).first()
    video['play_count'] = play.play_count if play else 0
    user_session_id = session.get('user_id', request.remote_addr)
    video['likes'] = db_session.query(Like).filter_by(item_type='video', item_id=video_id).count()
    video['user_liked'] = db_session.query(Like).filter_by(item_type='video', item_id=video_id, user_session=user_session_id).first() is not None
    total_views = db_session.query(WebsiteView).first().view_count if db_session.query(WebsiteView).first() else 0

    return render_template('video_detail.html', video=video, selected_week=week, other_videos=other_videos, media_week=media_week, total_views=total_views)

@app.route('/podcasts/<week>/<podcast_id>')
@increment_website_view
def podcast_detail(week, podcast_id):
    # If it's a file request (ends with .mp3 or .pdf), serve the file
    if podcast_id.endswith(('.mp3', '.pdf')):
        return serve_podcast_file(week, podcast_id)

    podcasts_file = os.path.join(BASE_DIR, f"podcasts/{week}/podcasts.json")
    media_week = week
    podcasts = []
    if os.path.exists(podcasts_file):
        with open(podcasts_file, 'r') as f:
            podcasts = json.load(f)
    # Fallback to main
    if not podcasts:
        media_week = 'main'
        podcasts_file = os.path.join(BASE_DIR, 'podcasts/main/podcasts.json')
        if os.path.exists(podcasts_file):
            with open(podcasts_file, 'r') as f:
                podcasts = json.load(f)
    podcast = next((p for p in podcasts if p['id'] == podcast_id), None)
    if not podcast:
        abort(404)
    other_podcasts = [p for p in podcasts if p['id'] != podcast_id]

    # Add play count and likes
    play = db_session.query(PodcastPlay).filter_by(podcast_id=podcast_id).first()
    podcast['play_count'] = play.play_count if play else 0
    user_session_id = session.get('user_id', request.remote_addr)
    podcast['likes'] = db_session.query(Like).filter_by(item_type='podcast', item_id=podcast_id).count()
    podcast['user_liked'] = db_session.query(Like).filter_by(item_type='podcast', item_id=podcast_id, user_session=user_session_id).first() is not None
    total_views = db_session.query(WebsiteView).first().view_count if db_session.query(WebsiteView).first() else 0

    return render_template('podcast_detail.html', podcast=podcast, selected_week=week, other_podcasts=other_podcasts, media_week=media_week, total_views=total_views)

@app.route('/videos/<week>/<path:filename>')
def serve_video_file(week, filename):
    directory = os.path.join(BASE_DIR, 'videos', week)
    if not os.path.exists(directory):
        abort(404)
    try:
        return send_from_directory(directory, filename)
    except FileNotFoundError:
        logger.error(f"Video file not found: {directory}/{filename}")
        abort(404)

@app.route('/podcasts/<week>/<path:filename>')
def serve_podcast_file(week, filename):
    directory = os.path.join(BASE_DIR, 'podcasts', week)
    if not os.path.exists(directory):
        abort(404)
    try:
        return send_from_directory(directory, filename)
    except FileNotFoundError:
        logger.error(f"Podcast file not found: {directory}/{filename}")
        abort(404)

@app.route('/api/increment_play', methods=['POST'])
def increment_play():
    data = request.json
    item_type = data['type']
    item_id = data['id']
    Model = VideoPlay if item_type == 'video' else PodcastPlay
    attr = 'video_id' if item_type == 'video' else 'podcast_id'
    play = db_session.query(Model).filter_by(**{attr: item_id}).first()
    if not play:
        play = Model(**{attr: item_id, 'play_count': 1})
        db_session.add(play)
    else:
        play.play_count += 1
    db_session.commit()
    return jsonify({'count': play.play_count})

@app.route('/api/increment_article_click', methods=['POST'])
def increment_article_click():
    data = request.json
    title = data['title']
    click = db_session.query(ArticleClick).filter_by 
    if not click:
        click = ArticleClick(article_title=title, click_count=1)
        db_session.add(click)
    else:
        click.click_count += 1
    db_session.commit()
    return jsonify({'count': click.click_count})

@app.route('/api/toggle_like', methods=['POST'])
def toggle_like():
    data = request.json
    item_type = data['type']
    item_id = data['id']
    user_session_id = session.get('user_id', request.remote_addr)
    like = db_session.query(Like).filter_by(item_type=item_type, item_id=item_id, user_session=user_session_id).first()
    if like:
        db_session.delete(like)
        liked = False
    else:
        like = Like(item_type=item_type, item_id=item_id, user_session=user_session_id)
        db_session.add(like)
        liked = True
    db_session.commit()
    total = db_session.query(Like).filter_by(item_type=item_type, item_id=item_id).count()
    return jsonify({'liked': liked, 'total': total})

def get_latest_week(folder='backend'):
    if folder == 'backend':
        weeks = [file.split('articles_week_')[-1].replace('.json', '') for file in glob.glob(os.path.join(BASE_DIR, f'{folder}/articles_week_*.json'))]
    else:
        weeks = get_weeks_from_folder(folder)
    if weeks:
        weeks.sort(reverse=True)
        return weeks[0]
    return get_current_week()

def get_weeks_from_folder(folder):
    weeks = []
    folder_path = os.path.join(BASE_DIR, folder)
    for dir_name in os.listdir(folder_path):
        if dir_name.startswith('20') and '-' in dir_name:
            weeks.append(dir_name)
    return weeks

def get_current_week():
    year, week, _ = datetime.now().isocalendar()
    return f"{year}-{week:02d}"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000, debug=True)
