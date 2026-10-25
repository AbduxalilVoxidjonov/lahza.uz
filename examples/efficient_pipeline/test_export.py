"""Run: python3 -m unittest discover -s examples/efficient_pipeline -p test_export.py -v

Uses bundled FFmpeg/FFprobe by default; override LAHZA_EXAMPLE_FFMPEG/FFPROBE.
Integration fixtures are generated in a temporary directory, never production.
No pip packages needed. Missing tools/hardware yield explicit integration skips.
"""

from __future__ import annotations

import array
import math
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from fractions import Fraction
from pathlib import Path
from unittest.mock import patch

try:
    from . import single_pass as export
    from . import smart_cut
except ImportError:
    import single_pass as export
    import smart_cut


class ValidationTests(unittest.TestCase):
    def test_hdr_and_anamorphic_input_require_explicit_adapter(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.mp4"
            source.write_bytes(b"probe-is-mocked")
            for extra in (
                {"color_transfer": "smpte2084"},
                {"color_transfer": "arib-std-b67"},
                {"sample_aspect_ratio": "4:3"},
            ):
                info = export.MediaInfo(2, {"index": 0, **extra}, None, "mp4")
                with (
                    self.subTest(extra=extra),
                    patch.object(export, "probe_media", return_value=info),
                    self.assertRaises(ValueError),
                ):
                    export.build_command(
                        [export.Segment(source, 0, 1000)],
                        export.ExportConfig(Path(directory) / "out.mp4"),
                        workdir=Path(directory),
                        encoder="h264_videotoolbox",
                    )

    def test_span_and_numeric_validation(self):
        for kwargs in (
            {"start_ms": -1, "end_ms": 20},
            {"start_ms": 20, "end_ms": 20},
            {"start_ms": True, "end_ms": 30},
            {"start_ms": 0, "end_ms": 30, "speed": float("nan")},
            {"start_ms": 0, "end_ms": 30, "speed": 0},
            {"start_ms": 0, "end_ms": 30, "gain_db": float("inf")},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                export.Segment(Path("x"), **kwargs)

    def test_graph_fragmentation_rejected_before_probe(self):
        with patch.object(export, "probe_media") as probe:
            with self.assertRaises(ValueError):
                export.run_export(
                    [export.Segment(Path("x"), 0, 100)] * 65, export.ExportConfig(Path("x.mp4"))
                )
            probe.assert_not_called()

    def test_cumulative_rounding_has_no_drift(self):
        segments = [export.Segment(Path("x"), 0, 111)] * 64
        durations = export.timeline_durations(segments, 30)
        self.assertLessEqual(abs(sum(durations) - 64 * 0.111), 0.5 / 30 + 1e-9)
        with self.assertRaises(ValueError):
            export.timeline_durations([export.Segment(Path("x"), 0, 1)], 30)

    def test_no_implicit_software_fallback_or_argv_injection(self):
        for encoder in ("libx264", "h264_videotoolbox;rm", "-c:v"):
            with self.subTest(encoder=encoder), self.assertRaises(ValueError):
                export.select_encoder(
                    export.ExportConfig(Path("x.mp4"), encoder=encoder),
                    export.ExportOptions(preflight=False),
                )

    def test_idr_parser_refuses_k_flag_without_idr(self):
        def nal(header):
            return (2).to_bytes(4, "big") + bytes([header, 0x80])

        self.assertTrue(smart_cut._is_idr(nal(0x65), 4))
        self.assertFalse(smart_cut._is_idr(nal(0x61), 4))
        self.assertFalse(smart_cut._is_idr(nal(0x65) + nal(0x61), 4))
        self.assertFalse(smart_cut._is_idr(b"\x00\x00\x00\xff\x65", 4))

    def test_bframes_and_hevc_are_not_auto_admitted(self):
        for stream in (
            {"codec_name": "h264", "has_b_frames": 2},
            {"codec_name": "hevc", "has_b_frames": 0},
        ):
            with (
                self.subTest(stream=stream),
                patch.object(smart_cut, "_probe_json", return_value={"streams": [stream]}),
                self.assertRaises(ValueError),
            ):
                smart_cut.build_keyframe_index(Path(__file__))

    def test_unproved_keyframe_falls_back(self):
        video = {
            "width": 320,
            "height": 180,
            "avg_frame_rate": "30/1",
            "r_frame_rate": "30/1",
            "sample_aspect_ratio": "1:1",
        }
        info = export.MediaInfo(3, video, None, "mov,mp4")
        index = smart_cut.KeyframeIndex(
            (smart_cut.Packet(Fraction(0), Fraction(0), Fraction(3), True),),
            (Fraction(0), Fraction(1), Fraction(2)),
            4,
        )
        with (
            patch.object(smart_cut, "probe_media", return_value=info),
            patch.object(smart_cut, "build_keyframe_index", return_value=index),
            patch.object(smart_cut, "_boundary_is_idr", return_value=False),
        ):
            plan = smart_cut.plan_copy(
                Path("x"), [(1000, 2000)], export.ExportConfig(Path("x.mp4"), width=320, height=180)
            )
        self.assertEqual(plan.mode, "reencode")
        self.assertIn("IDR", plan.reasons[0])

    def test_atomic_publish_does_not_overwrite_a_race(self):
        with tempfile.TemporaryDirectory() as directory:
            source, target = Path(directory) / "temp.mp4", Path(directory) / "out.mp4"
            source.write_bytes(b"new")
            target.write_bytes(b"original")
            with self.assertRaises(FileExistsError):
                export.publish_output(source, target, False)
            self.assertEqual(target.read_bytes(), b"original")

    def test_timeout_with_silent_process_and_flooded_stderr(self):
        with tempfile.TemporaryDirectory() as directory:
            command = [
                sys.executable,
                "-c",
                "import os,time; os.write(2,b'x'*1000000); time.sleep(5)",
            ]
            with self.assertRaises(TimeoutError):
                export.execute_command(
                    command,
                    cwd=Path(directory),
                    duration_s=1,
                    options=export.ExportOptions(timeout_s=0.25),
                )

    def test_cancel_while_no_progress_is_available(self):
        cancel = threading.Event()
        timer = threading.Timer(0.15, cancel.set)
        timer.start()
        try:
            with (
                tempfile.TemporaryDirectory() as directory,
                self.assertRaises(export.ExportCancelled),
            ):
                export.execute_command(
                    [sys.executable, "-c", "import time; time.sleep(5)"],
                    cwd=Path(directory),
                    duration_s=1,
                    cancel=cancel,
                    options=export.ExportOptions(timeout_s=3),
                )
        finally:
            timer.cancel()


class FFmpegTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[2]
        bundled = root / "app/src-tauri/resources/bin"
        ffmpeg = os.environ.get("LAHZA_EXAMPLE_FFMPEG", str(bundled / "ffmpeg"))
        ffprobe = os.environ.get("LAHZA_EXAMPLE_FFPROBE", str(bundled / "ffprobe"))
        if not shutil.which(ffmpeg) or not shutil.which(ffprobe):
            raise unittest.SkipTest("FFmpeg/FFprobe unavailable; set LAHZA_EXAMPLE_FFMPEG/FFPROBE")
        cls.options = export.ExportOptions(ffmpeg=ffmpeg, ffprobe=ffprobe, allow_libx264=True)
        cls.temp = tempfile.TemporaryDirectory(prefix="lahza-tests-")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.directory = Path(cls.temp.name) / "O‘zbek :, ' \\ [assets]"
        cls.directory.mkdir()
        config = export.ExportConfig(cls.directory / "out.mp4", width=320, height=180)
        try:
            cls.encoder = export.select_encoder(config, cls.options)
        except export.ExportError as exc:
            raise unittest.SkipTest(str(exc)) from exc
        cls.source = cls.directory / "video ,:'\\ o‘zbek.mp4"
        cls.silent = cls.directory / "silent.mp4"
        cls.music = cls.directory / "music.wav"
        encode_args = export._encoder_args(cls.encoder, config, cls.options)
        cls.ff(
            [
                "-f",
                "lavfi",
                "-i",
                "testsrc2=s=320x180:r=30:d=4",
                "-f",
                "lavfi",
                "-i",
                "sine=f=440:r=48000:d=4",
                *encode_args,
                "-g",
                "30",
                "-bf",
                "0",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-shortest",
                str(cls.source),
            ]
        )
        cls.ff(["-i", str(cls.source), "-map", "0:v", "-c:v", "copy", "-an", str(cls.silent)])
        cls.ff(
            ["-f", "lavfi", "-i", "sine=f=1200:r=48000:d=0.4", "-c:a", "pcm_s16le", str(cls.music)]
        )
        cls.ass = cls.directory / "captions :, '\\.ass"
        cls.ass.write_text(
            "[Script Info]\nScriptType: v4.00+\nPlayResX: 320\nPlayResY: 180\n"
            "[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
            "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
            "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
            "Style: Default,Inter,28,&H00FFFFFF,&H0000FFFF,&H00000000,&H80000000,"
            "0,0,0,0,100,100,0,0,1,2,0,2,10,10,12,1\n"
            "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
            "Dialogue: 0,0:00:00.00,0:00:00.60,Default,,0,0,0,,O‘zbekcha subtitr\n",
            encoding="utf-8",
        )
        cls.lut = cls.directory / "grade :'\\,.cube"
        cls.lut.write_text(
            "LUT_3D_SIZE 2\nDOMAIN_MIN 0 0 0\nDOMAIN_MAX 1 1 1\n"
            + "\n".join(
                f"{1 - r} {1 - g} {1 - b}" for b in range(2) for g in range(2) for r in range(2)
            )
            + "\n"
        )
        cls.fonts = cls.directory / "fonts ,:'\\"
        cls.fonts.mkdir()
        font = root / "engine/src/lahza_engine/subtitle/fonts/Inter.ttf"
        if not font.exists():
            raise unittest.SkipTest("Bundled Inter font unavailable")
        shutil.copyfile(font, cls.fonts / "Inter ' ,:.ttf")

    @classmethod
    def ff(cls, args):
        return subprocess.run(
            [cls.options.ffmpeg, "-v", "error", "-nostdin", "-y", "-filter_threads", "1", *args],
            capture_output=True,
            timeout=30,
            check=True,
            shell=False,
        ).stdout

    def config(self, name, **kwargs):
        return export.ExportConfig(
            self.directory / name, width=320, height=180, encoder=self.encoder, **kwargs
        )

    def assert_media(self, path, duration, audio=True):
        info = export.probe_media(path, self.options)
        self.assertEqual(info.video["codec_name"], "h264")
        self.assertEqual((info.video["width"], info.video["height"]), (320, 180))
        self.assertLessEqual(abs(info.duration_s - duration), 1 / 30 + 1024 / 48000 + 0.002)
        if audio:
            self.assertEqual(info.audio["codec_name"], "aac")
            self.assertEqual(info.audio["sample_rate"], "48000")
        # Verify the WHOLE output is decodable, not merely that a header exists.
        self.ff(["-xerror", "-i", str(path), "-f", "null", "-"])

    def test_01_single_pass_mixed_speeds_silent_muted_and_music_lut_ass(self):
        segments = [
            export.Segment(self.source, 133, 1533, speed=2),
            export.Segment(self.silent, 2100, 2500, speed=0.5),
            export.Segment(self.source, 3000, 3600, speed=1.5, mute=True),
        ]
        config = self.config(
            "all.mp4",
            ass_path=self.ass,
            lut_path=self.lut,
            fonts_dir=self.fonts,
            music=self.music,
            brightness=0.02,
            contrast=1.02,
            saturation=0.9,
        )
        updates = []
        result = export.run_export(segments, config, options=self.options, progress=updates.append)
        self.assert_media(result.output, 1.9)
        self.assertEqual(updates[-1], 1)
        self.assertEqual(updates, sorted(updates))
        argv = list(result.command)
        graph = argv[argv.index("-filter_complex") + 1]
        self.assertEqual(argv.count("-filter_complex"), 1)
        self.assertEqual(argv.count("-ss"), 3)
        self.assertIn("asplit=2", graph)
        self.assertLess(graph.index("concat="), graph.index("ass=filename"))
        self.assertNotIn(str(self.ass), graph)
        self.assertNotIn(str(self.lut), graph)
        self.assertNotIn(".mkv", " ".join(argv))
        self.assertFalse(list(self.directory.glob(".lahza-*")))

    def test_02_subtitles_use_output_time_and_lut_changes_pixels(self):
        segment = [export.Segment(self.source, 2000, 3000)]
        plain = export.run_export(segment, self.config("plain.mp4"), options=self.options)
        subtitled = export.run_export(
            segment,
            self.config("subs.mp4", ass_path=self.ass, fonts_dir=self.fonts),
            options=self.options,
        )
        graded = export.run_export(
            segment, self.config("lut.mp4", lut_path=self.lut), options=self.options
        )

        def frame(path, seconds):
            return self.ff(
                [
                    "-ss",
                    str(seconds),
                    "-i",
                    str(path),
                    "-frames:v",
                    "1",
                    "-pix_fmt",
                    "rgb24",
                    "-f",
                    "rawvideo",
                    "-",
                ]
            )

        def difference(first, second):
            self.assertEqual(len(first), len(second))
            return sum(abs(a - b) for a, b in zip(first, second, strict=True)) / len(first)

        early = difference(frame(plain.output, 0.2), frame(subtitled.output, 0.2))
        late = difference(frame(plain.output, 0.8), frame(subtitled.output, 0.8))
        self.assertGreater(early, late + 1)
        self.assertGreater(difference(frame(plain.output, 0.2), frame(graded.output, 0.2)), 30)

    def test_03_music_is_looped_and_ducked(self):
        segment = [export.Segment(self.source, 0, 2000)]
        duck = export.run_export(
            segment,
            self.config("duck.mp4", music=self.music, music_gain_db=-6),
            options=self.options,
        )
        no_duck = export.run_export(
            segment,
            self.config("no_duck.mp4", music=self.music, music_gain_db=-6, duck_music=False),
            options=self.options,
        )

        def rms(path):
            raw = self.ff(
                [
                    "-ss",
                    "0.8",
                    "-i",
                    str(path),
                    "-t",
                    "0.8",
                    "-vn",
                    "-af",
                    "bandpass=f=1200:width_type=h:width=80",
                    "-ac",
                    "1",
                    "-f",
                    "f32le",
                    "-",
                ]
            )
            values = array.array("f", raw)
            return math.sqrt(sum(v * v for v in values) / len(values))

        self.assertLess(rms(duck.output), rms(no_duck.output) * 0.75)
        self.assertGreater(rms(no_duck.output), 0.01)  # Music exists beyond its 0.4s source.

    def test_04_out_of_bounds_existing_output_and_process_failure_clean_up(self):
        with self.assertRaises(ValueError):
            export.run_export(
                [export.Segment(self.source, 0, 5000)],
                self.config("bounds.mp4"),
                options=self.options,
            )
        self.assertFalse((self.directory / "bounds.mp4").exists())
        existing = self.directory / "keep.mp4"
        existing.write_bytes(b"keep")
        with self.assertRaises(FileExistsError):
            export.run_export(
                [export.Segment(self.source, 0, 1000)],
                self.config("keep.mp4"),
                options=self.options,
            )
        self.assertEqual(existing.read_bytes(), b"keep")
        bad_lut = self.directory / "invalid.cube"
        bad_lut.write_text("not a LUT")
        with self.assertRaises(export.ExportError):
            export.run_export(
                [export.Segment(self.source, 0, 1000)],
                self.config("failure.mp4", lut_path=bad_lut),
                options=self.options,
            )
        self.assertFalse((self.directory / "failure.mp4").exists())
        self.assertFalse(list(self.directory.glob(".lahza-*")))

    def test_05_verified_idr_copy_and_arbitrary_word_cut_fallback(self):
        config = self.config("copy.mp4")
        index = smart_cut.build_keyframe_index(self.source, self.options)
        self.assertIn(Fraction(1), index.keyframes)
        plan, result = smart_cut.run_smart_cut(
            self.source, [(1000, 2000)], config, options=self.options
        )
        self.assertEqual(plan.mode, "copy_video_encode_audio", plan.reasons)
        self.assertEqual(result.encoder, "copy")
        self.assert_media(result.output, 1)
        self.assertIn("aac", result.command)
        # Full decoded pixels are identical: admitted video is really copied,
        # and excludes the end IDR rather than adding the next GOP.
        expected = self.ff(
            [
                "-ss",
                "1",
                "-i",
                str(self.source),
                "-t",
                "1",
                "-map",
                "0:v:0",
                "-pix_fmt",
                "yuv420p",
                "-f",
                "rawvideo",
                "-",
            ]
        )
        actual = self.ff(
            [
                "-i",
                str(result.output),
                "-map",
                "0:v:0",
                "-pix_fmt",
                "yuv420p",
                "-f",
                "rawvideo",
                "-",
            ]
        )
        self.assertEqual(actual, expected)
        unsafe, encoded = smart_cut.run_smart_cut(
            self.source, [(1117, 1933)], self.config("word.mp4"), options=self.options
        )
        self.assertEqual(unsafe.mode, "reencode")
        self.assertNotEqual(encoded.encoder, "copy")
        self.assert_media(encoded.output, 0.816)
        multi = smart_cut.plan_copy(
            self.source, [(0, 1000), (2000, 3000)], config, options=self.options
        )
        self.assertEqual(multi.mode, "reencode")

    def test_06_snapping_is_opt_in_and_reported(self):
        config = self.config("snap.mp4")
        exact = smart_cut.plan_copy(self.source, [(1010, 1990)], config, options=self.options)
        self.assertEqual(exact.mode, "reencode")
        snap = smart_cut.plan_copy(
            self.source, [(1010, 1990)], config, options=self.options, snap_tolerance_ms=15
        )
        self.assertEqual(snap.mode, "copy_video_encode_audio", snap.reasons)
        self.assertEqual(snap.spans[0].error_ms, (-10, 10))

    def test_07_silent_source_creates_silent_aac(self):
        result = export.run_export(
            [export.Segment(self.silent, 250, 1250)],
            self.config("silence.mp4"),
            options=self.options,
        )
        self.assert_media(result.output, 1)
        raw = self.ff(["-i", str(result.output), "-vn", "-f", "f32le", "-"])
        self.assertLess(max(map(abs, array.array("f", raw))), 1e-6)

    def test_08_packet_limit_is_enforced(self):
        with self.assertRaises(ValueError):
            smart_cut.build_keyframe_index(self.source, self.options, max_packets=10)

    def test_09_pcm_audio_is_encoded_never_copied(self):
        source = self.directory / "pcm.mov"
        self.ff(["-i", str(self.source), "-c:v", "copy", "-c:a", "pcm_s16le", str(source)])
        plan, result = smart_cut.run_smart_cut(
            source, [(1000, 2000)], self.config("pcm_cut.mp4"), options=self.options
        )
        self.assertEqual(plan.mode, "copy_video_encode_audio", plan.reasons)
        self.assert_media(result.output, 1)
        self.assertEqual(result.command[result.command.index("-c:a") + 1], "aac")


if __name__ == "__main__":
    unittest.main(verbosity=2)
