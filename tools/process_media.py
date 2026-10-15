#!/usr/bin/env python3
"""Handy Helperly media editor (photos, videos, testimonials) -> branded, platform-ready files.
Usage: HH_BUILD=<dir with node_modules/@fontsource> python3 process_media.py manifest.json outdir
manifest: {"items":[{"id":"M01","type":"photo|video|testimonial","path":"in.jpg","note":"Interior painting, St. Charles",
  "label":"Project photo","quote":"...","attribution":"Jane, St. Charles"}]}
Writes outdir/<id>_feed.jpg (1080x1350) + <id>_story.jpg (1080x1920) for photos/testimonials,
outdir/<id>_reel.mp4 (1080x1920, <=60s + 3s end card) for videos, and outdir/report.json with FLAGS for human review.
Rules: never alters meaning; testimonial text is used verbatim; people/privacy checks are manual flags (no face detection available offline).
No speech transcription is available offline: captions come only from the item's note."""
import json, os, sys, subprocess, html, shutil, tempfile
from PIL import Image, ImageOps, ImageEnhance, ImageFilter
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
B = os.environ.get("HH_BUILD", ".")
F = B + "/node_modules/@fontsource"
NAVY, ORANGE, OFF, CHAR = "#00224A", "#FF5A00", "#F7F5F1", "#182133"
FEED, STORY = (1080, 1350), (1080, 1920)
LOGO_SVG = '<svg viewBox="0 0 48 48" width="64" height="64" fill="none"><path d="M24 6L42 20V40C42 41.1046 41.1046 42 40 42H8C6.89543 42 6 41.1046 6 40V20L24 6Z" fill="#FFFFFF"/><circle cx="24" cy="6" r="3.2" fill="#EF6C3A"/><circle cx="10" cy="17" r="2.4" fill="#EF6C3A"/><circle cx="38" cy="17" r="2.4" fill="#EF6C3A"/><path d="M24 6L10 17M24 6L38 17" stroke="#EF6C3A" stroke-width="1.6" stroke-linecap="round"/><path d="M19 42V28C19 26.3431 20.3431 25 22 25H26C27.6569 25 29 26.3431 29 28V42" fill="#00224A"/></svg>'
FONTS = f'''@font-face{{font-family:Oswald;font-weight:700;src:url(file://{F}/oswald/files/oswald-latin-700-normal.woff2)}}
@font-face{{font-family:Inter;font-weight:500;src:url(file://{F}/inter/files/inter-latin-500-normal.woff2)}}
@font-face{{font-family:Inter;font-weight:700;src:url(file://{F}/inter/files/inter-latin-700-normal.woff2)}}'''
e = html.escape

def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode: raise RuntimeError(r.stderr[-800:])
    return r.stdout

def html_png(body, size, path):
    from playwright.sync_api import sync_playwright
    w, h = size
    doc = f"<!doctype html><meta charset=utf-8><style>{FONTS}*{{box-sizing:border-box;margin:0}}body{{width:{w}px;height:{h}px;overflow:hidden;font-family:Inter}}</style>{body}"
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page(viewport={"width": w, "height": h})
        hp = tempfile.mktemp(suffix=".html", dir=os.path.dirname(os.path.abspath(path)))
        open(hp, "w").write(doc); pg.goto("file://" + hp); pg.evaluate("document.fonts.ready"); pg.wait_for_timeout(150)
        pg.screenshot(path=path); b.close(); os.remove(hp)

def band_html(w, h, band, pad_bottom=0):
    """Branded footer band drawn over a finished photo background."""
    return (f'<div style="position:absolute;left:0;right:0;bottom:{pad_bottom}px;height:{band}px;background:{NAVY};display:flex;align-items:center;'
            f'justify-content:space-between;padding:0 48px;color:#fff"><div style="display:flex;align-items:center;gap:16px">{LOGO_SVG}'
            f'<span style="font:700 34px Oswald;letter-spacing:.04em;text-transform:uppercase">Handy Helperly</span></div>'
            f'<span style="font:700 28px Inter">handyhelperly.com</span></div>')

