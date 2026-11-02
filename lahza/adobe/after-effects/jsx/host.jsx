// Lahza Studio — After Effects host skripti (ExtendScript, ES3).
//
// QOIDALAR (ES3): faqat var/function; let/const, arrow, template literal, Array.map/forEach/filter,
// Object.keys YO'Q (test/host-es3.test.ts tekshiradi). JSON — jsx/json2.jsx (public domain) orqali,
// panel uni bridge.ensureLoaded() da $.evalFile bilan yuklaydi.
//
// API manbalari (tekshirilgan): ae-scripting.docsforadobe.dev — LayerCollection.add/addSolid/addText,
// Layer.startTime/stretch/inPoint/outPoint, Property.setValueAtTime (vaqt = kompozitsiya vaqti),
// setInterpolationTypeAtKey, setTemporalEaseAtKey (TwoD -> 2, ThreeD -> 3, boshqasi -> 1 ta KeyframeEase),
// CompItem.markerProperty + MarkerValue, PropertyGroup.addProperty("ADBE Mask Atom"), "ADBE Mask Shape" + Shape,
// matchName'lar: ADBE Transform Group/Anchor Point/Position/Scale/Rotate Z/Opacity, ADBE Effect Parade,
// ADBE Gaussian Blur 2, ADBE Audio Group/ADBE Audio Levels, ADBE Text Properties/Text Document/Text Animators/
// Text Animator/Text Animator Properties/Text Fill Color/Text Selectors/Text Selector/Text Range Advanced/
// Text Range Units/Text Index Start|End/Text Percent Start|End.
//
// Har bir ommaviy funksiya JSON string qaytaradi: {"ok":true,"comp":"...","warnings":[...]} yoki {"ok":false,"error":"..."}.

var LAHZA_HOST_VERSION = "0.1.0";

// Xavfsiz zona (9:16 ijtimoiy tarmoq UI'si): pastdan 35%, yuqoridan 14%, yonlardan 6%.
var LAHZA_SAFE_BOTTOM = 0.35;
var LAHZA_SAFE_TOP = 0.14;
var LAHZA_SAFE_SIDE = 0.06;

// ---------------------------------------------------------------- umumiy yordamchilar

function lahza__out(obj) {
    return JSON.stringify(obj);
}

function lahza__fail(e) {
    var msg = (e && e.message) ? e.message : String(e);
    if (e && e.line) {
        msg = msg + " (host.jsx:" + e.line + ")";
    }
    return lahza__out({ ok: false, error: msg });
}

function lahza__parse(planJson) {
    if (typeof planJson !== "string") {
        return planJson;
    }
    return JSON.parse(planJson);
}

function lahza__num(x, def) {
    return (typeof x === "number" && !isNaN(x)) ? x : def;
}

function lahza__clamp(x, lo, hi) {
    return x < lo ? lo : (x > hi ? hi : x);
}

function lahza__pad2(n) {
    return n < 10 ? "0" + n : String(n);
}

/** "#RRGGBB" -> [r, g, b] (0..1). Yaroqsiz bo'lsa def. */
function lahza__hex(hex, def) {
    if (typeof hex !== "string") {
        return def;
    }
    var m = /^#?([0-9a-fA-F]{2})([0-9a-fA-F]{2})([0-9a-fA-F]{2})$/.exec(hex);
    if (!m) {
        return def;
    }
    return [parseInt(m[1], 16) / 255, parseInt(m[2], 16) / 255, parseInt(m[3], 16) / 255];
}

function lahza__findById(list, id) {
    for (var i = 0; i < list.length; i++) {
        if (list[i].id === id) {
            return list[i];
        }
    }
    return null;
}

/** Loyiha ildizidagi papkani nomi bo'yicha topadi yoki yaratadi. */
function lahza__folder(name) {
    var items = app.project.items;
    for (var i = 1; i <= app.project.numItems; i++) {
        var it = app.project.item(i);
        if (it instanceof FolderItem && it.name === name && it.parentFolder === app.project.rootFolder) {
            return it;
        }
    }
    return items.addFolder(name);
}

function lahza__compByName(name) {
    for (var i = 1; i <= app.project.numItems; i++) {
        var it = app.project.item(i);
        if (it instanceof CompItem && it.name === name) {
            return it;
        }
    }
    return null;
}

function lahza__uniqueCompName(base) {
    var name = base;
    var n = 2;
    while (lahza__compByName(name)) {
        name = base + " (" + n + ")";
        n++;
    }
    return name;
}

function lahza__fsName(path) {
    try {
        return new File(path).fsName;
    } catch (e) {
        return String(path);
    }
}

/** Loyihada shu fayl allaqachon import qilinganmi — bo'lsa qayta ishlatamiz. */
function lahza__findFootage(path) {
    var want = lahza__fsName(path);
    for (var i = 1; i <= app.project.numItems; i++) {
        var it = app.project.item(i);
        if (it instanceof FootageItem) {
            var f = null;
            try {
                f = it.file;
            } catch (e) {
                f = null;
            }
            if (f && f.fsName === want) {
                return it;
            }
        }
    }
    return null;
}

