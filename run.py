"""Entry point.

From source:   ``python run.py``  (Flask dev server, debug/reloader on)
Frozen (.exe): double-click - starts a local server, opens the browser, no
               reloader/debugger. Uses ``waitress`` if available.

For a real multi-user deployment use a dedicated WSGI server instead, e.g.
``gunicorn "app:create_app()"``.
"""

import os
import sys

try:
    # Optional: load variables from a local .env file if python-dotenv is installed.
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from app import create_app

app = create_app()

FROZEN = getattr(sys, 'frozen', False)


def _serve(host, port):
    """Serve with waitress when present, otherwise the Flask dev server."""
    try:
        from waitress import serve

        serve(app, host=host, port=port)
    except ImportError:
        app.run(host=host, port=port, debug=False)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))

    if FROZEN:
        import threading
        import webbrowser

        url = f'http://127.0.0.1:{port}/'
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()
        print(f'Document Generator running at {url}  (close this window to quit)')
        _serve('127.0.0.1', port)
    else:
        debug = os.environ.get('FLASK_DEBUG', '1') == '1'
        app.run(debug=debug, port=port)