def fit_cover(img, size, blur_bg=True):
    """Cover-crop when aspect is close; otherwise blurred-background fit so nothing important is cut."""
    w, h = size; iw, ih = img.size
    if abs((iw / ih) / (w / h) - 1) < 0.35 or not blur_bg:
        return ImageOps.fit(img, size, Image.LANCZOS, centering=(0.5, 0.5))
    bg = ImageOps.fit(img, size, Image.LANCZOS).filter(ImageFilter.GaussianBlur(40))
    bg = ImageEnhance.Brightness(bg).enhance(0.6)
    s = min(w / iw, h / ih); fg = img.resize((int(iw * s), int(ih * s)), Image.LANCZOS)
    bg.paste(fg, ((w - fg.width) // 2, (h - fg.height) // 2)); return bg

def enhance(img):
    img = ImageOps.exif_transpose(img).convert("RGB")
    img = ImageOps.autocontrast(img, cutoff=1)
    img = ImageEnhance.Color(img).enhance(1.05)
    return img.filter(ImageFilter.UnsharpMask(radius=1.4, percent=60, threshold=3))

def do_photo(it, out):
    flags = []
    img = enhance(Image.open(it["path"]))
    flags.append("Confirm anyone who appears in the photo agreed to be shown (people are not detected automatically)")
    flags.append("Check for house numbers, license plates, addresses and mail in the photo (not detectable automatically)")
    tmp = tempfile.mkdtemp()
    for name, size, band in (("feed", FEED, 110), ("story", STORY, 150)):
        w, h = size
        bg = fit_cover(img, (w, h))
        bgp = f"{tmp}/{name}_bg.jpg"; bg.save(bgp, quality=95)
        lab = e(it.get("label", "Project photo"))
        extra = f'<div style="position:absolute;left:48px;top:{48 if name=="feed" else 260}px;background:rgba(0,34,74,.9);color:#fff;font:700 28px Inter;letter-spacing:.1em;text-transform:uppercase;padding:12px 20px;border-radius:6px">{lab}</div>'
        body = f'<div style="position:relative;width:{w}px;height:{h}px;background:url(file://{bgp}) center/cover">{extra}{band_html(w,h,band,0 if name=="feed" else 200)}</div>'
        html_png(body, size, f"{out}/{it['id']}_{name}.png")
    shutil.rmtree(tmp)
    return {"files": [f"{it['id']}_feed.png", f"{it['id']}_story.png"], "flags": flags}

def do_testimonial(it, out):
    q = it["quote"].strip().strip('"“”'); who = it.get("attribution", "").strip()
    size_cls = "88px" if len(q) < 90 else "68px" if len(q) < 180 else "54px" if len(q) < 300 else "44px"
    flags = []
    if len(q) > 420: flags.append("Quote is long; shown in a small size. Consider a shorter excerpt that you approve")
    if not it.get("permission_to_post"): flags.append("NO PERMISSION RECORDED - do not post")
    for name, size, padb in (("feed", FEED, 60), ("story", STORY, 300)):
        w, h = size
        body = (f'<div style="width:{w}px;height:{h}px;background:{NAVY};color:#fff;padding:{110 if name=="feed" else 330}px 90px {padb+140}px;display:flex;flex-direction:column;justify-content:center;position:relative">'
                f'<div style="font:700 36px Inter;letter-spacing:.14em;text-transform:uppercase;color:{ORANGE};margin-bottom:36px">Customer testimonial</div>'
                f'<div style="font:700 {size_cls}/1.12 Oswald;text-transform:none">“{e(q)}”</div>'
                + (f'<div style="font:500 40px Inter;margin-top:44px;color:#E8ECF2">— {e(who)}</div>' if who else '')
                + f'<div style="font:500 26px Inter;margin-top:30px;color:#9FB2CC">Shared with the customer’s permission.</div>'
                + band_html(w, h, 110 if name == "feed" else 150, 0 if name == "feed" else 200) + '</div>')
        html_png(body, size, f"{out}/{it['id']}_{name}.png")
    return {"files": [f"{it['id']}_feed.png", f"{it['id']}_story.png"], "flags": flags,
            "note": "Quote used verbatim. Do not edit wording without the customer's OK."}

def probe(path):
    j = json.loads(run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", path]))
    v = next(s for s in j["streams"] if s["codec_type"] == "video")
    rot = 0
    for sd in v.get("side_data_list", []) or []:
        rot = int(sd.get("rotation", 0)) or rot
    w, h = int(v["width"]), int(v["height"])
    if abs(rot) in (90, 270): w, h = h, w
    return {"w": w, "h": h, "dur": float(j["format"]["duration"]), "audio": any(s["codec_type"] == "audio" for s in j["streams"])}

def do_video(it, out):
    p = probe(it["path"]); flags = []
    dur = min(p["dur"], 60.0)
    if p["dur"] > 60: flags.append(f"Source is {p['dur']:.0f}s; trimmed to the first 60s - pick the clip you want before upload for a better cut")
    if p["dur"] < 3: flags.append("Very short clip")
    tmp = tempfile.mkdtemp(); main = f"{tmp}/main.mp4"
    # reframe to 1080x1920: portrait -> cover; landscape/square -> blurred-background fit
    if p["w"] / p["h"] <= 0.62:
        vf = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30"
    else:
        vf = ("split[a][b];[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=30:2,eq=brightness=-0.15[bg];"
              "[b]scale=1080:-2:force_original_aspect_ratio=decrease[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1,fps=30")
    vf += ",eq=contrast=1.04:saturation=1.05"
    note = it.get("note", "").strip()
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", it["path"], "-t", str(dur)]
    if not p["audio"]: cmd += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-shortest"]
    cmd += ["-filter_complex", f"[0:v]{vf}[v]", "-map", "[v]", "-map", "0:a:0" if p["audio"] else "1:a:0",
            "-af", "loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000", "-ar", "48000", "-ac", "2",
            "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", main]
    run(cmd)
    flags.append("Confirm anyone who appears in the video agreed to be shown (people are not detected automatically)")
    flags.append("Watch the whole video: check for house numbers, license plates, addresses, mail and private items")
    if not p["audio"]: flags.append("No audio in source; silent track added")
    flags.append("No speech captions: transcription is not available here; viewers see only the on-screen job label")
    # title lower-third (from note) + logo mark, burned in via an overlay PNG
    ov = f"{tmp}/ov.png"
    lab = e(it.get("label", "Project video"))
    body = (f'<div style="position:relative;width:1080px;height:1920px;background:transparent">'
            f'<div style="position:absolute;left:60px;top:260px;display:flex;align-items:center;gap:14px">{LOGO_SVG}</div>'
            + (f'<div style="position:absolute;left:60px;bottom:560px;max-width:860px;background:rgba(0,34,74,.92);color:#fff;padding:22px 28px;border-radius:10px">'
               f'<div style="font:700 26px Inter;letter-spacing:.12em;text-transform:uppercase;color:{ORANGE};margin-bottom:8px">{lab}</div>'
               f'<div style="font:500 38px/1.2 Inter">{e(note[:110])}</div></div>' if note else '') + '</div>')
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.launch(); pg = b.new_page(viewport={"width": 1080, "height": 1920})
        hp = f"{tmp}/ov.html"; open(hp, "w").write(f"<!doctype html><meta charset=utf-8><style>{FONTS}*{{margin:0}}html,body{{background:transparent}}</style>{body}")
        pg.goto("file://" + hp); pg.evaluate("document.fonts.ready"); pg.wait_for_timeout(150); pg.screenshot(path=ov, omit_background=True); b.close()
    ovd = f"{tmp}/overlaid.mp4"
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", main, "-i", ov, "-filter_complex",
         f"[0:v][1:v]overlay=0:0:enable='between(t,0.3,{max(1.0, min(dur - 0.5, 6.0))})'[v]", "-map", "[v]", "-map", "0:a",
         "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-pix_fmt", "yuv420p", "-c:a", "copy", ovd])
    # end card from the same renderer as the explainer videos
    import makevideo
    spec = {"scenes": [{"type": "outro", "dur": 3, "headline": "Start your request", "cta": "handyhelperly.com",
                        "line": "Greater St. Louis & St. Charles County · (636) 459-1530"}]}
    json.dump(spec, open(f"{tmp}/end.json", "w")); makevideo.main(f"{tmp}/end.json", f"{tmp}/end_v.mp4")
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", f"{tmp}/end_v.mp4", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-shortest",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", f"{tmp}/end.mp4"])
    final = f"{out}/{it['id']}_reel.mp4"
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", ovd, "-i", f"{tmp}/end.mp4", "-filter_complex",
         "[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[v][a]", "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "medium",
         "-crf", "21", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", final])
    # thumbnail
    run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(min(1.0, dur / 2)), "-i", final, "-frames:v", "1", f"{out}/{it['id']}_thumb.jpg"])
    shutil.rmtree(tmp)
    size_mb = os.path.getsize(final) / 1e6
    if size_mb > 250: flags.append(f"Output is {size_mb:.0f} MB; TikTok/Reels limits may apply")
    return {"files": [f"{it['id']}_reel.mp4", f"{it['id']}_thumb.jpg"], "flags": flags, "duration_s": round(dur + 3, 1), "size_mb": round(size_mb, 1)}

def main(manifest, out):
    os.makedirs(out, exist_ok=True); rep = []
    for it in json.load(open(manifest))["items"]:
        if it.get("permission_to_post") is False:
            rep.append({"id": it["id"], "skipped": "no permission to post recorded"}); continue
        try:
            fn = {"photo": do_photo, "video": do_video, "testimonial": do_testimonial}[it["type"]]
            r = fn(it, out); r["id"] = it["id"]; r["type"] = it["type"]; rep.append(r)
        except Exception as ex:
            rep.append({"id": it["id"], "error": str(ex)[:600]})
    json.dump(rep, open(f"{out}/report.json", "w"), indent=1); print(json.dumps(rep, indent=1))
if __name__ == "__main__": main(sys.argv[1], sys.argv[2])