/** HostMedia -> FootageItem (bir marta import; bor bo'lsa qayta ishlatish). */
function lahza__importMedia(media, cache, warnings, folder) {
    if (cache[media.id]) {
        return cache[media.id];
    }
    var item = lahza__findFootage(media.path);
    if (!item) {
        var f = new File(media.path);
        if (!f.exists) {
            warnings.push("Fayl topilmadi / File not found: " + media.path);
            cache[media.id] = null;
            return null;
        }
        var io = new ImportOptions(f);
        try {
            if (io.canImportAs(ImportAsType.FOOTAGE)) {
                io.importAs = ImportAsType.FOOTAGE;
            }
        } catch (e) {
            // canImportAs eski versiyalarda bo'lmasligi mumkin — standart import
        }
        item = app.project.importFile(io);
        if (folder) {
            try {
                item.parentFolder = folder;
            } catch (e2) {
                // papkaga ko'chirish shart emas
            }
        }
    }
    cache[media.id] = item;
    return item;
}

function lahza__xform(layer) {
    return layer.property("ADBE Transform Group");
}

/** setTemporalEaseAtKey uchun KeyframeEase soni: TwoD -> 2, ThreeD -> 3, qolgani -> 1 (rasmiy hujjat). */
function lahza__easeDims(prop) {
    var t = prop.propertyValueType;
    if (t === PropertyValueType.TwoD) {
        return 2;
    }
    if (t === PropertyValueType.ThreeD) {
        return 3;
    }
    return 1;
}

function lahza__setInterp(prop, keyIndex, interp) {
    if (interp === "hold") {
        prop.setInterpolationTypeAtKey(keyIndex, KeyframeInterpolationType.HOLD, KeyframeInterpolationType.HOLD);
    } else if (interp === "ease") {
        prop.setInterpolationTypeAtKey(keyIndex, KeyframeInterpolationType.BEZIER, KeyframeInterpolationType.BEZIER);
        var n = lahza__easeDims(prop);
        var eIn = [];
        var eOut = [];
        for (var d = 0; d < n; d++) {
            eIn.push(new KeyframeEase(0, 33.33));
            eOut.push(new KeyframeEase(0, 33.33));
        }
        prop.setTemporalEaseAtKey(keyIndex, eIn, eOut);
    } else {
        prop.setInterpolationTypeAtKey(keyIndex, KeyframeInterpolationType.LINEAR, KeyframeInterpolationType.LINEAR);
    }
}

/** Kalit kadr qo'yadi va uning interpolatsiyasini o'rnatadi. */
function lahza__key(prop, t, value, interp) {
    prop.setValueAtTime(t, value);
    var k = prop.nearestKeyIndex(t);
    lahza__setInterp(prop, k, interp);
    return k;
}

/** TransformKey'lar -> Scale/Position/Rotation (vaqt: tBase + key.t, kompozitsiya vaqti). */
function lahza__applyTransform(layer, keys, tBase, srcW, srcH) {
    var xf = lahza__xform(layer);
    var anchor = xf.property("ADBE Anchor Point");
    var pos = xf.property("ADBE Position");
    var scale = xf.property("ADBE Scale");
    var rot = xf.property("ADBE Rotate Z");
    // pos_x/pos_y — manba kadri MARKAZI qayerga tushadi, shuning uchun anchor = manba markazi.
    anchor.setValue([srcW / 2, srcH / 2]);
    if (!keys || keys.length === 0) {
        return;
    }
    var anyRot = false;
    var i;
    for (i = 0; i < keys.length; i++) {
        if (lahza__num(keys[i].rotation, 0) !== 0) {
            anyRot = true;
        }
    }
    if (keys.length === 1) {
        var k0 = keys[0];
        scale.setValue([k0.scale_pct, k0.scale_pct]);
        pos.setValue([k0.pos_x, k0.pos_y]);
        if (anyRot) {
            rot.setValue(k0.rotation);
        }
        return;
    }
    for (i = 0; i < keys.length; i++) {
        var k = keys[i];
        var t = tBase + k.t;
        var interp = k.interp || "linear";
        lahza__key(scale, t, [k.scale_pct, k.scale_pct], interp);
        lahza__key(pos, t, [k.pos_x, k.pos_y], interp);
        if (anyRot) {
            lahza__key(rot, t, lahza__num(k.rotation, 0), interp);
        }
    }
}

function lahza__applyEffects(layer, effects, warnings, label) {
    if (!effects) {
        return;
    }
    for (var i = 0; i < effects.length; i++) {
        var fx = effects[i];
        if (fx.kind === "gaussian_blur") {
            var blur = layer.property("ADBE Effect Parade").addProperty("ADBE Gaussian Blur 2");
            blur.property("ADBE Gaussian Blur 2-0001").setValue(lahza__num(fx.amount, 40));
            try {
                // Repeat Edge Pixels — xira fon chetlari qoraymasin
                blur.property("ADBE Gaussian Blur 2-0003").setValue(1);
            } catch (e) {
                // ANIQLANSIN: "-0003" (Repeat Edge Pixels) faqat skill qoidasida, rasmiy jadvalda yo'q
            }
        } else if (fx.kind === "lumetri_preset") {
            warnings.push(label + ": rang preseti \"" + fx.preset + "\" AE'da qo'llanmadi (qo'lda Lumetri) / color preset not applied");
        } else if (fx.kind === "lut") {
            warnings.push(label + ": LUT " + fx.lut_path + " AE'da qo'llanmadi (qo'lda Lumetri/Apply Color LUT) / LUT not applied");
        }
    }
}

/** Kompozitsiya vaqtidagi to'rtburchak mask (qatlam o'z koordinatasi kompozitsiya bilan bir xil bo'lishi kerak). */
function lahza__maskRect(layer, rect) {
    var x = rect[0];
    var y = rect[1];
    var w = rect[2];
    var h = rect[3];
    var mask = layer.property("ADBE Mask Parade").addProperty("ADBE Mask Atom");
    var shape = new Shape();
    shape.vertices = [[x, y], [x + w, y], [x + w, y + h], [x, y + h]];
    shape.closed = true;
    mask.property("ADBE Mask Shape").setValue(shape);
    return mask;
}

