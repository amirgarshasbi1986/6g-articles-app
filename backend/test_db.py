# backend/test_db.py
from backend.db import db
from backend.models import Article
from flask import Flask

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://wiseman:amirGR86!!@localhost:5432/db_6g'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

with app.app_context():
    db.create_all()
    print("Tables created")
