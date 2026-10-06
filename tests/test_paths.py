import os

import paths


def test_resource_path_points_at_bundled_files():
    assert os.path.isdir(paths.resource_path('app', 'templates'))
    assert os.path.isfile(paths.resource_path('app', 'static', 'assets', 'fonts', 'DejaVuSans.ttf'))


def test_uploads_dir_is_writable(tmp_path, monkeypatch):
    monkeypatch.setenv('DOCGEN_UPLOAD_DIR', str(tmp_path / 'up'))
    d = paths.uploads_dir()
    assert os.path.isdir(d)
    probe = os.path.join(d, 'probe.txt')
    with open(probe, 'w') as fh:
        fh.write('ok')
    assert os.path.exists(probe)


def test_data_dir_override(tmp_path, monkeypatch):
    monkeypatch.setenv('DOCGEN_DATA_DIR', str(tmp_path / 'data'))
    assert paths.data_dir() == str(tmp_path / 'data')
    assert os.path.isdir(paths.data_dir())


def test_app_icons_are_served_and_referenced(client):
    """The favicon/icon assets exist and both pages link to them."""
    for url in ('/static/assets/icon.png', '/static/assets/favicon.ico'):
        assert client.get(url).status_code == 200
    for page in ('/', '/history'):
        assert b'/static/assets/favicon.ico' in client.get(page).data
