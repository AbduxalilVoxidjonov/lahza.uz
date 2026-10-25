"""Isolated authenticated desktop API smoke; reuses installed model paths, never their registry.

Run with engine/.venv/bin/python. --setup-vad permits only the small VAD download;
ASR/LLM must already be installed. Without it, no model download is requested.
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import subprocess
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


def seed_models(destination: Path, registry_path: Path, *, omit_vad: bool = False) -> None:
    """Hardlink selected healthy model files inside the isolated managed boundary."""
    registry = json.loads(registry_path.read_text())
    selected = set(registry['defaults'].values())
    registry['models'] = [m for m in registry['models'] if m['id'] in selected
                          and not (omit_vad and m['task'] == 'vad')]
    if omit_vad:
        registry['defaults'].pop('vad', None)
    for model in registry['models']:
        source = Path(model['path']).resolve(strict=True)
        source_root = source if source.is_dir() else source.parent
        target = destination / model['task'] / source_root.name
        for item in source_root.rglob('*'):
            if not item.is_file():
                continue
            output = target / item.relative_to(source_root)
            output.parent.mkdir(parents=True, exist_ok=True)
            try:
                os.link(item.resolve(), output)
            except OSError:
                shutil.copy2(item, output)
        model['path'] = str(target if source.is_dir() else target / source.name)
    destination.mkdir(parents=True, exist_ok=True)
    (destination / 'installed.json').write_text(json.dumps(registry))


def main() -> None:
    from lahza_engine.config import Settings

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--video', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True, help='New isolated evidence directory')
    parser.add_argument('--setup-vad', action='store_true')
    parser.add_argument('--setup-only', action='store_true', help='Stop after setup API verification')
    parser.add_argument('--ai', action='store_true', help='Exercise real local editing plan and preview')
    parser.add_argument('--raw', action='store_true',
                        help='Beginner path: direct kind=file source with captions enabled, no episode import')
    parser.add_argument('--offline', action='store_true',
                        help='Require ready setup, block HTTP(S) upstream via unreachable proxy')
    parser.add_argument('--binary', type=Path, help='Frozen engine instead of source Python')
    parser.add_argument('--resources', type=Path, help='App Contents/Resources for frozen checks')
    args = parser.parse_args()
    if args.offline and args.setup_vad:
        parser.error('--offline and --setup-vad cannot be combined')
    root = args.out.resolve()
    root.mkdir(parents=True, exist_ok=False)
    models = root / 'data/Models'
    models.mkdir(parents=True)
    seed_models(models, Settings().models_dir / 'installed.json', omit_vad=args.setup_vad)
    token = secrets.token_urlsafe(32)
    env = {**os.environ, 'LAHZA_DATA_DIR': str(root / 'data'), 'LAHZA_TOKEN': token,
           'LAHZA_DEV': '1', 'LAHZA_BIN_DIR': str(ROOT / 'app/src-tauri/resources/bin'),
           'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1'}
    if args.offline:
        env.update(HTTP_PROXY='http://127.0.0.1:9', HTTPS_PROXY='http://127.0.0.1:9',
                   ALL_PROXY='http://127.0.0.1:9', NO_PROXY='127.0.0.1,localhost')
    if args.binary:
        resources = (args.resources or ROOT / 'app/src-tauri/resources').resolve()
        catalog = resources / 'catalog' if args.resources else ROOT / 'build/sidecar/catalog'
        env.update(LAHZA_DEV='0', LAHZA_BIN_DIR=str(resources / 'bin'),
                   LAHZA_CATALOG=str(catalog / 'catalog.json'),
                   LAHZA_CATALOG_PUBKEY=(catalog / 'catalog.pub').read_text().strip())
    command = [str(args.binary.resolve())] if args.binary else [sys.executable, '-m', 'lahza_engine']
    with (root / 'engine.log').open('w+') as log:
        process = subprocess.Popen([*command, 'serve', '--port', '0'], env=env,
                                   cwd=ROOT, stdout=log, stderr=log)
        try:
            deadline = time.monotonic() + 90
            port = None
            while time.monotonic() < deadline:
                for line in (root / 'engine.log').read_text().splitlines():
                    if line.startswith('LAHZA_READY port='):
                        port = int(line.split('=')[1])
                if port:
                    break
                if process.poll() is not None:
                    raise RuntimeError((root / 'engine.log').read_text())
                time.sleep(.2)
            if not port:
                raise TimeoutError('Engine startup')
            with httpx.Client(base_url=f'http://127.0.0.1:{port}', trust_env=False,
                              headers={'Authorization': f'Bearer {token}'}, timeout=180) as client:
                def request(method, path, body=None):
                    response = client.request(method, path, json=body)
                    response.raise_for_status()
                    return response.json()

                def wait(job):
                    end = time.monotonic() + 600
                    while time.monotonic() < end:
                        current = request('GET', '/v1/jobs/' + job['id'])
                        if current['status'] == 'done':
                            return current.get('result')
                        if current['status'] in ('failed', 'cancelled'):
                            raise RuntimeError(current)
                        time.sleep(.3)
                    raise TimeoutError(job)

                for _ in range(100):
                    try:
                        request('GET', '/v1/health')
                        break
                    except httpx.ConnectError:
                        time.sleep(.2)
                report = {'engine': command, 'isolated_data': str(root / 'data')}
                if args.offline:
                    status = request('GET', '/v1/setup')
                    assert status['ready'], status
                    job = request('POST', '/v1/setup:start', {'consent': True})
                    result = wait(job)
                    assert result == {'installed': [], 'ready': True}, result
                    report.update(offline_proxy=True, setup_ready=status, setup_result=result)
                if args.setup_vad:
                    before = request('GET', '/v1/setup')
                    report['setup_before'] = before
                    assert not before['ready'], before
                    missing = [c['id'] for c in before['components'] if c['required'] and not c['ready']]
                    assert missing == ['vad'], missing  # prohibit unintended multi-GB downloads
                    job = request('POST', '/v1/setup:start', {'consent': True})
                    installed = wait(job)
                    assert installed['installed'] == ['custom:silero-v5.1.2'], installed
                    after = request('GET', '/v1/setup')
                    assert after['ready'], after
                    repeat = request('POST', '/v1/setup:start', {'consent': True})
                    wait(repeat)
                    assert repeat['id'] == job['id'], repeat
                    report.update(setup_after=after, setup_repeat=repeat)
                if args.setup_only:
                    (root / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
                    print(json.dumps(report, ensure_ascii=False, indent=2))
                    return
                project = request('POST', '/v1/projects', {'name': 'Desktop smoke'})
                if args.raw:
                    sources = [{'kind': 'file', 'path': str(args.video.resolve(strict=True))}]
                    report.update(project_id=project['id'], source_kind='file', episode_import=False)
                else:
                    imported = request('POST', '/v1/media:import', {
                        'project_id': project['id'], 'path': str(args.video.resolve(strict=True)),
                        'force_lite': True,
                    })
                    analysis = wait(imported['job'])
                    report.update(project_id=project['id'], analysis=analysis, source_kind='episode')
                    sources = [{'kind': 'episode', 'episode_id': imported['episode_id']}]
                created = request('POST', '/v1/montages', {
                    'name': 'Desktop isolated smoke', 'template_id': 'uz.lahza.tpl.daily-story',
                    'project_id': project['id'],
                    'sources': sources,
                    'overrides': {'target_duration_ms': 12000, 'captions': True},
                })
                wait(created['job'])
                mid = created['montage_id']
                if args.raw:
                    timeline = request('GET', f'/v1/montages/{mid}')['timeline']
                    words = timeline['captions']['words']
                    assert timeline['captions']['enabled'] and words, 'Raw input produced no caption words'
                    assert request('GET', f"/v1/projects/{project['id']}/episodes") == []
                    report.update(raw_caption_words=len(words), raw_episode_count=0)
                if args.ai:
                    status = request('GET', '/v1/editing-agent/status')
                    assert status['available'], status
                    timeline = request('GET', f'/v1/montages/{mid}')['timeline']
                    proposal = request('POST', '/v1/editing-agent:plan', {
                        'prompt': 'Subtitrlar ekranda ko‘rinsin, harflari 80 piksel bo‘lsin.',
                        'timeline': timeline,
                    })
                    assert proposal['plan']['commands'], proposal
                    preview = request('POST', '/v1/editing-agent:preview', {
                        'timeline': timeline, 'plan': proposal['plan'],
                    })['timeline']
                    assert preview['captions']['style']['font_size'] == 80, preview['captions']
                    request('PUT', f'/v1/montages/{mid}/timeline', preview)
                    report.update(ai_status=status, ai_proposal=proposal)
                result = wait(request('POST', f'/v1/montages/{mid}:render', {
                    'out_dir': str(root / 'export'), 'filename': 'desktop-smoke',
                }))
                report.update(montage_id=mid, export=result)
                probe = subprocess.run([str(ROOT / 'app/src-tauri/resources/bin/ffprobe'),
                                        '-v', 'error', '-show_streams', '-of', 'json',
                                        str(root / 'export/desktop-smoke.mp4')],
                                       capture_output=True, text=True, check=True)
                streams = json.loads(probe.stdout)['streams']
                assert {s['codec_type'] for s in streams} >= {'audio', 'video'}
                video = next(s for s in streams if s['codec_type'] == 'video')
                audio = next(s for s in streams if s['codec_type'] == 'audio')
                assert (video['width'], video['height']) == (1080, 1920)
                delta = abs(float(video['duration']) - float(audio['duration']))
                assert delta < .25, delta
                srt = root / 'export/desktop-smoke.srt'
                assert '-->' in srt.read_text(), 'SRT has no timed captions'
                report.update(streams=streams, av_delta_s=delta,
                              srt_cues=srt.read_text().count('-->'))
                (root / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
                print(json.dumps(report, ensure_ascii=False, indent=2))
        finally:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)


if __name__ == '__main__':
    main()