/**
 * Footage'ni qatlam qilib joylaydi: src_in rec_in ga tushadi, speed -> stretch.
 * `offset` — maqsad kompozitsiya vaqtining boshlanishi (precomp uchun clip.rec_in).
 */
function lahza__placeFootage(comp, footage, clip, offset) {
    var layer = comp.layers.add(footage);
    var speed = lahza__num(clip.speed, 1);
    if (speed <= 0) {
        speed = 1;
    }
    var recIn = clip.rec_in - offset;
    var recOut = clip.rec_out - offset;
    layer.stretch = 100 / speed;
    layer.startTime = recIn - clip.src_in / speed;
    layer.inPoint = recIn;
    layer.outPoint = recOut;
    return layer;
}

function lahza__setVolume(layer, db) {
    // ANIQLANSIN: "ADBE Audio Levels" qiymati [chap dB, o'ng dB] (matchName rasmiy, qiymat shakli amaliyotdan)
    var levels = layer.property("ADBE Audio Group").property("ADBE Audio Levels");
    levels.setValue([db, db]);
}

function lahza__disableAudio(layer) {
    try {
        if (layer.hasAudio) {
            layer.audioEnabled = false;
        }
    } catch (e) {
        // audio yo'q
    }
}

// ---------------------------------------------------------------- matn

function lahza__fontName(style) {
    // ANIQLANSIN: TextDocument.font PostScript nom kutadi ("Inter-Bold"); o'rnatilmagan bo'lsa AE
    // o'rinbosar shrift qo'yadi. Oila nomidan PostScript nomini taxminiy yasaymiz.
    var fam = (style && style.font_family) ? String(style.font_family) : "Arial";
    var bold = style && style.bold !== false;
    var ps = fam.replace(/\s+/g, "");
    if (bold) {
        return ps + "-Bold";
    }
    return ps + "-Regular";
}

/** Text qatlam: shrift, o'lcham, ranglar, kontur; markazlangan. */
function lahza__textLayer(comp, text, opts) {
    var layer = comp.layers.addText(text);
    var srcText = layer.property("ADBE Text Properties").property("ADBE Text Document");
    var doc = srcText.value;
    doc.text = text;
    doc.fontSize = opts.fontSize;
    try {
        doc.font = opts.font;
    } catch (eF) {
        // shrift yo'q — AE standart shriftida qoladi
    }
    doc.applyFill = true;
    doc.fillColor = opts.fill;
    if (opts.strokeWidth > 0) {
        doc.applyStroke = true;
        doc.strokeColor = opts.stroke;
        doc.strokeWidth = opts.strokeWidth;
        doc.strokeOverFill = false;
    } else {
        doc.applyStroke = false;
    }
    // justification qatlam yaratilgandan keyin (skill: "TextDocument ... associated with a layer")
    doc.justification = ParagraphJustification.CENTER_JUSTIFY;
    srcText.setValue(doc);
    return layer;
}

/**
 * Matnni xavfsiz zonaga joylaydi. Kenglik (100% - 2*6%) dan oshsa kichraytiradi.
 * Qaytaradi: matn to'rtburchagi kompozitsiya koordinatasida {left, top, width, height}.
 */
function lahza__placeText(layer, comp, position, t) {
    var W = comp.width;
    var H = comp.height;
    var r = layer.sourceRectAtTime(t, false);
    var maxW = W * (1 - 2 * LAHZA_SAFE_SIDE);
    var s = 1;
    if (r.width > maxW && r.width > 0) {
        s = maxW / r.width;
    }
    var xf = lahza__xform(layer);
    var ax = r.left + r.width / 2;
    var ay;
    var py;
    if (position === "upper") {
        ay = r.top;
        py = H * LAHZA_SAFE_TOP;
    } else if (position === "middle") {
        ay = r.top + r.height / 2;
        py = H / 2;
    } else {
        ay = r.top + r.height;
        py = H * (1 - LAHZA_SAFE_BOTTOM);
    }
    xf.property("ADBE Anchor Point").setValue([ax, ay]);
    xf.property("ADBE Position").setValue([W / 2, py]);
    if (s !== 1) {
        xf.property("ADBE Scale").setValue([s * 100, s * 100]);
    }
    var w = r.width * s;
    var h = r.height * s;
    var top;
    if (position === "upper") {
        top = py;
    } else if (position === "middle") {
        top = py - h / 2;
    } else {
        top = py - h;
    }
    return { left: W / 2 - w / 2, top: top, width: w, height: h };
}

/** Matn ortidagi rangli plashka (solid) — matndan pastda. */
function lahza__boxBehind(comp, textLayer, rect, color, opacity, pad, name, inP, outP) {
    var bw = Math.max(4, Math.round(rect.width + pad * 2));
    var bh = Math.max(4, Math.round(rect.height + pad * 2));
    var box = comp.layers.addSolid(color, name, bw, bh, 1);
    box.inPoint = inP;
    box.outPoint = outP;
    var xf = lahza__xform(box);
    xf.property("ADBE Position").setValue([rect.left + rect.width / 2, rect.top + rect.height / 2]);
    xf.property("ADBE Opacity").setValue(lahza__clamp(opacity, 0, 1) * 100);
    box.moveAfter(textLayer);
    return box;
}

function lahza__styleOf(plan) {
    var s = (plan.captions && plan.captions.style) ? plan.captions.style : {};
    return s;
}

