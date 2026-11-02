#!/usr/bin/env python3
"""make_report.py — harbor-watch human report: ONE self-contained HTML file.

Inputs
------
--verdicts   JSONL, one record per tile decision:
               {"frame": 0, "tile": 5, "changed": true, "score": 0.97}
             `frame` may be int or str. `tile` may be an int (row-major over
             the grid), a [row, col] pair, or a "row,col" / "row_col" string.
             `score` is optional (shown when present).
--manifest   JSON describing the frame images and the tiling:
               {"grid": [4, 4],
                "frames": [{"frame": 0, "image": "path/to/frame0.png"}, ...]}
             Image paths are resolved relative to the manifest's directory.
--ground-truth  JSON, either shape:
               {"changed": {"0": [5, 6], "1": []}, "scene_cuts": [12]}
               {"frames": {"0": {"changed_tiles": [5, 6]}}}
             `changed` maps a frame key to the tiles that truly changed in
             that frame; `scene_cuts` (optional) lists frames that begin a
             new scene.
--compare    OPTIONAL JSON strategy comparison (rolling vs batched etc.):
               {"strategies": {"rolling": {"embeds_spent": 40,
                                            "ttfv_ms": 812.0},
                               "batched": {"embeds_spent": 160,
                                            "ttfv_ms": 2910.0}}}
             `ttfv_ms` = time to first verdict; the alias
             `time_to_first_verdict_ms` is also accepted.
--out        Output HTML path. --title  Report title (default "Harbor Watch").

Output: a single HTML file with NO external assets — images are base64
data URIs, overlays are absolutely-positioned divs (no canvas, no JS),
so it renders offline in any browser.

Metrics: per-tile precision / recall / F1 of `changed` against ground
truth, plus frame-level detection (a frame counts as flagged if any of
its tiles is predicted changed; truth = any truly-changed tile or a
scene-cut frame). Frames/tiles absent from ground truth are excluded
from scoring and marked "unscored" rather than silently counted.
"""
import argparse
import base64
import html
import json
import mimetypes
import sys
from pathlib import Path


# ---------------------------------------------------------------- schema glue

def norm_tile(tile, rows, cols):
    """Normalise a tile reference to a row-major int index."""
    if isinstance(tile, int):
        return tile
    if isinstance(tile, (list, tuple)) and len(tile) == 2:
        r, c = int(tile[0]), int(tile[1])
        return r * cols + c
    if isinstance(tile, str):
        for sep in (",", "_"):
            if sep in tile:
                r, c = tile.split(sep, 1)
                return int(r) * cols + int(c)
        return int(tile)
    raise ValueError(f"unrecognised tile reference: {tile!r}")


def load_verdicts(path, rows, cols):
    """Return {frame_key: {tile_idx: {"changed": bool, "score": float|None}}}."""
    out = {}
    for lineno, line in enumerate(Path(path).read_text().splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError as e:
            raise SystemExit(f"{path}:{lineno}: bad JSON: {e}")
        frame = str(rec["frame"])
        tile = norm_tile(rec["tile"], rows, cols)
        out.setdefault(frame, {})[tile] = {
            "changed": bool(rec.get("changed", False)),
            "score": rec.get("score"),
        }
    return out


def load_ground_truth(path, rows, cols):
    """Return ({frame_key: set(tile_idx)}, set(scene_cut_frame_keys))."""
    if not path:
        return {}, set()
    gt = json.loads(Path(path).read_text())
    changed = {}
    raw = gt.get("changed")
    if raw is None and isinstance(gt.get("frames"), dict):
        raw = {k: (v.get("changed_tiles") or v.get("changed") or [])
               for k, v in gt["frames"].items()}
    for frame, tiles in (raw or {}).items():
        changed[str(frame)] = {norm_tile(t, rows, cols) for t in tiles}
    cuts = {str(f) for f in gt.get("scene_cuts", [])}
    return changed, cuts


def load_compare(path):
    if not path:
        return {}
    data = json.loads(Path(path).read_text())
    strategies = data.get("strategies", data)
    out = {}
    for name, s in strategies.items():
        if not isinstance(s, dict):
            continue
        ttfv = s.get("ttfv_ms", s.get("time_to_first_verdict_ms"))
        out[name] = {"embeds_spent": s.get("embeds_spent"), "ttfv_ms": ttfv}
    return out


# ------------------------------------------------------------------- scoring

def score_tiles(verdicts, gt_changed):
    """Per-tile TP/FP/FN over frames present in ground truth."""
    tp = fp = fn = tn = 0
    for frame, truth in gt_changed.items():
        pred = verdicts.get(frame, {})
        all_tiles = set(pred) | truth
        for tile in all_tiles:
            p = pred.get(tile, {}).get("changed", False)
            t = tile in truth
            if p and t:
                tp += 1
            elif p and not t:
                fp += 1
            elif not p and t:
                fn += 1
            else:
                tn += 1
    precision = tp / (tp + fp) if (tp + fp) else None
    recall = tp / (tp + fn) if (tp + fn) else None
    f1 = (2 * precision * recall / (precision + recall)
          if precision and recall else None)
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "precision": precision, "recall": recall, "f1": f1}


