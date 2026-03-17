"""
WSGI entry point for production deployment (gunicorn, uwsgi, etc.).

Usage:
  gunicorn -w 4 -b 0.0.0.0:8000 wsgi:app
  uwsgi --http :8000 --wsgi-file wsgi.py --callable app
"""
from app import app