function lahza__textOpts(style, scaleK) {
    return {
        font: lahza__fontName(style),
        fontSize: Math.round(lahza__num(style.font_size, 72) * scaleK),
        fill: lahza__hex(style.primary_color, [1, 1, 1]),
        stroke: lahza__hex(style.outline_color, [0, 0, 0]),
        strokeWidth: lahza__num(style.outline_width, 5)
    };
}

// ---------------------------------------------------------------- o'tishlar va musiqa

/** Klip rejasida (ustma-ust yo'q) cross dissolve uchun oldingi klip qatlamlarini dur ga cho'zadi. */
function lahza__extendPrev(prevClip, prevLayers, dur, mediaById, warnings, label) {
    var pMedia = mediaById[prevClip.media];
    var pSpeed = lahza__num(prevClip.speed, 1) || 1;
    var avail = pMedia ? (pMedia.duration_s - prevClip.src_out) / pSpeed : dur;
    var ext = Math.min(dur, Math.max(0, avail));
    if (ext < dur - 0.001) {
        warnings.push(label + ": o'tish uchun oldingi klip manbasi yetmadi (" + ext.toFixed(2) + " s) / not enough handle");
    }
    for (var j = 0; j < prevLayers.length; j++) {
        if (prevLayers[j].inner) {
            prevLayers[j].inner.outPoint = prevClip.rec_out - prevClip.rec_in + ext;
        }
        prevLayers[j].layer.outPoint = prevClip.rec_out + ext;
    }
}

/** cut va dip_* dan boshqa barcha o'tishlar AE'da cross dissolve (opacity) qilinadi. */
function lahza__isDissolve(tr) {
    if (!tr || !(lahza__num(tr.dur_s, 0) > 0)) {
        return false;
    }
    return tr.kind !== "cut" && tr.kind !== "dip_to_black" && tr.kind !== "dip_to_white";
}

function lahza__opacityFadeIn(layer, t0, dur) {
    var op = lahza__xform(layer).property("ADBE Opacity");
    lahza__key(op, t0, 0, "linear");
    lahza__key(op, t0 + dur, 100, "linear");
}

/** dip_to_black/white: rangli solid, opacity 0 -> 100 (kesim nuqtasida) -> 0. */
function lahza__dip(comp, t, dur, rgb, name) {
    var half = dur / 2;
    var solid = comp.layers.addSolid(rgb, name, comp.width, comp.height, 1);
    var a = Math.max(0, t - half);
    solid.inPoint = a;
    solid.outPoint = Math.min(comp.duration, t + half);
    var op = lahza__xform(solid).property("ADBE Opacity");
    lahza__key(op, a, 0, "linear");
    lahza__key(op, t, 100, "linear");
    lahza__key(op, t + half, 0, "linear");
    return solid;
}

/** Nutq bo'laklari (captions.lines), yaqinlarini birlashtirib. */
function lahza__speechSegments(lines, gap) {
    var segs = [];
    var sorted = [];
    var i;
    for (i = 0; i < lines.length; i++) {
        sorted.push({ t0: lines[i].t0, t1: lines[i].t1 });
    }
    sorted.sort(function (a, b) { return a.t0 - b.t0; });
    for (i = 0; i < sorted.length; i++) {
        var s = sorted[i];
        var last = segs.length ? segs[segs.length - 1] : null;
        if (last && s.t0 - last.t1 <= gap) {
            if (s.t1 > last.t1) {
                last.t1 = s.t1;
            }
        } else {
            segs.push({ t0: s.t0, t1: s.t1 });
        }
    }
    return segs;
}

/**
 * Musiqa Audio Levels kalit kadrlari: fade in -> base, nutqda base-duckDb, fade out.
 * Qaytaradi [[t, db], ...] (saralangan) — test uchun ham qulay.
 */
function lahza__musicLevels(m, segs, duckDb) {
    var SILENT = -60;
    var RAMP_IN = 0.15;
    var RAMP_OUT = 0.25;
    var base = lahza__num(m.volume_db, -14);
    var fi = Math.max(0, lahza__num(m.fade_in_s, 0));
    var fo = Math.max(0, lahza__num(m.fade_out_s, 0));
    var a = m.rec_in;
    var b = m.rec_out;
    var pts = [];
    pts.push([a, fi > 0 ? SILENT : base]);
    if (fi > 0) {
        pts.push([a + fi, base]);
    }
    var lo = a + fi;
    var hi = b - fo;
    if (m.duck) {
        for (var i = 0; i < segs.length; i++) {
            var s0 = Math.max(segs[i].t0 - RAMP_IN, lo);
            var s1 = Math.min(segs[i].t1 + RAMP_OUT, hi);
            if (s1 - s0 <= RAMP_IN + RAMP_OUT) {
                continue;
            }
            pts.push([s0, base]);
            pts.push([s0 + RAMP_IN, base - duckDb]);
            pts.push([s1 - RAMP_OUT, base - duckDb]);
            pts.push([s1, base]);
        }
    }
    if (fo > 0) {
        pts.push([b - fo, base]);
        pts.push([b, SILENT]);
    }
    pts.sort(function (p, q) { return p[0] - q[0]; });
    // bir xil vaqtdagi takrorlarni olib tashlash (oxirgisi qoladi)
    var out = [];
    for (var j = 0; j < pts.length; j++) {
        if (out.length && Math.abs(out[out.length - 1][0] - pts[j][0]) < 0.001) {
            out[out.length - 1] = pts[j];
        } else {
            out.push(pts[j]);
        }
    }
    return out;
}

// ---------------------------------------------------------------- ommaviy funksiyalar

