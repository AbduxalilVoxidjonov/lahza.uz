"""Actual decoded pixels, timing and authenticated local-only inspection."""
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest
from conftest import requires_libass
from fastapi.testclient import TestClient

from lahza_engine.api.app import create_app
from lahza_engine.config import Settings
from lahza_engine.montage.model import Format, MediaRef, MontageTimeline, StickerItem, VideoItem
from lahza_engine.render.encoders import EncoderChoice
from lahza_engine.render.montage_render import render_montage, render_montage_frame
from lahza_engine.stickers import ASSETS, StickerError, inspect_sticker, list_stickers
from lahza_engine.stickers.generate_assets import write_png

ENC = EncoderChoice('mpeg4', ('-c:v', 'mpeg4', '-q:v', '2', '-pix_fmt', 'yuv420p'), False)


def ff(*args):
    return subprocess.run(['ffmpeg', '-v', 'error', '-y', *map(str, args)], capture_output=True, check=True)


def rgb(path, time=None):
    args = ['-i', path]
    if time is not None:
        args += ['-ss', str(time)]
    data = ff(*args, '-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-').stdout
    return np.frombuffer(data, np.uint8).reshape(120, 160, 3).astype(float)


@pytest.fixture
def scene(tmp_path):
    src = tmp_path / 'source.mp4'
    ff('-f', 'lavfi', '-i', 'color=black:s=160x120:r=10:d=2', '-c:v', 'mpeg4', src)
    image = tmp_path / "sticker ' [x];.png"
    write_png(image, 40, 20, lambda x, y: (255, 0, 0, 128) if x < 30 else (0, 0, 0, 0))
    tl = MontageTimeline(format=Format(aspect='16:9', w=160, h=120, fps=10),
                         media={'v': MediaRef(id='v', path=str(src), duration_ms=2000,
                                             width=160, height=120, fps=10, has_audio=False)},
                         video=[VideoItem(id='v', media='v', src_in_ms=0, src_out_ms=2000)],
                         stickers=[StickerItem(id='s', path=str(image), start_ms=500, end_ms=1500,
                                               width=.5, height=.5)])
    return tl


def test_catalog_and_inspection(tmp_path):
    items = list_stickers()['items']
    assert len(items) == 3 and len({s['id'] for s in items}) == 3
    assert all(s['width'] == 128 and s['format'] == 'PNG' for s in items)
    fake = tmp_path / 'fake.png'
    fake.write_text('not an image')
    for path in [str(fake), str(tmp_path / 'missing'), 'https://example.com/a.png', 'file:///tmp/a.png', '//server/a', 'bad\0path']:
        with pytest.raises(StickerError):
            inspect_sticker(path)
    client = TestClient(create_app(Settings(data_dir=tmp_path / 'data'), token='secret'))
    assert client.get('/v1/stickers').status_code == 401
    assert client.post('/v1/stickers:inspect', json={'path': str(ASSETS / 'heart.png')}).status_code == 401
    headers = {'Authorization': 'Bearer secret'}
    saved = client.get('/v1/stickers', headers=headers).json()['items']
    assert [{k: v for k, v in s.items() if k != 'path'} for s in saved] == [
        {k: v for k, v in s.items() if k != 'path'} for s in items]
    for source, retained in zip(items, saved, strict=True):
        dest = Path(retained['path'])
        assert dest.is_relative_to(tmp_path / 'data/Assets/stickers')
        assert dest.read_bytes() == Path(source['path']).read_bytes()
    got = client.post('/v1/stickers:inspect', headers=headers, json={'path': items[0]['path']})
    assert got.status_code == 200 and set(got.json()) == {'path', 'width', 'height', 'animated', 'format'}
    assert client.post('/v1/stickers:inspect', headers=headers, json={'path': str(fake)}).status_code == 400


def test_builtin_stickers_survive_frozen_extraction_cleanup(tmp_path, monkeypatch):
    import lahza_engine.stickers as stickers

    extracted = tmp_path / 'temporary-pyinstaller/assets'
    shutil.copytree(ASSETS, extracted)
    monkeypatch.setattr(stickers, 'ASSETS', extracted)
    first = list_stickers(tmp_path / 'persistent')['items']
    shutil.rmtree(extracted)
    for item in first:
        assert inspect_sticker(item['path'])['format'] == 'PNG'
    # A subsequent frozen extraction produces the same persistent file references.
    shutil.copytree(ASSETS, extracted)
    assert list_stickers(tmp_path / 'persistent')['items'] == first


def test_render_alpha_rotation_and_gating(scene, tmp_path):
    scene.stickers[0].rotation = 90
    scene.stickers[0].opacity = .5
    assert scene.duration_ms == 2000
    out = render_montage(scene, tmp_path/'out.mp4', tmp_path/'work', ENC, Settings()).video
    samples = {}
    for ms in (200, 500, 900, 1500, 1800):
        prev = render_montage_frame(scene, ms, tmp_path/f'p{ms}.jpg', Settings())
        p, e = rgb(prev), rgb(out, ms / 1000)
        assert np.abs(p-e).mean() < 3
        samples[ms] = p
    assert samples[200].max() < 10 and samples[1500].max() < 10 and samples[1800].max() < 10
    active = samples[900]
    assert 45 < active[45:65, 75:85, 0].mean() < 85  # source alpha * opacity
    ys, xs = np.where(active[:, :, 0] > 35)
    assert np.ptp(ys) > np.ptp(xs) * 1.3  # horizontal source became vertical
    assert active[10, 10].max() < 10  # transparent outside


