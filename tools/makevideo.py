#!/usr/bin/env python3
"""Handy Helperly short-video renderer (1080x1920, 30fps, silent, on-screen text).
Usage: HH_BUILD=<folder with node_modules/@fontsource/{oswald,inter}> python3 makevideo.py spec.json out.mp4
spec.json: {"scenes":[{"type":"title|step|outro","dur":seconds, ...fields}], "caption_safe":true}
Scene fields: title: eyebrow, headline, sub | step: n, total, head, body | outro: headline, cta, line
Keep text inside the center safe area (TikTok/Reels UI covers top ~220px and bottom ~480px)."""
import json, os, sys, subprocess, shutil, html
from playwright.sync_api import sync_playwright
B = os.environ.get("HH_BUILD", ".")
F = B + "/node_modules/@fontsource"
W, H, FPS = 1080, 1920, 30
NAVY, ORANGE, OFF, CHAR = "#00224A", "#FF5A00", "#F7F5F1", "#182133"
LOGO = '''<svg viewBox="0 0 48 48" width="96" height="96" fill="none"><path d="M24 6L42 20V40C42 41.1046 41.1046 42 40 42H8C6.89543 42 6 41.1046 6 40V20L24 6Z" fill="#FFFFFF"/><circle cx="24" cy="6" r="3.2" fill="#EF6C3A"/><circle cx="10" cy="17" r="2.4" fill="#EF6C3A"/><circle cx="38" cy="17" r="2.4" fill="#EF6C3A"/><path d="M24 6L10 17M24 6L38 17" stroke="#EF6C3A" stroke-width="1.6" stroke-linecap="round"/><path d="M19 42V28C19 26.3431 20.3431 25 22 25H26C27.6569 25 29 26.3431 29 28V42" fill="#00224A"/></svg>'''
e = html.escape
def scene_html(i, s):
    t = s["type"]
    if t == "title":
        inner = f'<div class="logo">{LOGO}<span>Handy Helperly</span></div><div class="eyebrow a1">{e(s["eyebrow"])}</div><h1 class="a2">{e(s["headline"])}</h1><p class="a3">{e(s.get("sub",""))}</p>'
    elif t == "step":
        dots = "".join(f'<i class="{"on" if k+1<=s["n"] else ""}"></i>' for k in range(s["total"]))
        inner = f'<div class="eyebrow a1">How it works · {s["n"]} of {s["total"]}</div><div class="num a1">{s["n"]}</div><h2 class="a2">{e(s["head"])}</h2><p class="a3">{e(s["body"])}</p><div class="dots">{dots}</div>'
    else:
        inner = f'<div class="logo">{LOGO}<span>Handy Helperly</span></div><h1 class="a1">{e(s["headline"])}</h1><div class="cta a2">{e(s["cta"])}</div><p class="a3">{e(s["line"])}</p>'
    return f'<section id="s{i}" class="sc {t}">{inner}</section>'
def build(spec):
    secs = "".join(scene_html(i, s) for i, s in enumerate(spec["scenes"]))
    durs = json.dumps([s["dur"] for s in spec["scenes"]])
    css = f'''
@font-face{{font-family:Oswald;font-weight:600;src:url(file://{F}/oswald/files/oswald-latin-600-normal.woff2)}}
@font-face{{font-family:Oswald;font-weight:700;src:url(file://{F}/oswald/files/oswald-latin-700-normal.woff2)}}
@font-face{{font-family:Inter;font-weight:500;src:url(file://{F}/inter/files/inter-latin-500-normal.woff2)}}
@font-face{{font-family:Inter;font-weight:700;src:url(file://{F}/inter/files/inter-latin-700-normal.woff2)}}
*{{box-sizing:border-box;margin:0}}body{{width:{W}px;height:{H}px;background:{NAVY};overflow:hidden;font-family:Inter}}
.sc{{position:absolute;inset:0;padding:300px 90px 560px;display:none;flex-direction:column;justify-content:center;color:#fff}}
.logo{{display:flex;align-items:center;gap:22px;margin-bottom:70px}}.logo span{{font:700 44px Oswald;letter-spacing:.04em;text-transform:uppercase}}
.eyebrow{{font:700 34px Inter;letter-spacing:.14em;text-transform:uppercase;color:{ORANGE};margin-bottom:34px}}
h1{{font:700 118px/1.02 Oswald;text-transform:uppercase}}h2{{font:700 100px/1.04 Oswald;text-transform:uppercase;margin-top:10px}}
p{{font:500 46px/1.32 Inter;margin-top:44px;color:#E8ECF2}}
.num{{font:700 260px/1 Oswald;color:{ORANGE}}}
.dots{{display:flex;gap:18px;margin-top:70px}}.dots i{{width:70px;height:12px;border-radius:6px;background:#2C4A73}}.dots i.on{{background:{ORANGE}}}
.cta{{margin-top:56px;background:{ORANGE};color:#fff;font:700 54px Oswald;text-transform:uppercase;letter-spacing:.03em;padding:30px 44px;border-radius:14px;align-self:flex-start}}
.step,.title{{}}'''
    js = f'''
const D={durs};const starts=[];let acc=0;D.forEach(d=>{{starts.push(acc);acc+=d}});window.TOTAL=acc;
const ease=x=>1-Math.pow(1-x,3);
function setT(t){{
 let idx=starts.findIndex((s,i)=>t>=s&&t<s+D[i]);if(idx<0)idx=D.length-1;
 document.querySelectorAll('.sc').forEach((el,i)=>{{el.style.display=i===idx?'flex':'none'}});
 const el=document.getElementById('s'+idx);const lt=t-starts[idx];const out=Math.min(1,Math.max(0,(D[idx]-lt)/0.3));
 ['a1','a2','a3'].forEach((c,k)=>{{const n=el.querySelector('.'+c);if(!n)return;const p=ease(Math.min(1,Math.max(0,(lt-0.15-k*0.28)/0.55)));
  n.style.opacity=p*out;n.style.transform='translateY('+(40*(1-p))+'px)'}});
}}'''
    return f"<!doctype html><meta charset=utf-8><style>{css}</style>{secs}<script>{js}</script>"
def main(spec_path, out):
    spec = json.load(open(spec_path)); work = os.path.splitext(out)[0] + "_frames"
    shutil.rmtree(work, ignore_errors=True); os.makedirs(work)
    open(work + "/v.html", "w").write(build(spec))
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page(viewport={"width": W, "height": H})
        pg.goto("file://" + os.path.abspath(work + "/v.html")); pg.evaluate("document.fonts.ready")
        total = pg.evaluate("TOTAL"); n = int(total * FPS)
        for f in range(n):
            pg.evaluate(f"setT({f/FPS})"); pg.screenshot(path=f"{work}/f{f:05d}.jpg", type="jpeg", quality=92)
        b.close()
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", f"{work}/f%05d.jpg",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-profile:v", "high", "-crf", "20", "-movflags", "+faststart", out], check=True)
    shutil.rmtree(work); print("wrote", out, f"{total:.1f}s")
if __name__ == "__main__": main(sys.argv[1], sys.argv[2])
