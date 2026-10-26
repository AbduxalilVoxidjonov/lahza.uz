"""V1-6: platform_limits.json - har qiymatning manbasi va tekshirish sanasi qayd etilgan."""

from __future__ import annotations

import json

from lahza_engine.render.limits import LIMITS_FILE, check_limits, load_limits

RAW = json.loads(LIMITS_FILE.read_text(encoding="utf-8"))


def test_every_value_has_provenance() -> None:
    sources = RAW["_sources"]
    assert RAW["_checked_at"] == "2026-10-26"
    for sid, src in sources.items():
        assert src["url"].startswith("https://"), sid
        assert src["checked_at"] == RAW["_checked_at"], sid
        assert src["status"] in ("verified", "unavailable"), sid
    for name, lim in RAW.items():
        if name.startswith("_") or not lim:
            continue
        prov = lim["_provenance"]
        for key, value in lim.items():
            if key.startswith("_"):
                continue
            ref = prov.get(key)
            assert ref, f"{name}.{key}: manba ko'rsatilmagan"
            sid = ref.split(" ")[0]
            if value is None:
                assert ref.startswith("unverified"), f"{name}.{key}"
            elif sid != "lahza_preset":
                assert sources[sid]["status"] == "verified", f"{name}.{key} -> {sid}"


def test_verified_values() -> None:
    lim = load_limits()
    assert "_sources" not in lim
    ig, shorts, yt = lim["instagram_reels"], lim["youtube_shorts"], lim["youtube_video"]
    assert shorts["max_duration_s"] == 180 and shorts["square_or_vertical"] is True
    assert ig["reach_max_duration_s"] == 180 and ig["max_duration_s"] == 20 * 60
    assert ig["max_file_bytes"] is None  # ilova orqali yuklash uchun rasmiy chegara topilmadi
    api = ig["api"]
    assert (api["min_duration_s"], api["max_duration_s"]) == (3, 15 * 60)
    assert api["max_file_bytes"] == 300 * 2**20 and (api["fps_min"], api["fps_max"]) == (23, 60)
    assert yt["max_duration_s"] == 12 * 3600 and yt["max_file_bytes"] == 256 * 2**30


def test_legacy_check_with_json_limits() -> None:
    lim = load_limits()
    assert check_limits(60_000, 1080, 1920, platform="instagram_reels", limits=lim) == []
    assert any("uzun" in w for w in check_limits(181_000, 1080, 1920, platform="youtube_shorts",
                                                 limits=lim))
    # Instagram: 5 GB fayl uchun ilova yuklashida tasdiqlanmagan hajm chegarasi qo'llanmaydi.
    assert check_limits(60_000, 1080, 1920, file_bytes=5 * 2**30, limits=lim) == []
