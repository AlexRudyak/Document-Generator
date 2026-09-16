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

import ctypes
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


def _die_with_this_process():
    """Windows only: put this process in a Job Object with kill-on-close.

    In dev mode, ``app.run(debug=True)`` runs its reloader as a *monitor*
    process that spawns the real server as a child via ``subprocess.call``.
    Closing the console window (or otherwise force-killing the monitor)
    doesn't reliably signal that child on Windows - it survives as an
    orphan still holding the port. A Job Object with
    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE fixes this at the OS level: children
    are auto-added to the same job, and the moment this process's handles
    are released - however it dies - Windows kills every process in the
    job with it.
    """
    if os.name != 'nt':
        return
    try:
        # ctypes defaults HANDLE-returning/accepting signatures to 32-bit
        # c_int, which truncates the pseudo-handle from GetCurrentProcess()
        # on 64-bit Python and makes AssignProcessToJobObject fail with
        # ERROR_INVALID_HANDLE. Declare the real (64-bit-safe) types.
        kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel32.CreateJobObjectW.restype = ctypes.c_void_p
        kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        kernel32.AssignProcessToJobObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]

        job = kernel32.CreateJobObjectW(None, None)
        if not job:
            return

        class _BasicLimits(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_int64),
                ("PerJobUserTimeLimit", ctypes.c_int64),
                ("LimitFlags", ctypes.c_uint32),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", ctypes.c_uint32),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", ctypes.c_uint32),
                ("SchedulingClass", ctypes.c_uint32),
            ]

        class _IoCounters(ctypes.Structure):
            _fields_ = [(n, ctypes.c_uint64) for n in (
                "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                "ReadTransferCount", "WriteTransferCount", "OtherTransferCount",
            )]

        class _ExtendedLimits(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", _BasicLimits),
                ("IoInfo", _IoCounters),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
        JobObjectExtendedLimitInformation = 9

        info = _ExtendedLimits()
        info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        kernel32.SetInformationJobObject(
            job, JobObjectExtendedLimitInformation, ctypes.byref(info), ctypes.sizeof(info)
        )
        kernel32.AssignProcessToJobObject(job, kernel32.GetCurrentProcess())
    except OSError:
        pass


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
    _die_with_this_process()

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
