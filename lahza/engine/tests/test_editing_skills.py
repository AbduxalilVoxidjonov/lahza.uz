"""Local data-only recipe lifecycle, rejection boundaries, atomic apply and rendering."""
import json
import stat
import subprocess
import zipfile

import pytest
from conftest import requires_libass, requires_symlink
from fastapi.testclient import TestClient

from lahza_engine.api.app import create_app
from lahza_engine.config import Settings
from lahza_engine.editing_skills.builtins import builtins
from lahza_engine.editing_skills.store import SkillStore
from lahza_engine.montage.model import Format, MediaRef, MontageTimeline, VideoItem


@pytest.fixture
def client(tmp_path):
    app = create_app(Settings(data_dir=tmp_path / 'data'), token='secret')
    with TestClient(app, headers={'Authorization': 'Bearer secret'}) as c:
        yield c


def recipe(**updates):
    return {**builtins()[0].model_dump(mode='json', by_alias=True), **updates}


def package(tmp_path, data=None, entries=()):
    p = tmp_path / 'test.lahzaskill'
    with zipfile.ZipFile(p, 'w') as z:
        z.writestr('skill.json', json.dumps(data or recipe()))
        for name, content in entries:
            # ZipInfo(name) turns "\" into "/" on Windows; write the raw name like a foreign archive.
            if isinstance(name, str):
                info = zipfile.ZipInfo(name)
                info.filename = name
                name = info
            z.writestr(name, content)
    return p


def seed(client, tmp_path):
    source = tmp_path / 'source.mp4'
    tl = MontageTimeline(format=Format(aspect='16:9', w=160, h=120, fps=10),
                         media={'src': MediaRef(id='src', path=str(source), duration_ms=2000,
                                               width=160, height=120, fps=10, has_audio=False)},
                         video=[VideoItem(id='shot', media='src', src_in_ms=0, src_out_ms=2000)])
    state = client.app.state.lahza
    state.lib_write("INSERT INTO montages(id, name, template_id, sources_json, overrides_json, status, timeline_json, duration_ms) VALUES ('m', 'Test', 't', '[]', '{}', 'ready', ?, 2000)", (tl.model_dump_json(by_alias=True),))
    return tl


def test_lifecycle(client, tmp_path):
    seed(client, tmp_path)
    p = package(tmp_path)
    installed = client.post('/v1/skills:install', json={'path': str(p)})
    assert installed.status_code == 200, installed.text
    assert client.post('/v1/skills:install', json={'path': str(p)}).status_code == 409
    assert client.post('/v1/skills:install', json={'path': str(p), 'replace': True}).status_code == 200
    catalog = client.get('/v1/skills').json()
    assert len(catalog['items']) == 1 and len(catalog['builtins']) == 2
    for builtin in catalog['builtins']:
        assert builtin['path'].endswith('.json')
    response = client.post('/v1/skills/caption-freeze:apply', json={'montage_id': 'm', 'title': 'Salom'})
    assert response.status_code == 200, response.text
    tl = MontageTimeline.model_validate(response.json()['timeline'])
    assert tl.text[0].text == 'Salom'
    assert tl.video[0].fx[0].plugin == 'uz.lahza.speed.freeze'
    assert tl.video[0].fx[0].params['dur_ms'] == 800
    assert tl.duration_ms == 2000
    row = client.app.state.lahza.lib("SELECT * FROM montages WHERE id = 'm'")[0]
    assert row['user_edited'] == 1
    assert MontageTimeline.model_validate_json(row['timeline_json']) == tl
    assert client.delete('/v1/skills/caption-freeze').status_code == 200
    assert client.get('/v1/skills').json()['items'] == []
    assert client.delete('/v1/skills/caption-freeze').status_code == 404
    assert client.post('/v1/skills/caption-freeze:apply', json={'montage_id': 'm'}).status_code == 404


@pytest.mark.parametrize('entry', ['../escape.png', '/abs.png', 'assets/../escape.png', 'assets/../../escape.png', 'assets\\x.png', 'assets/x.py', 'assets/x.js', 'assets/run.sh', 'assets/x.png/../../bad', 'https://example.com/a.png'])
def test_unsafe_paths(client, tmp_path, entry):
    response = client.post('/v1/skills:install', json={'path': str(package(tmp_path, entries=[(entry, b'x')]))})
    assert response.status_code == 400
    assert client.get('/v1/skills').json()['items'] == []


