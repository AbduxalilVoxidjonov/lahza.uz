"""Decode real offset fixtures; duration alone cannot detect independent A/V rebasing."""
import json
import subprocess

import numpy as np
import pytest
from conftest import requires_ffmpeg

from lahza_engine.config import RenderConfig
from lahza_engine.media.probe import extract_wav, read_wav_mono
from lahza_engine.media.tools import find_tool
from lahza_engine.reframe.planner import LayoutSegment
from lahza_engine.render.encoders import EncoderChoice
from lahza_engine.render.graph import RenderJob, build_command, render
from lahza_engine.timeline import Timeline
from lahza_engine.types import Layout

pytestmark = [requires_ffmpeg, pytest.mark.ffmpeg]
FPS = 25


def ff(*args):
    return subprocess.run([str(find_tool('ffmpeg')), '-v', 'error', '-y', *map(str, args)],
                          capture_output=True, check=True).stdout


@pytest.fixture(params=[(0.8, 0.0), (0.0, 0.8), (0.8, 0.4)])
def source(request, tmp_path):
    video_start, audio_start = request.param
    path = tmp_path / 'offset.mov'
    # A second visual/audio boundary one second after each stream starts.
    ff('-f', 'lavfi', '-i', 'color=red:s=64x64:r=25:d=3',
       '-f', 'lavfi', '-i', 'aevalsrc=0.4*sin(2*PI*440*t)*lt(t\\,1):s=48000:d=3',
       '-filter_complex',
       f"[0:v]drawbox=c=lime:t=fill:enable='gte(t,1)',setpts=PTS+{video_start}/TB[v];"
       f'[1:a]asetpts=PTS+{audio_start}/TB[a]',
       '-map', '[v]', '-map', '[a]', '-c:v', 'mpeg4', '-bf', '0', '-c:a', 'pcm_s16le', path)
    data = json.loads(subprocess.check_output([
        str(find_tool('ffprobe')), '-v', 'error', '-show_streams', '-of', 'json', str(path)]))
    starts = {s['codec_type']: float(s['start_time']) for s in data['streams']}
    assert starts['video'] == pytest.approx(video_start, abs=1 / FPS)
    assert starts['audio'] == pytest.approx(audio_start, abs=0.001)
    return path, video_start, audio_start


@pytest.mark.parametrize('start,end,cuts', [
    (0, 2800, []), (200, 2600, [(600, 1000)]),
    (1600, 2800, []), (2400, 3000, []), (0, 400, []), (0, 4200, []),
    (0, 2803, [(211, 317), (523, 641), (933, 1069), (1371, 1527)]),
])
def test_offset_render(source, tmp_path, start, end, cuts):
    path, video_start, audio_start = source
    tl = Timeline(start, end, cuts)
    job = RenderJob(path, tmp_path / 'out.mp4', tmp_path / 'work', 64, 64, FPS, tl,
                    [LayoutSegment(0, tl.duration_ms, Layout.FOCUS)],
                    EncoderChoice('mpeg4', ('-c:v', 'mpeg4', '-q:v', '2'), False),
                    cfg=RenderConfig(width=64, height=64, fade_ms=0,
                                     loudnorm_target_lufs=None))
    command = build_command(job, str(find_tool('ffmpeg')))
    assert '-copyts' in command
    if '-ss' in command:
        assert float(command[command.index('-ss') + 1]) == pytest.approx(max(0, start / 1000 - 1))
    assert '-t' in command[:command.index('-i')]  # bounded decoding, even after seeking
    render(job, timeout_s=30)
    data = json.loads(subprocess.check_output([
        str(find_tool('ffprobe')), '-v', 'error', '-show_format', '-show_streams',
        '-of', 'json', str(job.out)]))
    assert float(data['format']['duration']) == pytest.approx(tl.duration_ms / 1000, abs=1 / FPS)
    for stream in data['streams']:
        assert float(stream['duration']) == pytest.approx(tl.duration_ms / 1000, abs=1 / FPS)
    pixels = np.frombuffer(ff('-i', job.out, '-an', '-pix_fmt', 'rgb24', '-f', 'rawvideo', '-'),
                           np.uint8).reshape(-1, 64, 64, 3).mean(axis=(1, 2))
    audio = np.frombuffer(ff('-i', job.out, '-vn', '-ac', '1', '-ar', '48000',
                             '-f', 'f32le', '-'), np.float32)
    # Inspect every frame except +/- one frame around actual transitions/cuts.
    for i, rgb in enumerate(pixels):
        out_t = i / FPS
        src_t = tl.to_src(round(out_t * 1000)) / 1000
        boundaries = [video_start, video_start + 1, video_start + 3,
                      audio_start, audio_start + 1, audio_start + 3]
        if any(abs(src_t - b) <= 1 / FPS + 0.001 for b in boundaries):
            continue
        if any(abs(out_t - b / 1000) <= 1 / FPS for b in tl.boundaries_out()):
            continue
        if src_t < video_start or src_t >= video_start + 3:
            assert max(rgb) < 15, (out_t, src_t, rgb)
        elif src_t < video_start + 1:
            assert rgb[0] > 180 and rgb[1] < 30, (out_t, src_t, rgb)
        else:
            assert rgb[1] > 180 and rgb[0] < 30, (out_t, src_t, rgb)
        samples = audio[round(out_t * 48000):round((out_t + 0.02) * 48000)]
        rms = np.sqrt(np.mean(samples ** 2))
        if audio_start <= src_t < audio_start + 1:
            assert rms > 0.15, (out_t, src_t, rms)
        else:
            assert rms < 0.025, (out_t, src_t, rms)


def test_wav_uses_container_origin(source, tmp_path):
    path, _, audio_start = source
    wav, rate = read_wav_mono(extract_wav(path, tmp_path / 'asr.wav'))
    assert len(wav) / rate == pytest.approx(audio_start + 3, abs=0.002)
    if audio_start:
        assert np.max(np.abs(wav[:int((audio_start - 0.01) * rate)])) < 0.001
    section = wav[int((audio_start + 0.1) * rate):int((audio_start + 0.2) * rate)]
    assert np.sqrt(np.mean(section ** 2)) > 0.2
