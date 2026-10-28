"""Bounded, data-only inspection of user-selected external assets."""
from __future__ import annotations

import io
import math
import re
import stat
import zipfile
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree as ET

MAX_FILE = 16 * 1024 * 1024
MAX_ENTRIES = 256
MAX_EXPANDED = 64 * 1024 * 1024


def _cube(text: str, path: Path) -> dict:
    size = None
    count = 0
    domains = {}
    for line in text.splitlines():
        parts = line.split('#', 1)[0].split()
        if not parts:
            continue
        key = parts[0]
        if key == 'TITLE':
            continue
        if key == 'LUT_3D_SIZE':
            if size is not None or len(parts) != 2:
                raise ValueError('Duplicate or malformed LUT_3D_SIZE')
            size = int(parts[1])
            if not 2 <= size <= 64:
                raise ValueError('3D LUT size must be 2..64')
        elif key in ('DOMAIN_MIN', 'DOMAIN_MAX'):
            if key in domains or len(parts) != 4:
                raise ValueError('Duplicate or malformed domain')
            domains[key] = [float(x) for x in parts[1:]]
        else:
            if len(parts) != 3 or size is None:
                raise ValueError('Expected 3D LUT header followed by RGB triples; 1D/combined LUT unsupported')
            values = [float(x) for x in parts]
            if not all(math.isfinite(x) for x in values):
                raise ValueError('LUT numbers must be finite')
            count += 1
            if count > size ** 3:
                raise ValueError('Too many LUT samples')
    lo, hi = domains.get('DOMAIN_MIN', [0]*3), domains.get('DOMAIN_MAX', [1]*3)
    if not all(math.isfinite(a) and math.isfinite(b) and a < b for a, b in zip(lo, hi, strict=True)):
        raise ValueError('Invalid LUT domain')
    if size is None or count != size ** 3:
        raise ValueError('LUT sample count must equal declared size cubed')
    return {'size': size, 'samples': count, 'fx': {'plugin': 'uz.lahza.color.lut',
            'params': {'file': str(path)}, 'source': 'qolda'}}


def _srt(text: str) -> dict:
    cues = []
    def timestamp(s: str) -> int:
        match = re.fullmatch(r'(\d{2,}):([0-5]\d):([0-5]\d),(\d{3})', s)
        if not match:
            raise ValueError('Invalid SRT timestamp (expected HH:MM:SS,mmm)')
        h, m, sec, ms = map(int, match.groups())
        return ((h * 60 + m) * 60 + sec) * 1000 + ms
    for block in re.split(r'\n\s*\n', text.replace('\r\n', '\n').strip()):
        lines = block.splitlines()
        if len(lines) < 3 or not lines[0].isdigit():
            raise ValueError('Expected SRT cue number, timing and text')
        times = lines[1].split(' --> ')
        if len(times) != 2:
            raise ValueError('Invalid SRT timing line')
        start, end = map(timestamp, times)
        if end <= start:
            raise ValueError('SRT cue end must follow start')
        cues.append({'start_ms': start, 'end_ms': end, 'text': '\n'.join(lines[2:])})
        if len(cues) > 10000:
            raise ValueError('SRT exceeds 10000 cues')
    return {'cues': cues}


def _mogrt(data: bytes) -> dict:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        entries = archive.infolist()
        if len(entries) > MAX_ENTRIES or sum(x.file_size for x in entries) > MAX_EXPANDED:
            raise ValueError('Archive entry/expanded size limit exceeded')
        names = []
        metadata = {}
        for entry in entries:
            name = entry.filename
            if ('\\' in name or PurePosixPath(name).is_absolute() or '..' in PurePosixPath(name).parts
                    or ':' in name or stat.S_ISLNK(entry.external_attr >> 16) or entry.flag_bits & 1):
                raise ValueError('Unsafe archive entry')
            if entry.file_size > 16 * 1024 * 1024 or entry.file_size > max(1, entry.compress_size) * 200:
                raise ValueError('Archive member size/compression ratio limit exceeded')
            names.append(name)
            if PurePosixPath(name).name.lower() in ('definition.json', 'manifest.json'):
                if entry.file_size > 256 * 1024:
                    raise ValueError('Metadata exceeds 256 KiB')
                # Read bounded text only. Never extract, evaluate or load embedded projects.
                with archive.open(entry) as stream:
                    raw = stream.read(256 * 1024 + 1)
                if len(raw) > 256 * 1024:
                    raise ValueError('Metadata exceeds limit')
                metadata[name] = raw.decode('utf-8', errors='replace')
        return {'entries': names, 'metadata_text': metadata}


def inspect_asset(filename: str) -> dict:
    path = Path(filename)
    if not path.is_absolute():
        raise ValueError('Select an absolute local path')
    path = path.resolve(strict=True)
    # Open nonblocking so special files cannot hang the engine; check the opened descriptor.
    import os
    # Windows has no O_NONBLOCK (FIFOs cannot appear there) but needs O_BINARY.
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NONBLOCK', 0) | getattr(os, 'O_BINARY', 0))
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise ValueError('Select a regular file (native plugin directories are unsupported)')
        if info.st_size > MAX_FILE:
            raise ValueError('File exceeds 16 MiB inspection limit')
        data = stream.read(MAX_FILE + 1)
    if len(data) > MAX_FILE:
        raise ValueError('File exceeds 16 MiB inspection limit')
    kind = path.suffix.lower().lstrip('.') or 'unknown'
    report = {'path': str(path), 'format': kind, 'can_apply': False,
              'importability': 'unsupported', 'unsupported_features': [], 'normalized': {}}
    if kind == 'cube':
        report.update(can_apply=True, importability='timeline_color', normalized=_cube(data.decode('utf-8-sig'), path))
    elif kind == 'srt':
        report.update(importability='timed_text_report', normalized=_srt(data.decode('utf-8-sig')))
        report['unsupported_features'] = ['Formatting is preserved as literal text; word timing is unavailable; no timeline insertion in this slice.']
    elif kind == 'prfpset':
        text = data.decode('utf-8-sig')
        if '<!DOCTYPE' in text.upper() or '<!ENTITY' in text.upper():
            raise ValueError('XML DTD/entities are forbidden')
        root = ET.fromstring(text)
        nodes = list(root.iter())
        if len(nodes) > 20000:
            raise ValueError('XML node limit exceeded')
        names = sorted({(n.text or '').strip()[:256] for n in nodes
                        if n.tag.rsplit('}', 1)[-1].lower() in ('name', 'effectname', 'matchname') and (n.text or '').strip()})
        report.update(importability='inspect_only', normalized={'effect_names': names, 'supported_mappings': []})
        report['unsupported_features'] = ['Adobe effect IDs, parameter units, keyframes and plugin dependencies are not faithfully mapped; no effects imported.']
    elif kind == 'mogrt':
        report.update(importability='inspect_only', normalized=_mogrt(data))
        report['unsupported_features'] = ['Requires a compatible Adobe host and its effects/fonts/media; embedded project, expressions and scripts are never executed.']
    else:
        report['unsupported_features'] = ['Native Adobe/third-party execution and project translation are unsupported; no code is loaded or executed.']
    return report
