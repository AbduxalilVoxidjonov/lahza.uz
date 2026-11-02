"""Data-only external assets and real LUT timeline/render contract."""
import json
import zipfile
from pathlib import Path

import pytest
from _api_helpers import make_client

from lahza_engine.interop import MAX_FILE, inspect_asset
from lahza_engine.montage.model import FxRef, MontageTimeline
from lahza_engine.render.montage_render import _resolve_fx, color_filter


def cube(path: Path, content: str | None = None) -> Path:
    path.write_text(content or 'LUT_3D_SIZE 2\n' + '\n'.join(
        f'{r} {g} {b}' for b in (0, 1) for g in (0, 1) for r in (0, 1)))
    return path


def test_lut_timeline_and_renderer(tmp_path, monkeypatch):
    p = cube(tmp_path / 'identity.cube')
    c, st = make_client(tmp_path, monkeypatch)
    result = c.post('/v1/interop/inspect', json={'path': str(p)})
    assert result.status_code == 200
    report = result.json()
    assert report['can_apply'] and report['normalized']['samples'] == 8
    fx = FxRef.model_validate(report['normalized']['fx'])
    tl = MontageTimeline(color=fx)
    st.lib_write("INSERT INTO montages(id,name,template_id,status,sources_json,timeline_json) VALUES (?,?,?,?,?,?)",
                 ('interop-test', 'LUT test', 'test', 'ready', '[]', json.dumps(MontageTimeline().to_json())))
    saved = c.put('/v1/montages/interop-test/timeline', json=tl.to_json())
    assert saved.status_code == 200, saved.text
    loaded = c.get('/v1/montages/interop-test').json()['timeline']
    assert loaded['color']['params']['file'] == str(p)
    resolved = _resolve_fx([FxRef.model_validate(loaded['color'])], 1, [], 'color')
    assert len(resolved) == 1
    work = tmp_path / 'render'
    assert color_filter(resolved[0], work, 'lut0.cube') == 'lut3d=file=lut0.cube'
    assert (work / 'lut0.cube').read_bytes() == p.read_bytes()


@pytest.mark.parametrize('text', [
    'LUT_3D_SIZE 2\n0 0 0', 'LUT_3D_SIZE 999\n', 'LUT_1D_SIZE 2\n0 0 0',
    'LUT_3D_SIZE 2\nLUT_3D_SIZE 2', 'LUT_3D_SIZE 2\nnan 0 0',
    'LUT_3D_SIZE 2\nDOMAIN_MIN 1 1 1\nDOMAIN_MAX 0 0 0',
    'LUT_3D_SIZE 2\n' + '0 0 0\n' * 9,
])
def test_bad_lut(tmp_path, text):
    with pytest.raises(ValueError):
        inspect_asset(str(cube(tmp_path / 'bad.cube', text)))


def test_srt_and_bad_timing(tmp_path):
    p = tmp_path / 'captions.srt'
    p.write_text('1\n00:00:01,250 --> 00:00:02,500\nSalom\nDunyo\n')
    r = inspect_asset(str(p))
    assert not r['can_apply']
    assert r['normalized']['cues'] == [{'start_ms': 1250, 'end_ms': 2500, 'text': 'Salom\nDunyo'}]
    p.write_text('1\n00:00:02,500 --> 00:00:01,250\nOops')
    with pytest.raises(ValueError):
        inspect_asset(str(p))


def test_preset_names_not_fake_mapping(tmp_path):
    p = tmp_path / 'preset.prfpset'
    p.write_text('<Preset><EffectName>Lumetri Color</EffectName></Preset>')
    r = inspect_asset(str(p))
    assert r['normalized']['effect_names'] == ['Lumetri Color']
    assert r['normalized']['supported_mappings'] == [] and not r['can_apply']
    p.write_text('<!DOCTYPE x [<!ENTITY x "boom">]><x>&x;</x>')
    with pytest.raises(ValueError):
        inspect_asset(str(p))


def test_mogrt_bounds_and_metadata(tmp_path):
    p = tmp_path / 'template.mogrt'
    with zipfile.ZipFile(p, 'w') as z:
        z.writestr('definition.json', '{"name":"Title"}')
        z.writestr('script.jsx', 'throw new Error("never execute")')
    r = inspect_asset(str(p))
    assert not r['can_apply'] and r['normalized']['metadata_text']
    assert not (tmp_path / 'script.jsx').exists()
    for name, value in [('../escape', 'bad'), ('/absolute', 'bad'), ('C:/bad', 'bad'), ('bomb', '0' * 100000)]:
        with zipfile.ZipFile(p, 'w', compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr(name, value)
        with pytest.raises(ValueError):
            inspect_asset(str(p))
    with zipfile.ZipFile(p, 'w') as z:
        for i in range(257):
            z.writestr(str(i), '')
    with pytest.raises(ValueError):
        inspect_asset(str(p))


@pytest.mark.parametrize('ext', ['ffx', 'aep', 'prproj', 'aex', 'plugin', 'ccx', 'zxp', 'unknown'])
def test_native_never_applies(tmp_path, ext):
    p = tmp_path / f'asset.{ext}'
    p.write_bytes(b'not executable here')
    r = inspect_asset(str(p))
    assert not r['can_apply'] and r['importability'] == 'unsupported'


def test_api_auth_limits_and_errors(tmp_path, monkeypatch):
    c, _ = make_client(tmp_path, monkeypatch)
    p = cube(tmp_path / 'ok.cube')
    assert c.post('/v1/interop/inspect', json={'path': str(p)}, headers={'Authorization': 'Bearer wrong'}).status_code == 401
    for path in ['relative.cube', str(tmp_path / 'missing'), str(tmp_path)]:
        assert c.post('/v1/interop/inspect', json={'path': path}).status_code == 400
    p.write_bytes(b'x' * (MAX_FILE + 1))
    assert c.post('/v1/interop/inspect', json={'path': str(p)}).status_code == 400
    p = tmp_path / 'bad.mogrt'
    p.write_bytes(b'not zip')
    assert c.post('/v1/interop/inspect', json={'path': str(p)}).status_code == 400
    p = tmp_path / 'bad.prfpset'
    p.write_text('<unclosed>')
    assert c.post('/v1/interop/inspect', json={'path': str(p)}).status_code == 400