@pytest.mark.parametrize('updates', [
    {'schema': 'lahza.skill/2'}, {'version': 'latest'}, {'id': '../bad'}, {'id': 'UPPER'},
    {'permissions': ['network']}, {'permissions': []}, {'script': 'alert(1)'},
    {'actions': [{'type': 'shell', 'command': 'touch pwned'}]},
    {'actions': [{'type': 'motion', 'preset': 'custom-code'}]},
    {'actions': [{'type': 'freeze', 'params': {'code': 'x'}}]},
    {'actions': [{'type': 'caption', 'text': '{name}'}]},
    {'actions': [{'type': 'caption', 'text': r'{\p1}ASS'}]},
    {'actions': [{'type': 'freeze', 'duration_ms': '800'}]},
    {'actions': [{'type': 'color', 'preset': 'lut'}]},
])
def test_reject_manifest(client, tmp_path, updates):
    p = package(tmp_path, recipe(**updates))
    assert client.post('/v1/skills:install', json={'path': str(p)}).status_code == 400


@pytest.mark.parametrize('mode', [stat.S_IFLNK | 0o777, stat.S_IFREG | 0o755, stat.S_IFIFO | 0o600])
def test_symlink_and_executable(client, tmp_path, mode):
    entry = zipfile.ZipInfo('assets/x.png')
    entry.create_system = 3
    entry.external_attr = mode << 16
    p = package(tmp_path, entries=[(entry, b'/etc/passwd')])
    assert client.post('/v1/skills:install', json={'path': str(p)}).status_code == 400


def test_limits_and_failed_replace(client, tmp_path, monkeypatch):
    from lahza_engine.editing_skills import store
    p = package(tmp_path)
    assert client.post('/v1/skills:install', json={'path': str(p)}).status_code == 200
    monkeypatch.setattr(store, 'MAX_ENTRIES', 0)
    assert client.post('/v1/skills:install', json={'path': str(p), 'replace': True}).status_code == 400
    assert client.get('/v1/skills').json()['items'][0]['version'] == '1.0.0'
    monkeypatch.setattr(store, 'MAX_ENTRIES', 128)
    monkeypatch.setattr(store, 'MAX_TOTAL', 5)
    assert client.post('/v1/skills:install', json={'path': str(p)}).status_code == 400
    monkeypatch.setattr(store, 'MAX_TOTAL', 32*1024*1024)
    monkeypatch.setattr(store, 'MAX_MANIFEST', 5)
    assert client.post('/v1/skills:install', json={'path': str(p)}).status_code == 400


def test_auth_and_atomic_failure(client, tmp_path):
    seed(client, tmp_path)
    for method, path, body in [('get', '/v1/skills', None), ('post', '/v1/skills:install', {'path': '/tmp/x.json'}),
                               ('post', '/v1/skills/x:apply', {'montage_id': 'm'}), ('delete', '/v1/skills/x', None)]:
        kwargs = {'headers': {'Authorization': 'Bearer wrong'}}
        if body:
            kwargs['json'] = body
        assert getattr(client, method)(path, **kwargs).status_code == 401
    p = package(tmp_path, recipe(actions=[{'type': 'caption', 'text': 'ok'}, {'type': 'freeze', 'at_ms': 5000}]))
    assert client.post('/v1/skills:install', json={'path': str(p)}).status_code == 200
    before = client.app.state.lahza.lib("SELECT timeline_json FROM montages WHERE id='m'")[0][0]
    assert client.post('/v1/skills/caption-freeze:apply', json={'montage_id': 'm'}).status_code == 400
    after = client.app.state.lahza.lib("SELECT timeline_json FROM montages WHERE id='m'")[0][0]
    assert before == after
    assert client.post('/v1/skills/caption-freeze:apply', json={'montage_id': 'm', 'expected_timeline': '0'*64}).status_code == 409
    assert client.post('/v1/skills/caption-freeze:apply', json={'montage_id': 'missing'}).status_code == 404
    client.app.state.lahza.lib_write("UPDATE montages SET status='planning' WHERE id='m'")
    assert client.post('/v1/skills/caption-freeze:apply', json={'montage_id': 'm'}).status_code == 409


