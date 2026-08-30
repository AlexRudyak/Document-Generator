"""Entry point.

From source:   ``python run.py``  (Flask dev server + reloader; opens the browser)
Frozen (.exe): double-click - starts a local server, opens the browser, no
               reloader/debugger. Uses ``waitress`` if available.

For a real multi-user deployment use a dedicated WSGI server instead, e.g.
``gunicorn "app:create_app()"``.

Note: the server binds ``127.0.0.1`` and every URL here uses that literal, not
``localhost`` - on some systems ``localhost`` resolves to IPv6 ``::1`` first and
each request stalls ~2 s waiting for that to time out.
"""

import os
import sys
import threading
import webbrowser

try:
    # Optional: load variables from a local .env file if python-dotenv is installed.
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from app import create_app
from paths import version

app = create_app()

FROZEN = getattr(sys, 'frozen', False)
HOST = '127.0.0.1'


def _open_browser(url):
    if os.environ.get('NO_BROWSER') != '1':
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()


def _serve_prod(port):
    """Serve with waitress when present, otherwise the Flask dev server."""
    try:
        from waitress import serve

        serve(app, host=HOST, port=port, threads=8)
    except ImportError:
        app.run(host=HOST, port=port, debug=False, threaded=True)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    url = f'http://{HOST}:{port}/'
    print(f'Document Generator {version()} - {url}')

    if FROZEN:
        _open_browser(url)
        print('(close this window to quit)')
        _serve_prod(port)
    else:
        debug = os.environ.get('FLASK_DEBUG', '1') == '1'
        # Only the reloader's parent process should open the browser.
        if not debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
            _open_browser(url)
        app.run(host=HOST, port=port, debug=debug, threaded=True)
