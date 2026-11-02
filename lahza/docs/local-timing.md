# Container time and local clip rendering

Clip boundaries, cuts, subtitle times and decoded ASR WAV samples use container
presentation time zero. They do not start independently at each stream's first
packet. A source whose video begins at 6.214522 s and audio at 0.000363 s has
black image until the first video frame, with its existing audio underneath.
Positive audio starts produce leading silence. No scene is synthesized and the
source file is never rewritten.

`render/graph.py` retains input timestamps with `-copyts`. Every retained piece
trims absolute source times and subtracts the requested piece boundary from both
streams. A finite black video clock carries the requested piece duration even
when it contains no source images. Audio resampling starts at sample zero, fills
leading gaps, and pads/trims each piece to its requested duration. Concat receives
these normalized pieces. The output duration is bounded to Timeline.duration_ms;
video end times necessarily have one output frame of quantization, while audio
is trimmed at sample resolution. Disabling fades now omits afade entirely (FFmpeg
interprets a zero duration as its default sample count).

MOV/MP4 input seeking before the first video packet can discard earlier audio,
even with `-ss 0`. At zero we omit seeking. At positive seek times we query only
ffprobe stream headers and seek only beyond a known video start. Otherwise we
read from the beginning with a finite input duration. Later seeks retain absolute
timestamps using `-seek_timestamp 1`. Rendering does not eagerly decode or scan
the whole source. Preview frames use the same timing graph.

`media/probe.py:extract_wav` also retains timestamps and uses resampling with
`first_pts=0`, so positive audio starts are represented as silence in the WAV
used by transcription. Existing WAV/transcript caches for delayed-audio media
must be regenerated to adopt this convention. No ASR code was changed.

## Regression checks

Run from the repository root:

```sh
PATH="$PWD/build/local-runtime/bin:$PATH" \
LAHZA_BIN_DIR="$PWD/build/local-runtime/bin" \
engine/.venv/bin/python -m pytest engine/tests/test_render_timing.py
```

The tests create real tiny MOV files with MPEG-4 video and PCM audio: positive
video start, positive audio start, and both positive. They decode rendered pixels
and audio, checking color transitions, tone/silence boundaries, leading/trailing
padding, cuts (including non-frame-aligned cuts), clips entirely before stream
start, and later clips using input seeking. Boundary tolerance is one video
frame; duration assertions cover both streams and the container. WAV tests check
silence placement and length independently.

The original sample `build/local-smoke/source/nauuJZeQb0I-60-210.mp4` was rendered
without modifying it, using VideoToolbox at 1080x1920, from 0 to 58330 ms. Output:
`build/local-smoke/timing-fix/real-58330.mp4`. Probed container duration: 58350 ms
(one-frame quantization at 23.976 fps), replacing the previous 52177 ms result.
The full model smoke pipeline remains a separate PM rerun; the render check does
not claim to validate transcription/model output. No ingest normalization of the
sample is required; the render graph supplies black/silence. Start the PM rerun
with fresh derived artifacts so WAV/transcript caches use the same origin.