def test_gif_frames_and_preview(scene, tmp_path):
    # Original two-frame transparent GIF fixture, assembled from generated RGBA PNGs.
    for i, color in enumerate(((255, 0, 0, 255), (0, 255, 0, 255))):
        write_png(tmp_path/f'g{i}.png', 32, 32,
                  lambda x, y, c=color: c if 4 < x < 27 and 4 < y < 27 else (0, 0, 0, 0))
    gif = tmp_path / 'animation.gif'
    ff('-framerate', '5', '-i', tmp_path/'g%d.png', '-filter_complex',
       '[0:v]split[a][b];[a]palettegen=reserve_transparent=1[p];[b][p]paletteuse', '-loop', '0', gif)
    assert inspect_sticker(str(gif))['animated']
    scene.stickers[0].path = str(gif)
    scene.stickers[0].end_ms = 3000  # never extends timeline
    assert scene.duration_ms == 2000
    out = render_montage(scene, tmp_path/'gif.mp4', tmp_path/'work', ENC, Settings()).video
    colors = []
    for ms in (600, 800, 1000, 1200):
        p = rgb(render_montage_frame(scene, ms, tmp_path/f'g{ms}.jpg', Settings()))
        e = rgb(out, ms/1000)
        assert np.abs(p-e).mean() < 4
        colors.append(p[55:65, 75:85].mean(axis=(0, 1)))
        assert p[20, 20].max() < 10
    assert colors[0][0] > 180 and colors[1][1] > 180
    assert colors[2][0] > 180 and colors[3][1] > 180  # repeated GIF cycle


@pytest.mark.parametrize('animation', ['fade', 'pop'])
def test_animations(scene, tmp_path, animation):
    scene.stickers[0].animation = animation
    out = render_montage(scene, tmp_path/'anim.mp4', tmp_path/'work', ENC, Settings()).video
    for ms in (500, 600, 900, 1400):
        p = rgb(render_montage_frame(scene, ms, tmp_path/f'a{ms}.jpg', Settings()))
        assert np.abs(p-rgb(out, ms/1000)).mean() < 4
    if animation == 'fade':
        assert rgb(out, .5).mean() < rgb(out, .9).mean() / 3
    else:
        assert (rgb(out, .5)[:, :, 0] > 30).sum() < (rgb(out, .9)[:, :, 0] > 30).sum() * .6


def test_limits_real_decode(tmp_path, monkeypatch):
    import lahza_engine.stickers as stickers
    png = tmp_path/'small.png'
    write_png(png, 16, 16, lambda x, y: (0, 255, 0, 255))
    webp = tmp_path/'actual.webp'
    webp.write_bytes((Path(__file__).parent/'fixtures/stickers/green.webp').read_bytes())
    assert inspect_sticker(str(webp))['format'] == 'WEBP'
    renamed = tmp_path/'not-png.dat'
    renamed.write_bytes(png.read_bytes())
    assert inspect_sticker(str(renamed))['width'] == 16
    monkeypatch.setattr(stickers, 'MAX_DIMENSION', 8)
    with pytest.raises(StickerError, match='dimensions'):
        inspect_sticker(str(png))
    monkeypatch.setattr(stickers, 'MAX_DIMENSION', 4096)
    monkeypatch.setattr(stickers, 'MAX_BYTES', 1)
    with pytest.raises(StickerError, match='MiB'):
        inspect_sticker(str(png))
    monkeypatch.setattr(stickers, 'MAX_BYTES', 16*1024*1024)
    monkeypatch.setattr(stickers, 'MAX_FRAMES', 0)
    with pytest.raises(StickerError, match='frame/pixel'):
        inspect_sticker(str(png))


def test_fit_and_stable_layer_order(scene, tmp_path):
    # 2:1 image fits an 80x60 box at 80x40, without stretching.
    p = rgb(render_montage_frame(scene, 900, tmp_path/'fit.jpg', Settings()))
    ys, xs = np.where(p[:, :, 0] > 60)
    assert 36 <= np.ptp(ys) <= 42 and 55 <= np.ptp(xs) <= 63
    green = tmp_path/'green.png'
    write_png(green, 20, 20, lambda x, y: (0, 255, 0, 255))
    scene.stickers.append(StickerItem(id='g', path=str(green), start_ms=0, end_ms=2000,
                                      width=.5, height=.5, layer=0))
    p = rgb(render_montage_frame(scene, 900, tmp_path/'layers.jpg', Settings()))
    assert p[60, 80, 1] > 200 and p[60, 80, 0] < 20  # equal layer: later item on top
    scene.stickers[0].layer = 1
    p = rgb(render_montage_frame(scene, 900, tmp_path/'reverse.jpg', Settings()))
    assert p[60, 80, 0] > 100  # sorted layer wins, source alpha retained


