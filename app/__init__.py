from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy

from config import Config
from paths import resource_path

db = SQLAlchemy()

def create_app(config_class=Config):
    # Explicit folders so templates/static resolve from the PyInstaller bundle
    # (sys._MEIPASS) as well as from source.
    app = Flask(
        __name__,
        template_folder=resource_path('app', 'templates'),
        static_folder=resource_path('app', 'static'),
    )
    app.config.from_object(config_class)

    db.init_app(app)

    # Register blueprint
    from app.api.routes import api_bp
    app.register_blueprint(api_bp, url_prefix='/api')

    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/history')
    def history():
        return render_template('history.html')

    with app.app_context():
        db.create_all()
        _apply_lightweight_migrations()

    @app.errorhandler(400)
    def bad_request(error):
        return {"error": "Bad request", "message": str(error.description)}, 400

    @app.errorhandler(404)
    def not_found(error):
        return {"error": "Not found", "message": "Resource not found"}, 404

    @app.errorhandler(500)
    def internal_server_error(error):
        return {"error": "Internal server error", "message": "An unexpected error occurred"}, 500

    return app


def _apply_lightweight_migrations():
    """Add columns introduced after a database was first created.

    ``db.create_all()`` never alters existing tables, so for the SQLite file that
    ships with a running install we add any missing nullable columns by hand.
    Keeps upgrades painless without pulling in a full migration framework.
    """
    from sqlalchemy import inspect, text

    wanted = {
        'document': {
            'logo_left_path': 'VARCHAR(255)',
            'logo_right_path': 'VARCHAR(255)',
            'contact_details': 'TEXT',
        },
    }
    inspector = inspect(db.engine)
    existing_tables = set(inspector.get_table_names())
    for table, columns in wanted.items():
        if table not in existing_tables:
            continue
        present = {c['name'] for c in inspector.get_columns(table)}
        with db.engine.begin() as conn:
            for name, ddl in columns.items():
                if name not in present:
                    conn.execute(text(f'ALTER TABLE {table} ADD COLUMN {name} {ddl}'))