/** Project panelida tanlangan footage yoki faol comp'dagi tanlangan qatlamlar manbalarining fayl yo'llari. */
function lahza_selectedFootagePaths() {
    try {
        var paths = [];
        var seen = {};
        var warnings = [];
        var add = function (item) {
            if (!(item instanceof FootageItem)) {
                return;
            }
            var f = null;
            try {
                f = item.file;
            } catch (e) {
                f = null;
            }
            if (!f) {
                return; // solid / placeholder
            }
            if (item.footageMissing) {
                warnings.push("Fayl yo'q / missing: " + f.fsName);
                return;
            }
            if (!seen[f.fsName]) {
                seen[f.fsName] = true;
                paths.push(f.fsName);
            }
        };
        var sel = app.project.selection;
        var i;
        if (sel) {
            for (i = 0; i < sel.length; i++) {
                add(sel[i]);
            }
        }
        var comp = app.project.activeItem;
        var compName = null;
        if (comp && comp instanceof CompItem) {
            compName = comp.name;
            var layers = comp.selectedLayers;
            for (i = 0; i < layers.length; i++) {
                var src = null;
                try {
                    src = layers[i].source;
                } catch (e2) {
                    src = null;
                }
                if (src) {
                    add(src);
                }
            }
        }
        return lahza__out({ ok: true, comp: compName, paths: paths, warnings: warnings });
    } catch (e) {
        return lahza__fail(e);
    }
}

/** Saqlangan loyiha papkasi (engine out_dir uchun) va AE versiyasi. */
function lahza_projectInfo() {
    try {
        var dir = null;
        var f = app.project.file;
        if (f) {
            dir = f.parent.fsName;
        }
        return lahza__out({ ok: true, comp: null, project_dir: dir, version: app.version, host: LAHZA_HOST_VERSION, warnings: [] });
    } catch (e) {
        return lahza__fail(e);
    }
}

