from flask import Blueprint, jsonify, send_file, request
from .scheduler import run_weekly_job
from .models import Article
from .db import db
import os

api = Blueprint('api', __name__, url_prefix='/api')

@api.route('/health')
def health():
    try:
        db.session.execute('SELECT 1')
        return jsonify({'status': 'ok', 'db': 'connected'})
    except Exception as e:
        return jsonify({'status': 'error', 'db': 'disconnected', 'error': str(e)}), 500

@api.route('/trigger-search', methods=['POST'])
def trigger_search():
    try:
        run_weekly_job()
        return jsonify({'status': 'Search triggered'})
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500

@api.route('/articles')
def get_articles():
    week = request.args.get('week')
    if not week:
        return jsonify({'status': 'error', 'message': 'Week parameter required'}), 400
    articles = Article.query.filter_by(week=week).all()
    return jsonify([a.to_dict() for a in articles])

@api.route('/articles/json')
def get_articles_json():
    week = request.args.get('week')
    if not week:
        return jsonify({'status': 'error', 'message': 'Week parameter required'}), 400
    json_file = f"articles_week_{week}.json"
    if os.path.exists(json_file):
        return send_file(json_file, mimetype='application/json')
    else:
        return jsonify({'status': 'error', 'message': f'No JSON file found for week {week}'}), 404
