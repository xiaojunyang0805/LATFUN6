"""Colour layout pictures for publication, rendered from the saved project (EDA layer colours): one PNG per copper
layer, Top and Bottom composites, and one multi-page PDF. Pours come from EDA's saved fill (POURED, Rebuild All Copper
first); tracks, vias, pads and drills from the file. All views are seen from the top (Bottom not mirrored).
    python render_pub.py BOARD.eprj OUTDIR [--ppm 40] [--title "LATFUN6 v0.2"]"""
import sys, os, json, math
sys.path.insert(0, os.environ.get('PCB_LAYOUT_SCRIPTS', os.path.expanduser('~/.claude/skills/pcb-layout/scripts')))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageChops
import eprj_core as ec
import lfr

args = sys.argv[1:]
opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
SRC, OUT = args[0], args[1]
PPM = float(opt('--ppm', 40))
TITLE = opt('--title', 'LATFUN6 v0.2')
MIL = 0.0254
PU = 0.254
os.makedirs(OUT, exist_ok=True)

P = ec.Project(SRC); W = lfr.World(SRC); B = ec.Board(SRC)
NAMES = {1: 'Top (L1)', 15: 'Inner1 (L2)', 16: 'Inner2 (L3)', 17: 'Inner3 (L4)', 18: 'Inner4 (L5)', 19: 'Inner5 (L6)',
         20: 'Inner6 (L7)', 2: 'Bottom (L8)'}
COL = {1: (255, 0, 0), 15: (153, 153, 102), 16: (0, 128, 0), 17: (0, 255, 0), 18: (188, 142, 0), 19: (112, 219, 250),
       20: (0, 204, 102), 2: (0, 0, 255)}
BG, BOARD, DRILL, VIA = (0, 0, 0), (28, 28, 28), (0, 0, 0), (200, 200, 200)

# drawing extent: board polygon + everything that hangs over it (SMA bodies, J12 tab)
bp = W.board_poly
xs = [p[0] for p in bp]; ys = [p[1] for p in bp]
for e in W.sh:
    if e['cls'] == 'pad':
        b = e['bbox']; xs += [b[0], b[2]]; ys += [b[1], b[3]]
M = 4.0
X0, Y0, X1, Y1 = min(xs) - M, min(ys) - M, max(xs) + M, max(ys) + M
HEAD = int(14 * PPM / 4)                                  # title band in px
WPX, HPX = int((X1 - X0) * PPM), int((Y1 - Y0) * PPM)
px = lambda x, y: ((x - X0) * PPM, (y - Y0) * PPM + HEAD)


def path_pts(p):
    out = [(p[0], p[1])]; i = 2; mode = 'L'
    while i < len(p):
        if isinstance(p[i], str):
            mode = p[i]; i += 1; continue
        if mode == 'ARC':
            ang = math.radians(p[i]); x1, y1 = p[i + 1], p[i + 2]; i += 3
            x0, y0 = out[-1]
            d = math.hypot(x1 - x0, y1 - y0)
            if abs(ang) > 1e-6 and d > 1e-9:
                r = d / 2 / math.sin(abs(ang) / 2)
                mx, my = (x0 + x1) / 2, (y0 + y1) / 2
                h = math.sqrt(max(r * r - d * d / 4, 0)); ux, uy = -(y1 - y0) / d, (x1 - x0) / d
                done = False
                for s in (1, -1):
                    cx, cy = mx + s * ux * h, my + s * uy * h
                    a0 = math.atan2(y0 - cy, x0 - cx); n = max(int(abs(ang) / math.radians(8)), 2)
                    for sg in (1, -1):
                        pts = [(cx + r * math.cos(a0 + sg * ang * k / n), cy + r * math.sin(a0 + sg * ang * k / n)) for k in range(1, n + 1)]
                        if math.hypot(pts[-1][0] - x1, pts[-1][1] - y1) < max(0.02 * r, 0.05):
                            out.extend(pts); done = True; break
                    if done:
                        break
                if not done:
                    out.append((x1, y1))
            else:
                out.append((x1, y1))
        else:
            out.append((p[i], p[i + 1])); i += 2
    return [(x * PU, -y * PU) for x, y in out]


def stroke(d, a, b, w, fill):
    (x0, y0), (x1, y1) = px(*a), px(*b)
    r = w * PPM / 2
    d.line([(x0, y0), (x1, y1)], fill=fill, width=max(int(round(2 * r)), 1))
    d.ellipse([x0 - r, y0 - r, x0 + r, y0 + r], fill=fill); d.ellipse([x1 - r, y1 - r, x1 + r, y1 + r], fill=fill)


def shape(d, s, fill):
    if s[0] == 'c':
        x, y = px(s[1], s[2]); r = s[3] * PPM
        d.ellipse([x - r, y - r, x + r, y + r], fill=fill)
    elif s[0] == 'k':
        stroke(d, (s[1], s[2]), (s[3], s[4]), 2 * s[5], fill)
    else:
        d.polygon([px(*p) for p in s[1]], fill=fill)