/** Host-reja bo'yicha kompozitsiya yasaydi. */
function lahza_buildComp(planJson) {
    var warnings = [];
    var plan;
    try {
        plan = lahza__parse(planJson);
    } catch (eP) {
        return lahza__fail(new Error("host-reja JSON xato / bad plan JSON: " + eP.message));
    }
    if (!plan || plan.schema !== "lahza.hostplan/1") {
        return lahza__out({ ok: false, error: "lahza.hostplan/1 emas / not a lahza.hostplan/1 plan" });
    }
    app.beginUndoGroup("Lahza: kompozitsiya yasash");
    try {
        var seq = plan.sequence;
        var i;
        var j;
        var duration = lahza__num(seq.duration_s, 0);
        for (i = 0; i < plan.video.length; i++) {
            if (plan.video[i].rec_out > duration) {
                duration = plan.video[i].rec_out;
            }
        }
        if (duration <= 0) {
            throw new Error("Kompozitsiya davomiyligi 0 / empty plan");
        }
        var fps = lahza__clamp(lahza__num(seq.fps, 30), 1, 999);
        var folder = lahza__folder("Lahza");
        var name = lahza__uniqueCompName(seq.name || "Lahza");
        var comp = app.project.items.addComp(name, seq.width, seq.height, 1, duration, fps);
        comp.parentFolder = folder;

        var cache = {};
        var mediaById = {};
        for (i = 0; i < plan.media.length; i++) {
            mediaById[plan.media[i].id] = plan.media[i];
        }

        var prevLayers = [];
        var prevClip = null;
        var nLayers = 0;
        for (i = 0; i < plan.video.length; i++) {
            var clip = plan.video[i];
            var label = clip.label ? (clip.label + " #" + (i + 1)) : ("klip #" + (i + 1));
            var media = mediaById[clip.media];
            if (!media) {
                warnings.push(label + ": media \"" + clip.media + "\" rejada yo'q / unknown media");
                prevLayers = [];
                prevClip = null;
                continue;
            }
            var footage = lahza__importMedia(media, cache, warnings, folder);
            if (!footage) {
                prevLayers = [];
                prevClip = null;
                continue;
            }
            var srcW = footage.width || media.width;
            var srcH = footage.height || media.height;

            // O'tish. Montaj rejasida o'tishli element oldingisi bilan dur_s ga ALLAQACHON ustma-ust
            // (engine: MontageTimeline.item_starts) — bunda qatlamlar o'z-o'zidan ustma-ust, cho'zish shart emas.
            // Klip rejasida (ustma-ust yo'q) oldingi klip manbasi bo'lsa, kesish nuqtasidan keyin cho'ziladi.
            var tr = clip.transition_in;
            var trKind = tr ? tr.kind : "cut";
            var trDur = tr ? lahza__num(tr.dur_s, 0) : 0;
            var dissolve = lahza__isDissolve(tr);
            var isDip = (trKind === "dip_to_black" || trKind === "dip_to_white") && trDur > 0;
            var overlap = prevClip ? Math.max(0, prevClip.rec_out - clip.rec_in) : 0;
            var clipIn = clip.rec_in;
            if (dissolve) {
                if (trKind !== "cross_dissolve") {
                    warnings.push(label + ": o'tish \"" + trKind + "\" AE'da cross dissolve qilindi / replaced with cross dissolve");
                }
                if (!prevClip || !prevLayers.length) {
                    warnings.push(label + ": o'tish oldidan klip yo'q — fade in qilindi / no previous clip, fade-in");
                } else if (overlap < 0.001) {
                    lahza__extendPrev(prevClip, prevLayers, trDur, mediaById, warnings, label);
                }
            }
            if (isDip && overlap > 0.001) {
                // ustma-ust oraliqning o'rtasida (to'liq qora/oq paytda) yangi klipga o'tamiz
                clipIn = clip.rec_in + overlap / 2;
            }

            var clipLayers = [];
            var audioDone = false;
            for (j = 0; j < clip.layers.length; j++) {
                var hl = clip.layers[j];
                var role = hl.role || "main";
                var lname = label + " · " + role;
                var layer;
                var inner = null;
                if (hl.crop_rect) {
                    // split: precomp (kompozitsiya o'lchamida) + kompozitsiya koordinatasida mask.
                    // Keyingi klip dissolve bo'lsa, precomp shu o'tish uzunligicha uzunroq.
                    var nextClip = plan.video[i + 1];
                    var tail = (nextClip && lahza__isDissolve(nextClip.transition_in) && nextClip.rec_in >= clip.rec_out - 0.001) ?
                        nextClip.transition_in.dur_s : 0;
                    var pre = app.project.items.addComp(lahza__uniqueCompName(name + " · " + role + " " + (i + 1)),
                        seq.width, seq.height, 1, Math.max(clip.rec_out - clip.rec_in + tail, 1 / fps), fps);
                    pre.parentFolder = folder;
                    inner = lahza__placeFootage(pre, footage, clip, clip.rec_in);
                    lahza__applyTransform(inner, hl.keys, 0, srcW, srcH);
                    lahza__applyEffects(inner, hl.effects, warnings, lname);
                    layer = comp.layers.add(pre);
                    layer.startTime = clip.rec_in;
                    layer.inPoint = clipIn;
                    layer.outPoint = clip.rec_out;
                    lahza__maskRect(layer, hl.crop_rect);
                } else {
                    layer = lahza__placeFootage(comp, footage, clip, 0);
                    layer.inPoint = clipIn;
                    lahza__applyTransform(layer, hl.keys, clip.rec_in, srcW, srcH);
                    lahza__applyEffects(layer, hl.effects, warnings, lname);
                }
                layer.name = lname;
                try {
                    layer.comment = "lahza:" + clip.id + ":" + role;
                } catch (eC) {
                    // comment ixtiyoriy
                }
                // ovoz faqat bitta qatlamda (main yoki birinchi split qismi); bg/bottom jim
                var wantsAudio = !clip.mute && !audioDone && role !== "bg" && media.has_audio !== false;
                if (wantsAudio) {
                    audioDone = true;
                    if (lahza__num(clip.volume_db, 0) !== 0) {
                        try {
                            lahza__setVolume(layer, clip.volume_db);
                        } catch (eV) {
                            warnings.push(lname + ": ovoz darajasi qo'yilmadi / volume not set");
                        }
                    }
                } else {
                    lahza__disableAudio(layer);
                }
                if (dissolve) {
                    // yangi klipning barcha qatlamlari (bg ham) oldingisi ustida paydo bo'ladi
                    lahza__opacityFadeIn(layer, clip.rec_in, trDur);
                }
                clipLayers.push({ layer: layer, inner: inner });
                nLayers++;
            }
            if (isDip) {
                // dip markazi: ustma-ust bo'lsa uning o'rtasi, aks holda kesish nuqtasi
                lahza__dip(comp, clipIn, overlap > 0.001 ? overlap : trDur, trKind === "dip_to_black" ? [0, 0, 0] : [1, 1, 1],
                    trKind === "dip_to_black" ? "Lahza dip (qora)" : "Lahza dip (oq)");
            }
            prevLayers = clipLayers;
            prevClip = clip;
        }

        // matnlar
        var style = lahza__styleOf(plan);
        var texts = plan.text || [];
        for (i = 0; i < texts.length; i++) {
            var tov = texts[i];
            var k = 1.0;
            if (tov.kind === "hook" || tov.kind === "title") {
                k = 1.2;
            } else if (tov.kind === "card") {
                k = 1.3;
            } else if (tov.kind === "lower_third") {
                k = 0.8;
            }
            var bgCol = lahza__hex(tov.background, null);
            var card = null;
            if (tov.kind === "card") {
                card = comp.layers.addSolid(bgCol || [0.08, 0.08, 0.1], "Lahza karta " + (i + 1), comp.width, comp.height, 1);
                card.inPoint = tov.rec_in;
                card.outPoint = tov.rec_out;
            }
            var tl = lahza__textLayer(comp, tov.text, lahza__textOpts(style, k));
            tl.name = "Lahza matn " + (i + 1) + " (" + tov.kind + ")";
            tl.inPoint = tov.rec_in;
            tl.outPoint = tov.rec_out;
            var rect = lahza__placeText(tl, comp, tov.kind === "card" ? "middle" : (tov.position || "middle"), tov.rec_in);
            if (bgCol && !card) {
                lahza__boxBehind(comp, tl, rect, bgCol, 0.85, 24, "Lahza matn foni " + (i + 1), tov.rec_in, tov.rec_out);
            }
        }

        // markerlar
        var markers = plan.markers || [];
        var labels = { hook: 1, highlight: 9, emphasis: 2, note: 0 };
        for (i = 0; i < markers.length; i++) {
            var mk = markers[i];
            var mv = new MarkerValue(mk.comment ? (mk.name + " — " + mk.comment) : mk.name);
            if (labels[mk.kind] !== undefined) {
                mv.label = labels[mk.kind];
            }
            comp.markerProperty.setValueAtTime(mk.t, mv);
        }

        // musiqa
        var music = plan.music || [];
        var lines = (plan.captions && plan.captions.lines) ? plan.captions.lines : [];
        var segs = lahza__speechSegments(lines, 0.4);
        for (i = 0; i < music.length; i++) {
            var m = music[i];
            var mMedia = mediaById[m.media];
            if (!mMedia) {
                warnings.push("musiqa: media \"" + m.media + "\" rejada yo'q / unknown media");
                continue;
            }
            var mItem = lahza__importMedia(mMedia, cache, warnings, folder);
            if (!mItem) {
                continue;
            }
            var ml = comp.layers.add(mItem);
            ml.name = "Lahza musiqa " + (i + 1);
            ml.startTime = m.rec_in - m.src_in;
            ml.inPoint = m.rec_in;
            ml.outPoint = Math.min(m.rec_out, duration);
            ml.moveToEnd();
            if (m.duck && segs.length === 0) {
                warnings.push("musiqa: duck so'raldi, lekin nutq vaqtlari (captions) yo'q / no speech timing for ducking");
            }
            var pts = lahza__musicLevels(m, segs, 10);
            var lev = ml.property("ADBE Audio Group").property("ADBE Audio Levels");
            if (pts.length === 1) {
                lev.setValue([pts[0][1], pts[0][1]]);
            } else {
                for (j = 0; j < pts.length; j++) {
                    lahza__key(lev, pts[j][0], [pts[j][1], pts[j][1]], "linear");
                }
            }
        }

        var nt = plan.not_translated || [];
        for (i = 0; i < nt.length; i++) {
            warnings.push("O'tmadi / not translated: " + nt[i]);
        }
        try {
            comp.openInViewer();
        } catch (eO) {
            // ko'rsatish shart emas
        }
        return lahza__out({ ok: true, comp: comp.name, layers: comp.numLayers, warnings: warnings });
    } catch (e) {
        return lahza__fail(e);
    } finally {
        app.endUndoGroup();
    }
}

