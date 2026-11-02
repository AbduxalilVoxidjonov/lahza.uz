from lahza_engine.render.capabilities import LibassMissing, has_filter
from lahza_engine.render.encoders import EncoderChoice, choose_encoder
from lahza_engine.render.graph import RenderJob, build_graph, render, render_frame

__all__ = ["EncoderChoice", "choose_encoder", "RenderJob", "build_graph", "render", "render_frame",
           "LibassMissing", "has_filter", "MontageRenderResult", "render_montage",
           "render_montage_frame"]


def __getattr__(name: str):
    # Timeline models import lightweight profiles; do not eagerly import the renderer.
    if name in {"MontageRenderResult", "render_montage", "render_montage_frame"}:
        from lahza_engine.render import montage_render
        return getattr(montage_render, name)
    raise AttributeError(name)