def fmt(x, digits=3):
    return "n/a" if x is None else f"{x:.{digits}f}"


# ------------------------------------------------------------------ rendering

def img_data_uri(path):
    mime = mimetypes.guess_type(str(path))[0] or "image/png"
    return f"data:{mime};base64," + base64.b64encode(Path(path).read_bytes()).decode()


CSS = """
body{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;margin:24px;color:#1a1a1a;background:#fafafa}
h1{margin:0 0 4px} .sub{color:#555;margin-bottom:16px}
.scoreboard{display:flex;flex-wrap:wrap;gap:12px;margin:16px 0}
.card{background:#fff;border:1px solid #ddd;border-radius:8px;padding:12px 16px;min-width:140px}
.card .big{font-size:26px;font-weight:700} .card .lbl{color:#666;font-size:12px;text-transform:uppercase;letter-spacing:.05em}
table{border-collapse:collapse;background:#fff} td,th{border:1px solid #ddd;padding:6px 10px;text-align:left}
.frame{background:#fff;border:1px solid #ddd;border-radius:8px;padding:16px;margin:20px 0}
.frame h2{margin:0 0 4px} .verdict{font-weight:700} .changed-v{color:#b00020} .clear-v{color:#1b7a43}
.imgwrap{position:relative;display:inline-block;line-height:0;max-width:100%}
.imgwrap img{max-width:100%;height:auto;display:block}
.tile{position:absolute;border:2px solid rgba(220,0,0,.9);background:rgba(220,0,0,.28);box-sizing:border-box}
.tile span{position:absolute;top:1px;left:3px;color:#fff;font-size:11px;font-weight:700;line-height:1;text-shadow:0 0 3px #900}
.tiles-list{color:#444;font-size:14px} .unscored{color:#888;font-style:italic}
"""