/** Qator matnida har bir so'zning [boshlanish, oxir) belgi indekslari. Topilmasa taxminiy. */
function lahza__wordRanges(text, words) {
    var ranges = [];
    var cursor = 0;
    var low = text.toLowerCase();
    for (var i = 0; i < words.length; i++) {
        var w = String(words[i].text).toLowerCase();
        var at = w.length ? low.indexOf(w, cursor) : -1;
        if (at < 0) {
            // so'z topilmadi (masalan, imlo farqi) — keyingi bo'sh joygacha
            at = cursor;
            var sp = low.indexOf(" ", at);
            var end = sp < 0 ? low.length : sp;
            ranges.push([at, end]);
            cursor = Math.min(low.length, end + 1);
        } else {
            ranges.push([at, at + w.length]);
            cursor = at + w.length;
        }
    }
    return ranges;
}

/** Text Animator + Fill Color (rgba). */
function lahza__colorAnimator(textLayer, name, rgb) {
    var animators = textLayer.property("ADBE Text Properties").property("ADBE Text Animators");
    var animator = animators.addProperty("ADBE Text Animator");
    animator.name = name;
    var fill = animator.property("ADBE Text Animator Properties").addProperty("ADBE Text Fill Color");
    fill.setValue([rgb[0], rgb[1], rgb[2], 1]);
    return animator;
}

/**
 * Range Selector qo'shadi, Units = Index (belgi indekslari, Based On standart — Characters).
 * ANIQLANSIN: "ADBE Text Range Units" dropdown raqamlari (1 = Percentage, 2 = Index) rasmiy hujjatda yo'q;
 * o'rnatib bo'lmasa foiz (Percent Start/End) bilan ishlaymiz.
 */
function lahza__rangeSelector(animator) {
    var selector = animator.property("ADBE Text Selectors").addProperty("ADBE Text Selector");
    var useIdx = false;
    try {
        selector.property("ADBE Text Range Advanced").property("ADBE Text Range Units").setValue(2);
        useIdx = true;
    } catch (e) {
        useIdx = false;
    }
    return {
        useIdx: useIdx,
        start: selector.property(useIdx ? "ADBE Text Index Start" : "ADBE Text Percent Start"),
        end: selector.property(useIdx ? "ADBE Text Index End" : "ADBE Text Percent End")
    };
}

function lahza__unitsNote(state, useIdx, warnings) {
    if (state === null && !useIdx) {
        warnings.push("Range Selector Units=Index o'rnatilmadi — foizda / using percent units");
    }
    return state === null ? useIdx : state;
}

