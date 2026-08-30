"""Filesystem paths that work both from source and from a frozen build.

When packaged with PyInstaller the application runs from a temporary,
**read-only** extraction directory (``sys._MEIPASS``) and the executable itself
usually lives somewhere the user cannot write to. So we split paths in two:

* :func:`resource_path` - read-only assets shipped inside the bundle
  (HTML templates, CSS/JS, logos, fonts).
* :func:`data_dir` / :func:`uploads_dir` - a writable, per-user location for the
  SQLite database and uploaded images.

Environment overrides (useful for tests / servers):
``DOCGEN_DATA_DIR``   - base dir for the database
``DOCGEN_UPLOAD_DIR`` - dir for uploaded images
"""

import os
import sys

APP_NAME = "DocGenerator"


def is_frozen() -> bool:
    """True when running from a PyInstaller (or similar) bundle."""
    return getattr(sys, "frozen", False)


def _project_root() -> str:
    return os.path.abspath(os.path.dirname(__file__))


def resource_path(*parts: str) -> str:
    """Absolute path to a bundled, read-only resource.

    ``resource_path("app", "templates")`` resolves under ``sys._MEIPASS`` in a
    frozen build and under the project root when running from source.
    """
    base = getattr(sys, "_MEIPASS", None) or _project_root()
    return os.path.join(base, *parts)


def data_dir() -> str:
    """Writable base directory for user data (created on first access)."""
    override = os.environ.get("DOCGEN_DATA_DIR")
    if override:
        base = override
    elif is_frozen():
        if sys.platform == "win32":
            root = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
            base = os.path.join(root, APP_NAME)
        elif sys.platform == "darwin":
            base = os.path.join(os.path.expanduser("~/Library/Application Support"), APP_NAME)
        else:
            root = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
            base = os.path.join(root, APP_NAME)
    else:
        # Running from source: keep the database next to the code, as before.
        base = _project_root()
    os.makedirs(base, exist_ok=True)
    return base


def uploads_dir() -> str:
    """Writable directory for uploaded figures / signatures (created on access)."""
    override = os.environ.get("DOCGEN_UPLOAD_DIR")
    if override:
        base = override
    elif is_frozen():
        base = os.path.join(data_dir(), "uploads")
    else:
        base = resource_path("app", "static", "uploads")
    os.makedirs(base, exist_ok=True)
    return base
