"""
Shared Flask-SQLAlchemy extension. Models import db from here.
Initialized with app in app.py via db.init_app(app).
"""
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
