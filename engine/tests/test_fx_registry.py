"""FX reestri (`lahza.fx/1`): manifest sxemasi, o'rnatilgan plaginlar, parametrlar, oq ro'yxat
(NFR-M1/M3: GPL va fayl o'qiydigan filtrlar taqiqlangan)."""

import json

import pytest
from conftest import HAS_FFMPEG, ffmpeg_filters

from lahza_engine.fx import FxError, FxManifest, get_plugin, list_plugins, validate_params
from lahza_engine.fx.registry import (
    ALLOWED_GRAPH_FILTERS,
    BACKEND_FILTERS,
    BACKENDS,
    BUILTIN_DIR,
    GPL_FILTERS,
    IO_FILTERS,
    check_graph,
    graph_filters,
    load_manifest,
)

REQUIRED = {
    "transition": ["uz.lahza.tr.cut", "uz.lahza.tr.fade", "uz.lahza.tr.dissolve",
                   "uz.lahza.tr.fadeblack", "uz.lahza.tr.wipeleft", "uz.lahza.tr.slideup",
                   "uz.lahza.tr.zoomin", "uz.lahza.tr.smoothleft", "uz.lahza.tr.circleopen"],
    "motion": ["uz.lahza.motion.punch-in", "uz.lahza.motion.push-in", "uz.lahza.motion.pan",
               "uz.lahza.motion.shake", "uz.lahza.motion.zoom-out"],
    "color": ["uz.lahza.color.warm", "uz.lahza.color.cool", "uz.lahza.color.bw",
              "uz.lahza.color.vivid", "uz.lahza.color.film", "uz.lahza.color.lut"],
    "speed": ["uz.lahza.speed.freeze"],
    "audio": ["uz.lahza.audio.fade"],
}


def _manifest(**kw) -> dict:
    base = {"schema": "lahza.fx/1", "id": "user.test.fx", "version": "1.0.0", "kind": "motion",
            "name": {"uz": "Sinov"}, "backend": "motion-keys", "preset": "punch-in",
            "params": [{"id": "zoom", "type": "float", "min": 1.0, "max": 2.0, "default": 1.2}]}
    base.update(kw)
    return base


def test_builtin_ids_and_kinds() -> None:
    for kind, ids in REQUIRED.items():
        have = {m.id for m in list_plugins(kind)}
        assert set(ids) <= have, kind
        for i in ids:
            m = get_plugin(i)
            assert m.kind == kind and m.builtin
            assert m.name["uz"] and m.name["ru"] and m.name["en"] and m.name["uz-Cyrl"]
    assert len(list_plugins()) == sum(len(v) for v in REQUIRED.values())
    with pytest.raises(KeyError):
        get_plugin("uz.lahza.yoq")


def test_builtin_files_are_valid_json_schema() -> None:
    files = sorted(BUILTIN_DIR.glob("*.json"))
    assert files
    for f in files:
        data = json.loads(f.read_text(encoding="utf-8"))
        assert data["schema"] == "lahza.fx/1"
        assert f.stem == data["id"]
        assert data["backend"] in BACKENDS
        load_manifest(f)


def test_manifest_extra_and_whitelist_rejected() -> None:
    FxManifest.model_validate(_manifest())
    for bad in (
        _manifest(filter="eq=contrast=2"),  # noma'lum maydon (extra=forbid)
        _manifest(backend="glsl"),  # ruxsat etilmagan backend
        _manifest(preset="melting"),  # backendda yo'q preset
        _manifest(kind="transition"),  # tur/backend mos emas
        _manifest(name={"ru": "Тест"}),  # uz majburiy
        _manifest(id="Bad Id"),
        _manifest(params=[{"id": "zoom", "type": "float", "min": 1, "max": 2, "default": 5}]),
        _manifest(params=[{"id": "x", "type": "enum", "values": ["a"], "default": "b"}]),
        _manifest(params=[{"id": "x", "type": "string"}]),
    ):
        with pytest.raises(FxError):
            load_manifest(bad)


def test_validate_params_defaults_clamp_and_errors() -> None:
    m = get_plugin("uz.lahza.motion.punch-in")
    assert validate_params(m, {}) == {"zoom": 1.25, "kirish_ms": 120, "easing": "ease-out"}
    assert validate_params(m, {"zoom": 9, "kirish_ms": -5})["zoom"] == 2.0
    assert validate_params(m, {"kirish_ms": 99.6})["kirish_ms"] == 100
    with pytest.raises(FxError):
        validate_params(m, {"zoom": 9}, strict=True)
    with pytest.raises(FxError):
        validate_params(m, {"nomalum": 1})
    with pytest.raises(FxError):
        validate_params(m, {"easing": "bounce"})
    with pytest.raises(FxError):
        validate_params(m, {"zoom": "katta"})
    lut = get_plugin("uz.lahza.color.lut")
    assert validate_params(lut, {"file": "/a/b.cube"}) == {"file": "/a/b.cube"}
    with pytest.raises(FxError):
        validate_params(lut, {"file": 5})
    pan = get_plugin("uz.lahza.motion.pan")
    assert validate_params(pan, {"yonalish": "chapga"})["yonalish"] == "chapga"


def test_whitelist_has_no_gpl_or_io_filters() -> None:
    for backend, names in BACKEND_FILTERS.items():
        assert not names & GPL_FILTERS, backend
        assert not names & IO_FILTERS, backend
    assert not ALLOWED_GRAPH_FILTERS & (GPL_FILTERS | IO_FILTERS)
    for f in ("eq", "histeq", "boxblur", "smartblur", "perspective", "delogo", "hqdn3d",
              "cropdetect", "mpdecimate", "vidstabtransform", "frei0r", "lensfun"):
        assert f in GPL_FILTERS


def test_graph_filter_parser_and_check() -> None:
    g = ("[0:v]trim=start=1:end=2,crop@c0=w=10:h=10:x='clip(t\\,0,5)':y=0[v];\n"
         "[v]zoompan=z='if(between(it,0,1),1.2,1)':d=1:s=1080x1920[o];"
         "[0:a]atrim=end=1,volume=-3dB[a]")
    assert graph_filters(g) == {"trim", "crop", "zoompan", "atrim", "volume"}
    check_graph(g)
    with pytest.raises(FxError, match="taqiqlangan"):
        check_graph("[0:v]eq=contrast=1.2[v]")
    with pytest.raises(FxError, match="taqiqlangan"):
        check_graph("movie=/etc/passwd[v]")
    with pytest.raises(FxError, match="oq ro'yxat"):
        check_graph("[0:v]geq=r=1[v]")


@pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg yo'q")
def test_whitelisted_filters_exist_in_ffmpeg() -> None:
    have = ffmpeg_filters()
    missing = ALLOWED_GRAPH_FILTERS - have - {"ass"}  # ass - faqat libass bilan
    assert not missing, missing