# ---------------------------------------------------------------- per-layer masks (L = 'pour', 'cu')
recs = [json.loads(l) for l in P.text.split('\n') if l.startswith('["POUR')]
pour_layer = {a[1]: a[4] for a in recs if a[0] == 'POUR'}
size = (WPX, HPX + HEAD)
pour = {l: Image.new('1', size, 0) for l in COL}
for a in sorted((a for a in recs if a[0] == 'POURED'), key=lambda a: a[4] is False):
    lay = pour_layer.get(a[2])
    if lay not in pour:
        continue
    if a[4] is False:                                   # thermal spokes
        d = ImageDraw.Draw(pour[lay])
        for pth in a[5]:
            pts = path_pts(pth)
            for p, q in zip(pts, pts[1:]):
                stroke(d, p, q, 0.254, 1)
        continue
    m = Image.new('1', size, 0)                        # even-odd over the record's paths
    for pth in a[5]:
        if pth and len(pth) >= 6:
            t = Image.new('1', size, 0)
            ImageDraw.Draw(t).polygon([px(*p) for p in path_pts(pth)], fill=1)
            m = ImageChops.logical_xor(m, t)
    pour[lay] = ImageChops.logical_or(pour[lay], m)

cu = {l: Image.new('1', size, 0) for l in COL}
dr = {l: ImageDraw.Draw(cu[l]) for l in COL}
for t in B.tracks:
    if t.layer in dr:
        stroke(dr[t.layer], lfr.to_mm(t.x1, t.y1), lfr.to_mm(t.x2, t.y2), t.width * MIL, 1)
for e in W.sh:
    if e['cls'] == 'pad':
        for l in e['layers']:
            if l in dr:
                shape(dr[l], e['s'], 1)
vias = [(lfr.to_mm(v.x, v.y), v.dia * MIL / 2, v.hole * MIL / 2) for v in B.vias]
holes = [(h[0], h[1], h[2]) for h in W.holes]

font = lambda s: ImageFont.load_default(size=int(s))


def board_base():
    im = Image.new('RGB', size, BG)
    ImageDraw.Draw(im).polygon([px(*p) for p in bp], fill=BOARD)
    return im


def paint(im, mask, col):
    im.paste(Image.new('RGB', size, col), (0, 0), mask)


def finish(im, label):
    d = ImageDraw.Draw(im)
    for (x, y), r, hr in vias:
        cx, cy = px(x, y)
        d.ellipse([cx - r * PPM, cy - r * PPM, cx + r * PPM, cy + r * PPM], fill=VIA)
    for x, y, r in holes:
        cx, cy = px(x, y)
        d.ellipse([cx - r * PPM, cy - r * PPM, cx + r * PPM, cy + r * PPM], fill=DRILL)
    d.line([px(*p) for p in bp + bp[:1]], fill=(255, 220, 0), width=max(int(PPM / 12), 1))
    d.rectangle([0, 0, WPX, HEAD], fill=(245, 245, 245))
    d.text((PPM, HEAD * 0.18), f'{TITLE}  |  {label}', fill=(20, 20, 20), font=font(HEAD * 0.5))
    d.text((WPX - PPM * 70, HEAD * 0.3), '145 x 102 mm, 8 layers, viewed from top', fill=(90, 90, 90), font=font(HEAD * 0.35))
    return im


def dim(c, k):
    return tuple(int(v * k) for v in c)


pages = []
order = [1, 15, 16, 17, 18, 19, 20, 2]
# composites: Top = Bottom (dim) under Top; Bottom = Top (dim) under Bottom
for name, front, back in (('top', 1, 2), ('bottom', 2, 1)):
    im = board_base()
    paint(im, pour[back], dim(COL[back], 0.25)); paint(im, cu[back], dim(COL[back], 0.5))
    paint(im, pour[front], dim(COL[front], 0.45)); paint(im, cu[front], COL[front])
    im = finish(im, f'{NAMES[front]} over {NAMES[back]}')
    im.save(os.path.join(OUT, f'latfun6_composite_{name}.png')); pages.append(im)
    print('wrote composite', name, flush=True)
for l in order:
    im = board_base()
    paint(im, pour[l], dim(COL[l], 0.38)); paint(im, cu[l], COL[l])
    im = finish(im, NAMES[l])
    fn = f'latfun6_L{order.index(l) + 1}_{NAMES[l].split()[0].lower()}.png'
    im.save(os.path.join(OUT, fn)); pages.append(im)
    print('wrote', fn, flush=True)
import matplotlib; matplotlib.use('Agg')            # lossless (Flate) pages; PIL's PDF writer is JPEG or raw
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
DPI = PPM * 25.4
with PdfPages(os.path.join(OUT, 'latfun6_layout.pdf')) as pdf:
    for im in pages:
        a = np.asarray(im); h, w = a.shape[:2]
        fig = plt.figure(figsize=(w / DPI, h / DPI), dpi=DPI)
        fig.figimage(a, 0, 0, resize=False)
        pdf.savefig(fig, dpi=DPI); plt.close(fig)
print('wrote latfun6_layout.pdf', len(pages), 'pages')