function lahza__isWordChar(ch) {
    return ch !== "" && !/[\s.,!?;:"()\[\]«»—–-]/.test(ch);
}

/** Matndagi kalit so'zlarning (to'liq so'z sifatida) [boshlanish, oxir) indekslari. */
function lahza__keywordRanges(text, keywords) {
    var out = [];
    var low = text.toLowerCase();
    for (var k = 0; k < keywords.length; k++) {
        var w = String(keywords[k]).toLowerCase();
        if (!w.length) {
            continue;
        }
        var from = 0;
        var at = low.indexOf(w, from);
        while (at >= 0) {
            var before = at > 0 ? low.charAt(at - 1) : "";
            var after = low.charAt(at + w.length);
            if (!lahza__isWordChar(before) && !lahza__isWordChar(after)) {
                out.push([at, at + w.length]);
            }
            from = at + w.length;
            at = low.indexOf(w, from);
        }
    }
    return out;
}

/** Karaoke subtitr: har qator — Text qatlam; joriy so'z Text Animator (Fill Color + Range Selector) bilan. */
function lahza_buildKaraoke(planJson, compName) {
    var warnings = [];
    var plan;
    try {
        plan = lahza__parse(planJson);
    } catch (eP) {
        return lahza__fail(new Error("host-reja JSON xato / bad plan JSON: " + eP.message));
    }
    if (!plan || !plan.captions) {
        return lahza__out({ ok: false, error: "captions yo'q / no captions" });
    }
    var lines = plan.captions.lines || [];
    if (lines.length === 0) {
        return lahza__out({ ok: false, error: "Subtitr qatorlari yo'q / no caption lines" });
    }
    app.beginUndoGroup("Lahza: karaoke subtitr");
    try {
        var comp = null;
        if (compName) {
            comp = lahza__compByName(compName);
        }
        if (!comp) {
            var act = app.project.activeItem;
            if (act && act instanceof CompItem) {
                comp = act;
            }
        }
        if (!comp && plan.sequence) {
            comp = lahza__compByName(plan.sequence.name);
        }
        if (!comp) {
            var seq = plan.sequence;
            comp = app.project.items.addComp(lahza__uniqueCompName((seq.name || "Lahza") + " · karaoke"),
                seq.width, seq.height, 1, Math.max(seq.duration_s, lines[lines.length - 1].t1), lahza__num(seq.fps, 30));
            comp.parentFolder = lahza__folder("Lahza");
            warnings.push("Kompozitsiya topilmadi — yangisi yaratildi / no comp found, created new");
        }
        var style = lahza__styleOf(plan);
        var upper = style.uppercase === true;
        var anim = style.animation || "karaoke";
        if (anim === "pop") {
            warnings.push("\"pop\" animatsiyasi AE'da rang highlight sifatida qilindi / pop rendered as color highlight");
        }
        var hiColor = lahza__hex(style.highlight_color, [1, 0.83, 0]);
        var opts = lahza__textOpts(style, 1);
        var position = style.position || "lower";
        var useBox = style.box === true;
        var boxColor = lahza__hex(style.box_color, [0, 0, 0]);
        var boxOpacity = lahza__num(style.box_opacity, 0.6);
        var unitsIndex = null;
        var made = 0;
        var keywords = (style.keywords instanceof Array) ? style.keywords : [];

        for (var i = 0; i < lines.length; i++) {
            var ln = lines[i];
            var text = upper ? String(ln.text).toUpperCase() : String(ln.text);
            if (!text.length || ln.t1 <= ln.t0) {
                warnings.push("Qator " + (i + 1) + " bo'sh yoki vaqti xato — o'tkazildi / skipped");
                continue;
            }
            var tl = lahza__textLayer(comp, text, opts);
            tl.name = "Lahza karaoke " + lahza__pad2(i + 1);
            tl.inPoint = ln.t0;
            tl.outPoint = ln.t1;
            var rect = lahza__placeText(tl, comp, position, ln.t0);
            if (useBox) {
                lahza__boxBehind(comp, tl, rect, boxColor, boxOpacity, Math.round(opts.fontSize * 0.25),
                    "Lahza karaoke foni " + lahza__pad2(i + 1), ln.t0, ln.t1);
            }
            made++;
            var len = text.length;
            // kalit so'zlar — doim highlight rangida (statik selektorlar)
            var kw = lahza__keywordRanges(text, keywords);
            if (kw.length) {
                var kAnim = lahza__colorAnimator(tl, "Lahza kalit so'zlar", hiColor);
                for (var q = 0; q < kw.length; q++) {
                    var ks = lahza__rangeSelector(kAnim);
                    unitsIndex = lahza__unitsNote(unitsIndex, ks.useIdx, warnings);
                    ks.end.setValue(ks.useIdx ? kw[q][1] : (kw[q][1] / len) * 100);
                    ks.start.setValue(ks.useIdx ? kw[q][0] : (kw[q][0] / len) * 100);
                }
            }
            var words = ln.words || [];
            if (anim === "none" || words.length === 0) {
                continue;
            }
            var animator = lahza__colorAnimator(tl, "Lahza highlight", hiColor);
            var sel = lahza__rangeSelector(animator);
            unitsIndex = lahza__unitsNote(unitsIndex, sel.useIdx, warnings);
            var pStart = sel.start;
            var pEnd = sel.end;
            var useIdx = sel.useIdx;
            var conv = function (c) {
                return useIdx ? c : (c / len) * 100;
            };
            var ranges = lahza__wordRanges(text, words);
            // qator boshida hech narsa tanlanmagan
            lahza__key(pStart, ln.t0, 0, "hold");
            lahza__key(pEnd, ln.t0, 0, "hold");
            for (var w = 0; w < words.length; w++) {
                var wd = words[w];
                var t0 = Math.max(ln.t0, wd.t0);
                var r = ranges[w];
                lahza__key(pStart, t0, conv(r[0]), "hold");
                lahza__key(pEnd, t0, conv(r[1]), "hold");
                var next = (w + 1 < words.length) ? words[w + 1].t0 : ln.t1;
                if (next - wd.t1 > 0.08 && wd.t1 < ln.t1) {
                    // so'zlar orasida pauza — highlight o'chadi
                    lahza__key(pStart, wd.t1, 0, "hold");
                    lahza__key(pEnd, wd.t1, 0, "hold");
                }
            }
        }
        if (lahza__num(style.shadow, 0) > 0) {
            warnings.push("Soya (shadow) AE'da qo'shilmadi / shadow not applied");
        }
        return lahza__out({ ok: true, comp: comp.name, lines: made, warnings: warnings });
    } catch (e) {
        return lahza__fail(e);
    } finally {
        app.endUndoGroup();
    }
}

/** Panel moslik tekshiruvi uchun. */
function lahza_ping() {
    return lahza__out({ ok: true, comp: null, host: LAHZA_HOST_VERSION, version: app.version, warnings: [] });
}
