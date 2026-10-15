import json
from pathlib import Path

from _api_helpers import make_client


def test_lexicon_crud(tmp_path: Path, monkeypatch) -> None:
    c, _ = make_client(tmp_path, monkeypatch)
    p = c.post("/v1/projects", json={"name": "A"}).json()["id"]
    r = c.post("/v1/lexicon", json={"show_id": p, "term": "Lahza", "variants": ["laxza", "Lahza", "laxza"],
                                    "kind": "brend"})
    assert r.status_code == 200
    e = r.json()
    assert e["variants"] == ["laxza"] and e["kind"] == "brend" and e["show_id"] == p
    g = c.post("/v1/lexicon", json={"term": "Umumiy", "kind": "atama"}).json()
    assert {x["id"] for x in c.get("/v1/lexicon", params={"project_id": p}).json()} == {e["id"], g["id"]}
    other = c.post("/v1/projects", json={"name": "B"}).json()["id"]
    assert [x["id"] for x in c.get("/v1/lexicon", params={"project_id": other}).json()] == [g["id"]]
    assert len(c.get("/v1/lexicon").json()) == 2
    assert c.post("/v1/lexicon", json={"term": "x", "kind": "noma'lum"}).status_code == 422
    assert c.post("/v1/lexicon", json={"term": "  ", "kind": "ism"}).status_code == 400
    assert c.post("/v1/lexicon", json={"show_id": "yoq", "term": "x", "kind": "ism"}).status_code == 404
    assert c.delete(f"/v1/lexicon/{e['id']}").json() == {"ok": True}
    assert c.delete(f"/v1/lexicon/{e['id']}").status_code == 404


def test_styles_crud_import_export(tmp_path: Path, monkeypatch) -> None:
    c, _ = make_client(tmp_path, monkeypatch)
    tpl = {"font_size": 80, "highlight_color": "#00ff00", "animation": "pop"}
    r = c.post("/v1/styles", json={"name": "Brend", "template": tpl})
    assert r.status_code == 200
    st = r.json()
    assert st["name"] == "Brend" and st["template"]["highlight_color"] == "#00FF00"
    assert st["template"]["name"] == "Brend"
    up = c.put(f"/v1/styles/{st['id']}", json={"name": "Brend 2", "template": {**tpl, "font_size": 90}})
    assert up.json()["template"]["font_size"] == 90
    assert c.put("/v1/styles/yoq", json={"name": "x", "template": tpl}).status_code == 404
    assert c.post("/v1/styles", json={"name": "x", "template": {"font_size": 5}}).status_code == 422

    out = tmp_path / "brend"
    assert c.post(f"/v1/styles/{st['id']}:export", json={"path": str(out)}).json() == {"ok": True}
    data = json.loads((tmp_path / "brend.json").read_text(encoding="utf-8"))
    assert data["name"] == "Brend 2" and data["template"]["font_size"] == 90
    imp = c.post("/v1/styles:import", json={"path": str(tmp_path / "brend.json")}).json()
    assert imp["id"] != st["id"] and imp["name"] == "Brend 2"
    bare = tmp_path / "bare.json"
    bare.write_text(json.dumps({"name": "Yalang'och", "font_size": 64}), encoding="utf-8")
    assert c.post("/v1/styles:import", json={"path": str(bare)}).json()["name"] == "Yalang'och"
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert c.post("/v1/styles:import", json={"path": str(bad)}).status_code == 400
    bad.write_text(json.dumps({"font_size": 1}), encoding="utf-8")
    assert c.post("/v1/styles:import", json={"path": str(bad)}).status_code == 400
    assert c.post("/v1/styles:import", json={"path": str(tmp_path / "yoq.json")}).status_code == 400
    assert len(c.get("/v1/styles").json()) == 3
    assert c.delete(f"/v1/styles/{st['id']}").json() == {"ok": True}
    assert c.delete(f"/v1/styles/{st['id']}").status_code == 404
    assert c.post(f"/v1/styles/{imp['id']}:export",
                  json={"path": str(tmp_path / "yoq" / "a.json")}).status_code == 400


def test_fonts(tmp_path: Path, monkeypatch) -> None:
    c, _ = make_client(tmp_path, monkeypatch)
    import lahza_engine.subtitle.fonts as fonts

    class F:
        def model_dump(self, mode="json"):
            return {"family": "Inter", "path": "/x.ttf", "ok": True, "missing": []}

    monkeypatch.setattr(fonts, "list_fonts", lambda fonts_dir=None: [F()])
    assert c.get("/v1/fonts").json() == [{"family": "Inter", "path": "/x.ttf", "ok": True, "missing": []}]