def test_builtin_zoom_color_and_target(client, tmp_path):
    seed(client, tmp_path)
    example = client.get('/v1/skills').json()['builtins'][1]
    assert client.post('/v1/skills:install', json={'path': example['path']}).status_code == 200
    response = client.post('/v1/skills/gentle-zoom:apply', json={'montage_id': 'm', 'video_id': 'shot', 'start_ms': 100})
    assert response.status_code == 200, response.text
    fx = response.json()['timeline']['video'][0]['fx'][0]
    assert fx['at_ms'] == 100 and fx['dur_ms'] == 1900 and fx['params']['zoom'] == 1.12
    assert client.post('/v1/skills/gentle-zoom:apply', json={'montage_id': 'm', 'video_id': 'missing'}).status_code == 400
    p = package(tmp_path, recipe(id='warm', actions=[{'type': 'color', 'preset': 'warm'}]))
    assert client.post('/v1/skills:install', json={'path': str(p)}).status_code == 200
    assert client.post('/v1/skills/warm:apply', json={'montage_id': 'm'}).json()['timeline']['color']['plugin'] == 'uz.lahza.color.warm'


def test_assets_survive_remove(client, tmp_path):
    from lahza_engine.stickers.generate_assets import write_png
    seed(client, tmp_path)
    png = tmp_path / 'image.png'
    write_png(png, 16, 16, lambda x, y: (255, 0, 0, 255))
    p = package(tmp_path, recipe(id='sticker', permissions=['timeline.modify', 'assets.read'], actions=[{'type': 'sticker', 'asset': 'assets/image.png'}]), [('assets/image.png', png.read_bytes())])
    assert client.post('/v1/skills:install', json={'path': str(p)}).status_code == 200
    response = client.post('/v1/skills/sticker:apply', json={'montage_id': 'm'})
    assert response.status_code == 200, response.text
    from pathlib import Path
    retained = Path(response.json()['timeline']['stickers'][0]['path'])
    assert retained.read_bytes() == png.read_bytes()
    assert client.delete('/v1/skills/sticker').status_code == 200
    assert retained.is_file()
    # Prove the persisted timeline still renders AFTER its source recipe is removed.
    from lahza_engine.render.montage_render import render_montage_frame
    from lahza_engine.stickers import inspect_sticker
    assert inspect_sticker(str(retained))['width'] == 16
    saved = client.app.state.lahza.lib("SELECT timeline_json FROM montages WHERE id='m'")[0][0]
    timeline = MontageTimeline.model_validate_json(saved)
    assert str(client.app.state.lahza.settings.data_dir.resolve()) in str(retained)
    assert '/Skills/' not in str(retained)
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i',
                    'color=black:s=160x120:r=10:d=2', '-c:v', 'mpeg4',
                    timeline.media['src'].path], check=True)
    frame = render_montage_frame(timeline, 500, tmp_path/'after-uninstall.jpg',
                                 client.app.state.lahza.settings)
    import numpy as np
    pixels = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(frame), '-frames:v', '1',
                             '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True, check=True).stdout
    image = np.frombuffer(pixels, dtype=np.uint8).reshape(120, 160, 3)
    assert image[60, 80, 0] > 200 and image[60, 80, 1] < 30
    p = package(tmp_path, recipe(permissions=['timeline.modify', 'assets.read'], actions=[{'type': 'sticker', 'asset': 'assets/missing.png'}]))
    assert client.post('/v1/skills:install', json={'path': str(p)}).status_code == 400


@requires_symlink
def test_symlink_scope(tmp_path):
    data = tmp_path / 'data'
    data.mkdir()
    outside = tmp_path / 'outside'
    outside.mkdir()
    (data / 'Skills').symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError):
        SkillStore(data)
    (data / 'Skills').unlink()
    store = SkillStore(data)
    (store.root / 'bad').symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError):
        store.remove('bad')
    assert outside.is_dir()


@requires_libass
@pytest.mark.ffmpeg
def test_installed_recipe_renders(client, tmp_path):
    from lahza_engine.render.encoders import EncoderChoice
    from lahza_engine.render.montage_render import render_montage, render_montage_frame
    tl = seed(client, tmp_path)
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc2=s=160x120:r=10:d=2', '-c:v', 'mpeg4', tl.media['src'].path], check=True)
    p = package(tmp_path)
    assert client.post('/v1/skills:install', json={'path': str(p)}).status_code == 200
    response = client.post('/v1/skills/caption-freeze:apply', json={'montage_id': 'm', 'title': 'Salom'})
    assert response.status_code == 200
    result = MontageTimeline.model_validate(response.json()['timeline'])
    enc = EncoderChoice('mpeg4', ('-c:v', 'mpeg4', '-q:v', '2', '-pix_fmt', 'yuv420p'), False)
    settings = client.app.state.lahza.settings
    output = render_montage(result, tmp_path/'out.mp4', tmp_path/'work', enc, settings).video
    assert output.is_file() and output.stat().st_size > 0
    assert render_montage_frame(result, 400, tmp_path/'preview.jpg', settings).is_file()