@requires_libass
def test_freeze_captions_and_sticker_clock(scene, tmp_path):
    from conftest import make_words

    from lahza_engine.montage.model import Captions, FxRef

    # Moving source: verify the freeze itself as well as overlays over its held frame.
    ff('-f', 'lavfi', '-i', 'testsrc2=s=160x120:r=10:d=2', '-c:v', 'mpeg4', scene.media['v'].path)
    scene.video[0].fx = [FxRef(plugin='uz.lahza.speed.freeze', at_ms=400, dur_ms=1000)]
    scene.stickers = []
    plain = render_montage(scene, tmp_path/'freeze.mp4', tmp_path/'w1', ENC, Settings()).video
    assert np.abs(rgb(plain, .6)-rgb(plain, 1.1)).mean() < 1
    scene.captions = Captions(enabled=True, words=make_words('Salom', start_ms=800, word_ms=400))
    captioned = render_montage(scene, tmp_path/'caption.mp4', tmp_path/'w2', ENC, Settings()).video
    assert np.abs(rgb(plain, 1)-rgb(captioned, 1)).mean() > .2
    assert np.abs(rgb(plain, .6)-rgb(captioned, .6)).mean() < 1
    p = rgb(render_montage_frame(scene, 1000, tmp_path/'freeze.jpg', Settings()))
    assert np.abs(p-rgb(captioned, 1)).mean() < 8
    for i, color in enumerate(((255, 0, 0, 255), (0, 255, 0, 255))):
        write_png(tmp_path/f'hold{i}.png', 32, 32,
                  lambda x, y, c=color: c if 4 < x < 27 and 4 < y < 27 else (0, 0, 0, 0))
    gif = tmp_path/'hold.gif'
    ff('-framerate', '5', '-i', tmp_path/'hold%d.png', '-filter_complex',
       '[0:v]split[a][b];[a]palettegen=reserve_transparent=1[p];[b][p]paletteuse', '-loop', '0', gif)
    scene.stickers = [StickerItem(id='gif', path=str(gif), start_ms=500, end_ms=5000,
                                 x=.75, y=.25, width=.25, height=.25)]
    combined = render_montage(scene, tmp_path/'combined.mp4', tmp_path/'w3', ENC, Settings()).video
    for ms in (600, 800, 1000, 1200):
        prev = rgb(render_montage_frame(scene, ms, tmp_path/f'combined{ms}.jpg', Settings()))
        exported = rgb(combined, ms/1000)
        assert np.abs(prev-exported).mean() < 8
    red = rgb(combined, .6)[25:35, 115:125].mean(axis=(0, 1))
    green = rgb(combined, .8)[25:35, 115:125].mean(axis=(0, 1))
    assert red[0] > 180 and green[1] > 180  # GIF continues over frozen video + ASS
    probe = subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-of', 'json', str(combined)],
                           capture_output=True, text=True, check=True)
    import json
    durations = {s['codec_type']: float(s['duration']) for s in json.loads(probe.stdout)['streams']}
    assert abs(durations['video'] - scene.duration_ms/1000) <= .051
    assert abs(durations['audio'] - durations['video']) <= .051


def test_static_webp_render_and_missing_fail_early(scene, tmp_path):
    scene.stickers[0].path = str(Path(__file__).parent/'fixtures/stickers/green.webp')
    p = rgb(render_montage_frame(scene, 900, tmp_path/'webp.jpg', Settings()))
    assert p[60, 70, 1] > 90 and p[60, 70, 0] < 20
    scene.stickers[0].path = str(tmp_path/'missing.png')
    with pytest.raises(StickerError, match='not found'):
        render_montage(scene, tmp_path/'bad.mp4', tmp_path/'badwork', ENC, Settings())
    assert not (tmp_path/'badwork').exists() and not (tmp_path/'bad.mp4').exists()
    with pytest.raises(StickerError):
        render_montage_frame(scene, 0, tmp_path/'bad.jpg', Settings())


def test_real_gif_frame_limit_and_sticker_count(scene, tmp_path, monkeypatch):
    import lahza_engine.stickers as stickers

    for i in range(2):
        write_png(tmp_path/f'limit{i}.png', 16, 16, lambda x, y, n=i: (255*n, 255*(1-n), 0, 255))
    gif = tmp_path/'limit.gif'
    ff('-framerate', '5', '-i', tmp_path/'limit%d.png', '-loop', '0', gif)
    assert inspect_sticker(str(gif))['animated']
    monkeypatch.setattr(stickers, 'MAX_FRAMES', 1)
    with pytest.raises(StickerError, match='frame/pixel'):
        inspect_sticker(str(gif))
    scene.stickers = [scene.stickers[0]] * 33  # guards model_copy/unvalidated internal callers too
    with pytest.raises(StickerError, match='32'):
        render_montage(scene, tmp_path/'badcount.mp4', tmp_path/'countwork', ENC, Settings())
