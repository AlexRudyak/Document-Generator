import glob
import os

import pytest

from app import create_app, db

UPLOAD_DIR = os.path.join('app', 'static', 'uploads')


class TestConfig:
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = 'test'


@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture(autouse=True)
def _clean_uploads():
    """Remove any files written to the uploads dir by a test."""
    before = set(glob.glob(os.path.join(UPLOAD_DIR, '*')))
    yield
    for path in set(glob.glob(os.path.join(UPLOAD_DIR, '*'))) - before:
        os.remove(path)
