from lahza_engine.montage.model import MediaRef, MontageTimeline, TextItem, TransitionRef, VideoItem


def _tl(text: list[TextItem]) -> MontageTimeline:
    return MontageTimeline(
        media={"m1": MediaRef(id="m1", path="/x.mp4", duration_ms=20_000, width=1920, height=1080,
                              fps=30)},
        video=[
            VideoItem(id="a", media="m1", src_in_ms=0, src_out_ms=4000),
            VideoItem(id="b", media="m1", src_in_ms=5000, src_out_ms=9000,
                      transition_in=TransitionRef(plugin="uz.lahza.tr.dissolve", dur_ms=500)),
        ],
        text=text,
    )


def test_overlay_text_past_video_end_does_not_extend_duration() -> None:
    # Tahrirdan keyin video qisqarsa, CTA video oxiridan oshib qolishi mumkin - qora kadr bo'lmasin.
    tl = _tl([TextItem(id="outro", start_ms=6000, end_ms=9000, text="Obuna", kind="cta")])
    assert tl.duration_ms == 7500


def test_background_card_after_video_extends_duration() -> None:
    tl = _tl([TextItem(id="outro", start_ms=7500, end_ms=9500, text="Rahmat", kind="card",
                       background="#111111")])
    assert tl.duration_ms == 9500