def render(manifest, verdicts, gt_changed, scene_cuts, compare, title):
    rows, cols = manifest.get("grid", [4, 4])
    base = Path(manifest["_base"])
    metrics = score_tiles(verdicts, gt_changed)
    parts = [f"<!DOCTYPE html><html><head><meta charset='utf-8'>"
             f"<title>{html.escape(title)}</title><style>{CSS}</style></head><body>"]
    parts.append(f"<h1>{html.escape(title)}</h1>")
    parts.append("<div class='sub'>Self-contained report — images embedded, "
                 "no external assets. Red tiles = predicted change. "
                 "Scores are per tile against ground truth.</div>")

    # scoreboard
    parts.append("<div class='scoreboard'>")
    for label, value in [
        ("Precision", fmt(metrics["precision"])),
        ("Recall", fmt(metrics["recall"])),
        ("F1", fmt(metrics["f1"])),
        ("True positives", str(metrics["tp"])),
        ("False positives", str(metrics["fp"])),
        ("False negatives", str(metrics["fn"])),
    ]:
        parts.append(f"<div class='card'><div class='big'>{value}</div>"
                     f"<div class='lbl'>{label}</div></div>")
    parts.append("</div>")

    if compare:
        parts.append("<h2>Strategy comparison</h2><table><tr><th>Strategy</th>"
                     "<th>Embeds spent</th><th>Time to first verdict</th></tr>")
        for name, s in compare.items():
            embeds = "n/a" if s["embeds_spent"] is None else str(s["embeds_spent"])
            ttfv = "n/a" if s["ttfv_ms"] is None else f"{s['ttfv_ms']:.0f} ms"
            parts.append(f"<tr><td>{html.escape(name)}</td><td>{embeds}</td>"
                         f"<td>{ttfv}</td></tr>")
        parts.append("</table>")

    # per frame
    for entry in manifest["frames"]:
        frame = str(entry["frame"])
        img_path = base / entry["image"]
        pred = verdicts.get(frame, {})
        changed_tiles = sorted(t for t, v in pred.items() if v["changed"])
        scored = frame in gt_changed
        truth = gt_changed.get(frame, set())
        if scored:
            missed = sorted(truth - set(changed_tiles))
            false_al = sorted(set(changed_tiles) - truth)
        verdict_word = "CHANGE" if changed_tiles else "no change"
        vclass = "changed-v" if changed_tiles else "clear-v"
        parts.append("<div class='frame'>")
        head = f"Frame {html.escape(frame)}"
        if frame in scene_cuts:
            head += " · scene cut"
        parts.append(f"<h2>{head}</h2>")
        parts.append(f"<div class='verdict {vclass}'>Verdict: {verdict_word}"
                     f" ({len(changed_tiles)} tile{'s' if len(changed_tiles)!=1 else ''})</div>")
        if not scored:
            parts.append("<div class='unscored'>unscored — no ground truth for this frame</div>")
        elif missed or false_al:
            bits = []
            if missed:
                bits.append(f"missed tiles: {missed}")
            if false_al:
                bits.append(f"false-alarm tiles: {false_al}")
            parts.append(f"<div class='tiles-list'>vs truth — {'; '.join(bits)}</div>")
        # image + overlays
        parts.append("<div class='imgwrap'>")
        parts.append(f"<img src='{img_data_uri(img_path)}' alt='frame {html.escape(frame)}'>")
        for tile in changed_tiles:
            r, c = divmod(tile, cols)
            rec = pred[tile]
            label = f"{tile}" + (f" · {rec['score']:.2f}" if isinstance(rec.get("score"), (int, float)) else "")
            parts.append(
                f"<div class='tile' style='left:{c*100/cols:.4f}%;top:{r*100/rows:.4f}%;"
                f"width:{100/cols:.4f}%;height:{100/rows:.4f}%'><span>{label}</span></div>")
        parts.append("</div></div>")

    parts.append("</body></html>")
    return "\n".join(parts), metrics


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--verdicts", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--ground-truth")
    ap.add_argument("--compare")
    ap.add_argument("--out", required=True)
    ap.add_argument("--title", default="Harbor Watch")
    args = ap.parse_args(argv)

    manifest = json.loads(Path(args.manifest).read_text())
    manifest["_base"] = str(Path(args.manifest).resolve().parent)
    rows, cols = manifest.get("grid", [4, 4])
    verdicts = load_verdicts(args.verdicts, rows, cols)
    gt_changed, scene_cuts = load_ground_truth(args.ground_truth, rows, cols)
    compare = load_compare(args.compare)
    html_text, metrics = render(manifest, verdicts, gt_changed, scene_cuts,
                                compare, args.title)
    Path(args.out).write_text(html_text)
    print(f"wrote {args.out} ({len(html_text)} bytes)  "
          f"precision={fmt(metrics['precision'])} recall={fmt(metrics['recall'])} "
          f"tp={metrics['tp']} fp={metrics['fp']} fn={metrics['fn']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
