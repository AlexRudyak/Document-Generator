"""Application configuration.

All values can be overridden with environment variables (see ``.env.example``).
A ``.env`` file, if present, is loaded automatically by ``run.py``.
"""

import os

from paths import data_dir, uploads_dir

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    # In production ALWAYS set SECRET_KEY. The dev fallback is intentionally
    # obvious so it is never mistaken for a real secret.
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-only-insecure-secret-key'

    # SQLite lives in the writable data dir (project root from source, per-user
    # app-data dir in a frozen build). Override with DATABASE_URL.
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(data_dir(), 'app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Where uploaded figures / signatures are stored.
    UPLOAD_FOLDER = uploads_dir()

    # Cap upload size (default 10 MB) to protect the figure-upload endpoint.
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 10 * 1024 * 1024))
