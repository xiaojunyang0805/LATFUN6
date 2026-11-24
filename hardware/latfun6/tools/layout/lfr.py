"""LATFUN6 offline router library (layout worknote W5b step 2). After SmartPrint pcbc_route_ddr.py / pcbc_route_nets.py,
rebuilt on eprj_core's exact board model (pads, tracks, vias, rules read from the file) and extended with COUPLED
differential pairs.

Coordinates: mm, x right, y DOWN (y_mm = -y_mil * 0.0254). Grid G = 0.05 mm; BGA balls (0.8 mm pitch) sit on grid lines.

Clearance model (per job, rasterised over the job's window only):
  a centreline cell is free for a track of half-width hw when its centre is
    >= CLR(0.152) + hw + M from foreign pad/via copper, >= TT(0.102) + hw + M from foreign tracks,
    >= EDGE(0.3) + hw + M from the board edge.
  M = 0.036 mm covers the sampling error (any point of an octilinear grid step is <= G/sqrt2 from a checked centre;
  distance is 1-Lipschitz).  Every result is re-verified by eprj_check.py (independent exact checker) on a candidate.

Routing: octilinear A* (state = cell + travel direction; straight or 45-degree turns only, BEND cost per turn).
  route_net : single track, optionally multi-layer with new vias (outside BGA fields).
  route_pair: coupled pair. A* runs the CENTRELINE with half-width d/cos(22.5) + w/2 (d = (w+gap)/2), the two legs are
              its miter offsets, polarity is part of the A* state so P stays on the P side at both ends. Each end
              is reached from its pads by a short single-track breakout per leg (BGA balls: through the ball gaps)."""
import sys, os, math, heapq, json, collections, time
import numpy as np
from scipy import ndimage
sys.path.insert(0, os.environ.get('PCB_LAYOUT_SCRIPTS', os.path.expanduser('~/.claude/skills/pcb-layout/scripts')))
import eprj_core as ec

MIL = 0.0254
G = 0.05
M = 0.036
DIRS = [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)]      # circular order (y down)
DLEN = [1.0 if dx == 0 or dy == 0 else math.sqrt(2) for dx, dy in DIRS]
COS225 = math.cos(math.radians(22.5))


def to_mm(x, y):
    return x * MIL, -y * MIL


def to_mil(x, y):
    return x / MIL, -y / MIL


def conv_shape(s):
    """eprj_core shape (mil, y up) -> mm, y down"""
    if s[0] == 'c':
        return ('c', s[1] * MIL, -s[2] * MIL, s[3] * MIL)
    if s[0] == 'k':
        return ('k', s[1] * MIL, -s[2] * MIL, s[3] * MIL, -s[4] * MIL, s[5] * MIL)
    return ('p', [(u * MIL, -v * MIL) for u, v in s[1]])


def shape_bbox(s):
    if s[0] == 'c':
        return (s[1] - s[3], s[2] - s[3], s[1] + s[3], s[2] + s[3])
    if s[0] == 'k':
        return (min(s[1], s[3]) - s[5], min(s[2], s[4]) - s[5], max(s[1], s[3]) + s[5], max(s[2], s[4]) + s[5])
    xs = [p[0] for p in s[1]]; ys = [p[1] for p in s[1]]
    return (min(xs), min(ys), max(xs), max(ys))


def shape_center(s):
    if s[0] == 'c':
        return s[1], s[2]
    if s[0] == 'k':
        return (s[1] + s[3]) / 2, (s[2] + s[4]) / 2
    return sum(p[0] for p in s[1]) / len(s[1]), sum(p[1] for p in s[1]) / len(s[1])


def _seg_dist(X, Y, x1, y1, x2, y2):
    vx, vy = x2 - x1, y2 - y1
    L2 = vx * vx + vy * vy
    if L2 == 0:
        return np.hypot(X - x1, Y - y1)
    t = np.clip(((X - x1) * vx + (Y - y1) * vy) / L2, 0, 1)
    return np.hypot(X - (x1 + t * vx), Y - (y1 + t * vy))


def shape_dist(s, X, Y):
    """distance from points to the shape's copper (0 inside)"""
    if s[0] == 'c':
        return np.maximum(np.hypot(X - s[1], Y - s[2]) - s[3], 0)
    if s[0] == 'k':
        return np.maximum(_seg_dist(X, Y, s[1], s[2], s[3], s[4]) - s[5], 0)
    pts = s[1]; n = len(pts)
    d = None; inside = np.zeros(X.shape, bool)
    for i in range(n):
        (x1, y1), (x2, y2) = pts[i], pts[(i + 1) % n]
        e = _seg_dist(X, Y, x1, y1, x2, y2)
        d = e if d is None else np.minimum(d, e)
        cond = ((y1 > Y) != (y2 > Y))
        with np.errstate(divide='ignore', invalid='ignore'):
            xi = x1 + (Y - y1) * (x2 - x1) / (y2 - y1 if y2 != y1 else 1e-12)
        inside ^= cond & (X < xi)
    return np.where(inside, 0.0, d)


def pt_seg(px, py, a):
    (x1, y1), (x2, y2) = a
    vx, vy = x2 - x1, y2 - y1; L2 = vx * vx + vy * vy
    t = 0 if L2 == 0 else max(0, min(1, ((px - x1) * vx + (py - y1) * vy) / L2))
    return math.hypot(px - x1 - t * vx, py - y1 - t * vy)


def _segseg(a1, a2, b1, b2):
    """exact distance between segments a1-a2 and b1-b2"""
    def orient(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    o1, o2, o3, o4 = orient(a1, a2, b1), orient(a1, a2, b2), orient(b1, b2, a1), orient(b1, b2, a2)
    if o1 * o2 < 0 and o3 * o4 < 0:
        return 0.0
    return min(pt_seg(a1[0], a1[1], (b1, b2)), pt_seg(a2[0], a2[1], (b1, b2)),
               pt_seg(b1[0], b1[1], (a1, a2)), pt_seg(b2[0], b2[1], (a1, a2)))


class World:
    def __init__(self, path, ripup_prefix=None, ripup_nets=None):
        """ripup_prefix: drop the file's tracks/vias whose record id starts with it (lfr writes ids 'e8r...'), so a
        job script can re-route its own earlier result; write_candidate removes those records too."""
        self.path = path
        self.ripup_prefix = ripup_prefix
        self.ripup_nets = ripup_nets       # optional callable(net) -> bool: only those nets' records are ripped
        rip0 = lambda i: bool(ripup_prefix) and str(i).startswith(ripup_prefix)
        self.B = ec.Board(path)
        R = self.B.rules
        self.CLR, self.TT, self.EDGE = R.copper * MIL, R.track_track * MIL, R.edge * MIL
        self.layers = list(self.B.layers)
        self.LI = {l: i for i, l in enumerate(self.layers)}
        self.ALL = frozenset(self.layers)
        self.sh = []                        # dict(net, layers, s, cls, src, bbox)
        self.pad = {}                       # 'DES.NUM' -> pad entry
        for p in self.B.pads:
            s = conv_shape(p.shape)
            e = self._add(p.net, p.layers, s, 'pad', f'{p.des}.{p.num}')
            self.pad[f'{p.des}.{p.num}'] = e
        rip = lambda o: rip0(o.id) and (ripup_nets is None or ripup_nets(o.net))
        self.ripped = sum(rip(t) for t in self.B.tracks) + sum(rip(v) for v in self.B.vias)
        for t in self.B.tracks:
            if rip(t):
                continue
            (x1, y1), (x2, y2) = to_mm(t.x1, t.y1), to_mm(t.x2, t.y2)
            self._add(t.net, frozenset({t.layer}), ('k', x1, y1, x2, y2, t.width * MIL / 2), 'trk', 'file')
        self.HH = R.hole_hole * MIL
        self.holes = []                     # every drilled hole (x, y, r) mm, any net: hole-to-hole rule for new vias
        for v in self.B.vias:
            if rip(v):
                continue
            x, y = to_mm(v.x, v.y)
            self._add(v.net, self.ALL, ('c', x, y, v.dia * MIL / 2), 'via', 'file')
            self.holes.append((x, y, v.hole * MIL / 2))
        for p in self.B.pads:
            if p.hole:
                b = shape_bbox(conv_shape(p.hole))
                self.holes.append(((b[0] + b[2]) / 2, (b[1] + b[3]) / 2, max(b[2] - b[0], b[3] - b[1]) / 2))
        for des, h in getattr(self.B, 'npth', []):          # footprint NPTH: copper keeps the edge rule (0.3 mm)
            s = conv_shape(h)
            self._add(None, self.ALL, s, 'npth', des)
            b = shape_bbox(s)
            self.holes.append(((b[0] + b[2]) / 2, (b[1] + b[3]) / 2, (b[2] - b[0]) / 2))
        self.new_tracks, self.new_vias = [], []      # (net, layer, (x1,y1,x2,y2), w) / (net, x, y, dia, hole)
        self._edge()
        self.fields = []                    # BGA fields (no new vias): (x0, y0, x1, y1) mm
        self.keep = []                      # keep-out rectangles (layers, x0, y0, x1, y1): no new tracks there; a via
        #                                     is blocked if it touches a rectangle on any of its layers
        self.pair_nets = set()              # nets of coupled pairs: other pairs keep PAIR_SEP from them
        self.PAIR_SEP = 0.0

    def _add(self, net, layers, s, cls, src):
        e = dict(net=net, layers=frozenset(layers), s=s, cls=cls, src=src, bbox=shape_bbox(s))
        self.sh.append(e)
        return e

    def _footprint_outline_segments(self):
        """board-outline (layer 11) POLY segments drawn inside footprints (J12's card-edge tab and key notch), mm"""
        segs = []
        for cid, c in self.B.comp.items():
            fp = self.B.P.footprints.get(self.B.attr.get(cid, {}).get('Footprint'), [])
            for a in fp:
                if a[0] != 'POLY' or len(a) < 7 or a[4] != 11:
                    continue
                p = a[6]
                if len(p) >= 5 and p[2] == 'L':
                    loc = [(p[0], p[1]), (p[3], p[4])]
                elif len(p) >= 6 and p[2] == 'ARC':          # [x1, y1, 'ARC', sweep_deg, x2, y2]
                    (xa, ya), sw, (xb, yb) = (p[0], p[1]), math.radians(p[3]), (p[4], p[5])
                    cx, cy = (xa + xb) / 2, (ya + yb) / 2   # semicircle (|sweep| = 180) -> centre at the chord midpoint
                    r = math.hypot(xa - cx, ya - cy); a0 = math.atan2(ya - cy, xa - cx)
                    loc = [(cx + r * math.cos(a0 + sw * k / 12), cy + r * math.sin(a0 + sw * k / 12)) for k in range(13)]
                else:
                    continue
                pl = [ec.Board._place(('c', u, v, 0), c[4], c[5], c[6] or 0, c[3] == 2)[1:3] for u, v in loc]
                pl = [to_mm(*q) for q in pl]
                segs += list(zip(pl, pl[1:]))
        return segs

    def _edge(self):
        """Board = main outline polygon closed through the footprint outline chain (J12 tab + notch).
        edge_dist: conservative distance (mm) from each cell centre to the board edge (0 outside)."""
        from matplotlib.path import Path
        pts = [to_mm(*p) for p in self.B.outline['pts']]
        segs = self._footprint_outline_segments()
        chain, cur, used = [], pts[-1], set()
        close = lambda p, q: math.hypot(p[0] - q[0], p[1] - q[1]) < 0.02
        while segs and not close(cur, pts[0]) and len(chain) < 500:
            nxt = None
            for i, (a, b) in enumerate(segs):
                if i in used:
                    continue
                if close(a, cur):
                    nxt = (i, b); break
                if close(b, cur):
                    nxt = (i, a); break
            if nxt is None:
                break
            used.add(nxt[0]); cur = nxt[1]; chain.append(cur)
        self.outline_closed = bool(chain) and close(cur, pts[0])
        if not self.outline_closed:
            raise SystemExit(f'board outline does not close through footprint outlines (chain {len(chain)} pts)')
        poly = pts + chain[:-1]
        self.board_poly = poly
        ybot = max(p[1] for p in poly)
        self.NX, self.NY = int(math.ceil(150 / G)) + 1, int(math.ceil((ybot + 3) / G)) + 1
        XS = np.arange(self.NX) * G; YS = np.arange(self.NY) * G
        X, Y = np.meshgrid(XS, YS)
        inside = Path(poly).contains_points(np.c_[X.ravel(), Y.ravel()]).reshape(X.shape)
        # EDT between cell centres overestimates the distance to the true boundary by < G/sqrt2 -> subtract it
        self.edge_dist = np.maximum(ndimage.distance_transform_edt(inside) * G - G / math.sqrt(2), 0).astype(np.float32)

    def edge_check(self):
        """Exact, raster-free check of every NEW track/via against the closed board polygon: inside and >= EDGE."""
        from matplotlib.path import Path
        P = self.board_poly
        edges = list(zip(P, P[1:] + P[:1]))
        pth = Path(P)
        bad = []
        items = [(n, ('k', *t, w / 2)) for n, l, t, w in self.new_tracks] + [(n, ('c', x, y, d / 2)) for n, x, y, d, h in self.new_vias]
        for net, s in items:
            if s[0] == 'k':
                ends = [(s[1], s[2]), (s[3], s[4])]; r = s[5]
                dmin = min(min(_segseg((s[1], s[2]), (s[3], s[4]), a, b) for a, b in edges), 1e9)
            else:
                ends = [(s[1], s[2])]; r = s[3]
                dmin = min(pt_seg(s[1], s[2], (a, b)) for a, b in edges)
            ins = all(pth.contains_point(e) for e in ends)
            if not ins or dmin - r < self.EDGE - 1e-6:
                bad.append((net, s[0], [round(v, 3) for v in ends[0]], round(dmin - r, 4), ins))
        return bad

    def add_field(self, des, margin=0.5):
        pts = [shape_center(e['s']) for k, e in self.pad.items() if k.split('.')[0] == des]
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
        self.fields.append((min(xs) - margin, min(ys) - margin, max(xs) + margin, max(ys) + margin))

    # ------------------------------------------------------------------ new copper
    def add_track(self, net, layer, a, b, w):
        self.new_tracks.append((net, layer, (a[0], a[1], b[0], b[1]), w))
        self._add(net, frozenset({layer}), ('k', a[0], a[1], b[0], b[1], w / 2), 'trk', 'new')

    def add_via(self, net, x, y, dia=0.45, hole=0.2):
        self.new_vias.append((net, x, y, dia, hole))
        self._add(net, self.ALL, ('c', x, y, dia / 2), 'via', 'new')
        self.holes.append((x, y, hole / 2))

    def remove_new_track(self, i):
        net, lay, (x1, y1, x2, y2), w = self.new_tracks.pop(i)
        for j in range(len(self.sh) - 1, -1, -1):
            e = self.sh[j]
            if e['src'] == 'new' and e['cls'] == 'trk' and e['net'] == net and lay in e['layers'] and                     e['s'][1:5] == (x1, y1, x2, y2):
                del self.sh[j]
                return
        raise RuntimeError('track shape not found')

    def mark(self):
        return (len(self.sh), len(self.new_tracks), len(self.new_vias), len(self.holes))

    def rollback(self, m):
        del self.sh[m[0]:]; del self.new_tracks[m[1]:]; del self.new_vias[m[2]:]; del self.holes[m[3]:]

    # ------------------------------------------------------------------ rasterising
    def win(self, pts, margin):
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
        ix0 = max(int((min(xs) - margin) / G), 0); iy0 = max(int((min(ys) - margin) / G), 0)
        ix1 = min(int((max(xs) + margin) / G) + 1, self.NX - 1); iy1 = min(int((max(ys) + margin) / G) + 1, self.NY - 1)
        return ix0, iy0, ix1, iy1

    def blocked(self, own, layer, hw, w, sep_extra=0.0, partner=None, pgap=0.18, via=False):
        """bool array over window w: True where a centreline of half-width hw is NOT allowed.
        own: set of nets that are not obstacles; own_block: own-net shape srcs that still block (unused)."""
        ix0, iy0, ix1, iy1 = w
        blk = self.edge_dist[iy0:iy1 + 1, ix0:ix1 + 1] < self.EDGE + hw + M
        xa, ya, xb, yb = ix0 * G, iy0 * G, ix1 * G, iy1 * G
        for (kl, kx0, ky0, kx1, ky1) in self.keep:
            if layer in kl:
                a0 = max(int(math.floor((kx0 - hw - M) / G)) - ix0, 0); a1 = int(math.ceil((kx1 + hw + M) / G)) - ix0 + 1
                b0 = max(int(math.floor((ky0 - hw - M) / G)) - iy0, 0); b1 = int(math.ceil((ky1 + hw + M) / G)) - iy0 + 1
                if a1 > 0 and b1 > 0:
                    blk[b0:b1, a0:a1] = True
        Rmax = max(self.CLR, self.EDGE) + hw + M + sep_extra
        for e in self.near((xa - Rmax, ya - Rmax, xb + Rmax, yb + Rmax)):
            if layer not in e['layers'] or (e['net'] is not None and e['net'] in own):
                continue
            b = e['bbox']
            # track-track uses the track-track rule; a VIA against a track uses the general copper rule (0.152)
            R = ((self.TT if not via else self.CLR) if e['cls'] == 'trk' else self.EDGE if e['cls'] == 'npth' else self.CLR) + hw + M
            if partner is not None and e['net'] == partner and e['cls'] == 'trk':
                # diff-pair rule P/N gap >= gap_min (0.18). Without the sampling margin: the coupled section sits at
                # 0.203, which M would forbid; every breakout is re-verified exactly (_clear_poly) before it is kept.
                R = max(self.TT + M, pgap + 0.003) + hw
            if sep_extra and e['net'] in self.pair_nets:
                R = max(R, self.PAIR_SEP + hw + M)
            jx0 = max(int(math.floor((b[0] - R) / G)), ix0); jx1 = min(int(math.ceil((b[2] + R) / G)), ix1)
            jy0 = max(int(math.floor((b[1] - R) / G)), iy0); jy1 = min(int(math.ceil((b[3] + R) / G)), iy1)
            if jx1 < jx0 or jy1 < jy0:
                continue
            X, Y = np.meshgrid(np.arange(jx0, jx1 + 1) * G, np.arange(jy0, jy1 + 1) * G)
            blk[jy0 - iy0:jy1 - iy0 + 1, jx0 - ix0:jx1 - ix0 + 1] |= shape_dist(e['s'], X, Y) < R
        return blk

    def near(self, box):
        """shapes whose bbox overlaps box (x0, y0, x1, y1): vectorised prefilter over a cached bbox array, rebuilt
        whenever self.sh changed (append, rollback, removal)"""
        key = (len(self.sh), id(self.sh[-1]) if self.sh else 0, id(self.sh[0]) if self.sh else 0)
        if getattr(self, '_bbkey', None) != key:
            self._bbarr = np.array([e['bbox'] for e in self.sh], dtype=np.float64).reshape(-1, 4)
            self._bbkey = key
        a = self._bbarr
        idx = np.nonzero((a[:, 2] >= box[0]) & (a[:, 0] <= box[2]) & (a[:, 3] >= box[1]) & (a[:, 1] <= box[3]))[0]
        sh = self.sh
        return [sh[i] for i in idx]

    def via_ok(self, own, w, dia=0.45, hole=0.2):
        ix0, iy0, ix1, iy1 = w
        r = dia / 2
        ok = np.ones((iy1 - iy0 + 1, ix1 - ix0 + 1), bool)
        for l in self.layers:
            ok &= ~self.blocked(own, l, r - M + 0.001, w, via=True)
        # hole-to-hole (any net, including own-net vias): centre distance >= r_hole_new + r_hole + HH
        X, Y = np.meshgrid(np.arange(ix0, ix1 + 1) * G, np.arange(iy0, iy1 + 1) * G)
        for (hx, hy, hr) in self.holes:
            Rh = hole / 2 + hr + self.HH
            if ix0 * G - Rh <= hx <= ix1 * G + Rh and iy0 * G - Rh <= hy <= iy1 * G + Rh:
                ok &= np.hypot(X - hx, Y - hy) >= Rh
        for (fx0, fy0, fx1, fy1) in self.fields:
            a0, b0 = int(fx0 / G) - ix0, int(fy0 / G) - iy0
            a1, b1 = int(fx1 / G) - ix0 + 1, int(fy1 / G) - iy0 + 1
            ok[max(b0, 0):max(b1, 0), max(a0, 0):max(a1, 0)] = False
        return ok


# ====================================================================== A*
def astar(frees, vok, starts, goal_fn, hpt, w, bend=0.5, via_cost=2.0, maxexp=2_000_000, hweight=1.25, lcost=None,
          start_ok=None):
    """frees: {li: bool free array (window)}; vok: via-ok array or None; starts: [(ix, iy, li, g0)] window indices;
    goal_fn(ix, iy, li, d) -> extra cost or None (not a goal). hpt: heuristic target (ix, iy). Returns [(ix,iy,li)]."""
    BEND, VIA = bend / G, via_cost / G
    tx, ty = hpt
    H = lambda x, y: hweight * (max(abs(x - tx), abs(y - ty)) + 0.41421356 * min(abs(x - tx), abs(y - ty)))
    openq, came, gs = [], {}, {}
    for (x, y, l, g0) in starts:
        if frees[l][y, x]:
            st = (x, y, l, -1)
            if g0 < gs.get(st, 1e18):
                gs[st] = g0; came[st] = None
                heapq.heappush(openq, (g0 + H(x, y), g0, st))
    nexp = 0
    Ls = list(frees)
    hgt, wid = next(iter(frees.values())).shape
    while openq:
        f, gc, cur = heapq.heappop(openq)
        if cur == 'GOAL':
            path = []; c = came['GOAL']
            while c is not None:
                path.append(c[:3]); c = came[c]
            return path[::-1]
        if gc > gs.get(cur, 1e18):
            continue
        nexp += 1
        if nexp > maxexp:
            return None
        x, y, l, d = cur
        ge = goal_fn(x, y, l, d)
        if ge is not None and gc + ge < gs.get('GOAL', 1e18):
            gs['GOAL'] = gc + ge; came['GOAL'] = cur
            heapq.heappush(openq, (gc + ge, -1.0, 'GOAL'))      # -1: never ties a state's g (no str/tuple compare)
        fr = frees[l]; lc = (lcost or {}).get(l, 1.0)
        for k in (range(8) if d < 0 else (d, (d + 1) % 8, (d - 1) % 8)):
            if d < 0 and start_ok is not None and not start_ok(k, x, y, l):
                continue
            dx, dy = DIRS[k]; nx, ny = x + dx, y + dy
            if nx < 0 or ny < 0 or nx >= wid or ny >= hgt or not fr[ny, nx]:
                continue
            if dx and dy and not (fr[y, nx] and fr[ny, x]):
                continue
            ng = gc + DLEN[k] * lc + (BEND if d >= 0 and k != d else 0)
            st = (nx, ny, l, k)
            if ng < gs.get(st, 1e18):
                gs[st] = ng; came[st] = cur
                heapq.heappush(openq, (ng + H(nx, ny), ng, st))
        if vok is not None and vok[y, x]:
            for l2 in Ls:
                if l2 != l and frees[l2][y, x]:
                    st = (x, y, l2, -1); ng = gc + VIA
                    if ng < gs.get(st, 1e18):
                        gs[st] = ng; came[st] = cur
                        heapq.heappush(openq, (ng + H(x, y), ng, st))
    return None


def _turning(pts, lmin=1e-4):
    """total absolute turning (degrees) along a polyline, ignoring zero-length pieces"""
    q = [pts[0]]
    for p in pts[1:]:
        if math.hypot(p[0] - q[-1][0], p[1] - q[-1][1]) > lmin:
            q.append(p)
    tot = 0.0
    for a, b, c in zip(q, q[1:], q[2:]):
        a1 = math.atan2(b[1] - a[1], b[0] - a[0]); a2 = math.atan2(c[1] - b[1], c[0] - b[0])
        tot += abs((a2 - a1 + math.pi) % (2 * math.pi) - math.pi)
    return math.degrees(tot)


def _toward(dvec, v, min_cells=3):
    """direction dvec within 45 deg of vector v (grid cells); always true when v is shorter than min_cells"""
    L = math.hypot(*v)
    if L < min_cells:
        return True
    c = (dvec[0] * v[0] + dvec[1] * v[1]) / (math.hypot(*dvec) * L)
    return c >= math.cos(math.radians(45.5))


def dir_index(u):
    """nearest of the 8 octilinear directions to vector u"""
    a = math.atan2(u[1], u[0])
    return int(round(a / (math.pi / 4))) % 8


def corners(cells):
    """grid path [(x,y)] -> vertices where the direction changes"""
    out = [cells[0]]
    for i in range(1, len(cells) - 1):
        a, b, c = cells[i - 1], cells[i], cells[i + 1]
        if (b[0] - a[0], b[1] - a[1]) != (c[0] - b[0], c[1] - b[1]):
            out.append(b)
    if len(cells) > 1:
        out.append(cells[-1])
    return out


def offset_poly(pts, d):
    """left (+d) offset of a polyline with miter joins (y down: left normal of (dx,dy) is (dy,-dx))"""
    out = []
    n = len(pts)
    for i in range(n):
        if i == 0:
            dx, dy = pts[1][0] - pts[0][0], pts[1][1] - pts[0][1]; L = math.hypot(dx, dy)
            nx, ny = dy / L, -dx / L
        elif i == n - 1:
            dx, dy = pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]; L = math.hypot(dx, dy)
            nx, ny = dy / L, -dx / L
        else:
            ax, ay = pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]; La = math.hypot(ax, ay)
            bx, by = pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]; Lb = math.hypot(bx, by)
            n1 = (ay / La, -ax / La); n2 = (by / Lb, -bx / Lb)
            k = 1 + n1[0] * n2[0] + n1[1] * n2[1]
            nx, ny = (n1[0] + n2[0]) / k, (n1[1] + n2[1]) / k
        out.append((pts[i][0] + d * nx, pts[i][1] + d * ny))
    return out


def side(dirv, vec):
    """+1 if vec points to the LEFT of direction dirv (y down: left normal (dy,-dx)), -1 right, 0 parallel"""
    c = dirv[1] * vec[0] - dirv[0] * vec[1]
    return 0 if abs(c) < 1e-9 else (1 if c > 0 else -1)


class Router:
    def __init__(self, W, log=print):
        self.W = W; self.log = log
        self.results = {}

    # -------------------------------------------------------------- single net, point to point
    def route_net(self, net, a, b, layers, w, margin=6.0, vias=False, a_layers=None, b_layers=None, lcost=None,
                  bend=0.5, maxexp=1_500_000, own=None, partner=None, end_dirs=None):
        """a, b: (x, y) mm. layers: copper ids allowed. a_layers/b_layers: layers the end may be entered on
        (default: all allowed). Returns list of (layer, pts) runs or None. Commits the copper on success."""
        W = self.W
        win = W.win([a, b], margin)
        ix0, iy0 = win[0], win[1]
        own = own or {net}
        frees = {W.LI[l]: ~W.blocked(own, l, w / 2, win, partner=partner) for l in layers}
        vok = W.via_ok(own, win) if vias else None
        cell = lambda p: (int(round(p[0] / G)) - ix0, int(round(p[1] / G)) - iy0)
        (sx, sy), (tx, ty) = cell(a), cell(b)
        al = [W.LI[l] for l in (a_layers or layers)]; bl = {W.LI[l] for l in (b_layers or layers)}
        for li in al:                         # the end cells themselves sit on own copper: force free
            frees[li][sy, sx] = True
        for li in bl:
            frees[li][ty, tx] = True
        starts = [(sx, sy, li, 0.0) for li in al]
        goal = lambda x, y, l, d: 0.0 if (x, y) == (tx, ty) and l in bl and (end_dirs is None or d in end_dirs) else None
        lc = {W.LI[k]: v for k, v in (lcost or {}).items()}
        path = astar(frees, vok, starts, goal, (tx, ty), win, bend=bend, maxexp=maxexp, lcost=lc)
        if path is None:
            return None
        runs = [[path[0]]]
        for p in path[1:]:
            if p[2] == runs[-1][-1][2]:
                runs[-1].append(p)
            else:
                runs.append([p])
        out = []
        for ri, run in enumerate(runs):
            cs = corners([(p[0], p[1]) for p in run])
            pts = [((x + ix0) * G, (y + iy0) * G) for x, y in cs]
            if ri == 0:
                pts[0] = a
            if ri == len(runs) - 1:
                pts[-1] = b
            lay = W.layers[run[0][2]]
            out.append((lay, pts))
        for ri, (lay, pts) in enumerate(out):
            for p, q in zip(pts, pts[1:]):
                if math.hypot(q[0] - p[0], q[1] - p[1]) > 1e-6:
                    W.add_track(net, lay, p, q, w)
            if ri + 1 < len(out):
                W.add_via(net, *pts[-1])
        return out

    def via_near(self, net, x, y, r=1.5, dia=0.45, avoid_fields=True):
        """legal via spot nearest (x, y) within r mm, or None. Does not commit."""
        W = self.W
        win = W.win([(x, y)], r + 0.1)
        ok = W.via_ok({net}, win, dia) if avoid_fields else None
        ix0, iy0 = win[0], win[1]
        best = None
        for yy in range(ok.shape[0]):
            for xx in range(ok.shape[1]):
                if ok[yy, xx]:
                    px, py = (xx + ix0) * G, (yy + iy0) * G
                    dd = math.hypot(px - x, py - y)
                    if dd <= r and (best is None or dd < best[0]):
                        best = (dd, px, py)
        return None if best is None else (best[1], best[2])

    # -------------------------------------------------------------- coupled pair
    def route_pair(self, P, N, endA, endB, layer, w, gap, wleg=None, Ra=3.0, Rb=3.0, lam=3.0, margin=6.0,
                   bend=0.6, maxexp=3_000_000, legmargin=2.5, sep=0.0, amid=None, bmid=None, retries=8):
        """endA/endB: ((xP, yP), (xN, yN)) leg end points (pad centres / via centres) at each end.
        The centreline starts within Ra of A's midpoint and ends within Rb of B's midpoint."""
        W = self.W
        d = (w + gap) / 2
        hwc = d / COS225 + w / 2
        (pa, na), (pb, nb) = endA, endB
        ma = amid or ((pa[0] + na[0]) / 2, (pa[1] + na[1]) / 2)
        mb = bmid or ((pb[0] + nb[0]) / 2, (pb[1] + nb[1]) / 2)
        win = W.win([ma, mb, pa, na, pb, nb], margin + max(Ra, Rb))
        ix0, iy0 = win[0], win[1]
        li = W.LI[layer]
        free = ~W.blocked(set(), layer, hwc, win, sep_extra=sep)      # own P/N copper blocks the corridor too
        hgt, wid = free.shape
        # the coupled section never starts or ends inside a BGA field (+0.3 mm): legs break out of the field first
        inf = np.zeros_like(free)
        for (fx0, fy0, fx1, fy1) in W.fields:
            a0, b0 = max(int((fx0 - 0.3) / G) - ix0, 0), max(int((fy0 - 0.3) / G) - iy0, 0)
            a1, b1 = int((fx1 + 0.3) / G) - ix0 + 1, int((fy1 + 0.3) / G) - iy0 + 1
            if a1 > 0 and b1 > 0:
                inf[b0:b1, a0:a1] = True
        # polarity: sP = +1 when P is on the LEFT of the travel direction; fixed at the start, checked at the goal
        vA = (pa[0] - na[0], pa[1] - na[1]); vB = (pb[0] - nb[0], pb[1] - nb[1])
        cmid = lambda p: (p[0] / G - ix0, p[1] / G - iy0)
        ca, cb = cmid(ma), cmid(mb)
        starts = []
        ra = int(Ra / G) + 1
        for yy in range(max(int(ca[1]) - ra, 0), min(int(ca[1]) + ra + 1, hgt)):
            for xx in range(max(int(ca[0]) - ra, 0), min(int(ca[0]) + ra + 1, wid)):
                dd = math.hypot(xx - ca[0], yy - ca[1]) * G
                if dd <= Ra and free[yy, xx] and not inf[yy, xx]:
                    starts.append((xx, yy, 0, lam * dd / G))
        last = None
        for spread in (1, 2):                     # breakout-to-pair junction: <= 45 deg on every try first, then 90
          banned = np.zeros_like(free)            # start/goal cells banned after a breakout failure there
          for attempt in range(retries):
              st = [s for s in starts if not banned[s[1], s[0]]]
              cands = []
              for sP in (1, -1):
                  def goal(x, y, l, dcur, sP=sP):
                      if dcur < 0:
                          return None
                      dd = math.hypot(x - cb[0], y - cb[1]) * G
                      if dd > Rb or inf[y, x] or banned[y, x]:
                          return None
                      sd = side(DIRS[dcur], vB)
                      if sd != 0 and sd != sP:
                          return None
                      if not _toward(DIRS[dcur], (cb[0] - x, cb[1] - y)):     # arrive heading toward the pads
                          return None
                      return lam * dd / G
                  sok = lambda k, x, y, l=None, sP=sP: side(DIRS[k], vA) in (0, sP) and _toward(DIRS[k], (x - ca[0], y - ca[1]))
                  t0 = time.time()
                  path = astar({0: free}, None, st, goal, cb, win, bend=bend, maxexp=maxexp, start_ok=sok)
                  self.log(f'    pair {P}/{N} try {attempt} sP={sP:+d}: {"found " + str(len(path)) + " cells" if path else "no path"} ({time.time() - t0:.1f} s)')
                  if path and len(path) >= 2:
                      cands.append((len(path), sP, [(p[0], p[1]) for p in path]))
              if not cands:
                  break
              cands.sort()
              for _, sP, cells in cands:
                  r = self._commit_pair(P, N, sP, cells, ix0, iy0, d, layer, w, wleg, pa, na, pb, nb, legmargin, spread)
                  if r['ok']:
                      return r
                  last = r
                  # ban 0.6 mm around the end of the centreline whose breakout failed
                  fpad = r['fail'][1] if r.get('fail') else None
                  endc = cells[0] if fpad in (pa, na) else cells[-1]
                  rr = int(0.6 / G)
                  banned[max(endc[1] - rr, 0):endc[1] + rr + 1, max(endc[0] - rr, 0):endc[0] + rr + 1] = True
        return last

    def _commit_pair(self, P, N, sP, cells, ix0, iy0, d, layer, w, wleg, pa, na, pb, nb, legmargin, spread=1):
        W = self.W
        m0 = W.mark()
        cs = corners(cells)
        cpts = [((x + ix0) * G, (y + iy0) * G) for x, y in cs]
        left, right = offset_poly(cpts, d), offset_poly(cpts, -d)
        legP, legN = (left, right) if sP == 1 else (right, left)
        # commit the coupled section first, then the breakouts per leg
        for net, pts in ((P, legP), (N, legN)):
            for p, q in zip(pts, pts[1:]):
                W.add_track(net, layer, p, q, w)
        wa, wb = (wleg if isinstance(wleg, tuple) else (wleg or w, wleg or w))
        m1 = W.mark()
        ends = [(P, pa, legP[0]), (N, na, legN[0]), (P, pb, legP[-1]), (N, nb, legN[-1])]
        fail = None
        for order in ((0, 1, 2, 3), (1, 0, 3, 2), (0, 1, 3, 2), (1, 0, 2, 3)):
            W.rollback(m1)
            bo = {}
            fail = None
            for i in order:
                net, pad, lp = ends[i]
                mb = W.mark()
                leg = legP if net == P else legN
                u = (leg[1][0] - leg[0][0], leg[1][1] - leg[0][1]) if i < 2 else (leg[-2][0] - leg[-1][0], leg[-2][1] - leg[-1][1])
                k0 = dir_index(u)
                r = self.route_net(net, pad, lp, [layer], wa if i < 2 else wb,
                                   margin=legmargin + math.hypot(pad[0] - lp[0], pad[1] - lp[1]) / 2, bend=0.2,
                                   partner=N if net == P else P,
                                   end_dirs={(k0 + j) % 8 for j in range(-spread, spread + 1)})
                if r is not None and not all(_clear_poly(W, net, N if net == P else P, lay, pts, wa if i < 2 else wb)
                                             for lay, pts in r):
                    r = None                     # exact re-check failed (partner gap or sampling margin)
                if r is not None:                # no loops: a breakout may be at most 1.5x its straight distance (+0.3)
                    Lb = sum(math.hypot(q[0] - p[0], q[1] - p[1]) for lay, pts in r for p, q in zip(pts, pts[1:]))
                    pts_all = [p for lay, pts in r for p in pts] + [lp[0] + u[0], lp[1] + u[1]] if False else                         [p for lay, pts in r for p in pts] + [(lp[0] + u[0] / max(math.hypot(*u), 1e-9) * 0.2,
                                                               lp[1] + u[1] / max(math.hypot(*u), 1e-9) * 0.2)]
                    if Lb > 1.5 * math.hypot(lp[0] - pad[0], lp[1] - pad[1]) + 0.3 or _turning(pts_all) > 181:
                        W.rollback(mb)
                        r = None
                if r is None:
                    fail = (net, pad, lp); break
                bo.setdefault(net, []).append(r)
            if fail is None:
                return dict(ok=True, P=legP, N=legN, centre=cpts, breakouts=bo, sP=sP)
        W.rollback(m0)
        return dict(ok=False, P=legP, N=legN, centre=cpts, fail=fail, sP=sP)


# ====================================================================== output
def write_candidate(W, out_path, tag='lfr'):
    P = ec.Project(W.path)
    lines = P.text.split('\n')
    if W.ripup_prefix:
        pfx = W.ripup_prefix if isinstance(W.ripup_prefix, tuple) else (W.ripup_prefix,)
        pre = tuple('["LINE","' + q for q in pfx) + tuple('["VIA","' + q for q in pfx)
        lines = [l for l in lines if not (l.startswith(pre) and (W.ripup_nets is None or W.ripup_nets(json.loads(l)[3])))]
    nid = P.id_alloc('e8r')
    J = lambda a: json.dumps(a, separators=(',', ':'), ensure_ascii=False)
    new = []
    for net, lay, (x1, y1, x2, y2), w in W.new_tracks:
        (a, b), (c, d) = to_mil(x1, y1), to_mil(x2, y2)
        new.append(J(['LINE', nid(), 0, net, lay, round(a, 4), round(b, 4), round(c, 4), round(d, 4), round(w / MIL, 4), 0]))
    for net, x, y, dia, hole in W.new_vias:
        a, b = to_mil(x, y)
        new.append(J(['VIA', nid(), 0, net, '', round(a, 4), round(b, 4), round(hole / MIL, 4), round(dia / MIL, 4), 0, None, None, 0, []]))
    nl = ec.insert_after_last(lines, new, ('LINE', 'VIA', 'COMPONENT', 'ATTR', 'PAD_NET'))
    return ec.make_candidate(P, '\n'.join(nl), out_path), len(new)


def net_lengths(W, nets):
    L = collections.defaultdict(float)
    for net, lay, (x1, y1, x2, y2), w in W.new_tracks:
        if net in nets:
            L[net] += math.hypot(x2 - x1, y2 - y1)
    for e in W.sh:
        if e['src'] == 'file' and e['cls'] == 'trk' and e['net'] in nets:
            s = e['s']; L[e['net']] += math.hypot(s[3] - s[1], s[4] - s[2])
    return dict(L)


def render(W, out_png, box=None, nets=None, title=''):
    import matplotlib; matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle, Polygon as Pg
    fig, ax = plt.subplots(figsize=(18, 13), dpi=110)
    col = {1: '#d62728', 2: '#1f77b4', 15: '#2ca02c', 16: '#9467bd', 17: '#ff7f0e', 18: '#8c564b'}
    for e in W.sh:
        if e['cls'] != 'pad' and e['src'] != 'file':
            continue
        b = e['bbox']
        if box and (b[2] < box[0] or b[0] > box[2] or b[3] < box[1] or b[1] > box[3]):
            continue
        s = e['s']; top = 1 in e['layers']
        fc = '#bbbbbb' if top else '#e6c3c3'
        if s[0] == 'c':
            ax.add_patch(Circle((s[1], s[2]), s[3], fc=fc if e['cls'] == 'pad' else '#999999', ec='none'))
        elif s[0] == 'k':
            ax.plot([s[1], s[3]], [s[2], s[4]], color='#999999', lw=0.6)
        else:
            ax.add_patch(Pg(s[1], fc=fc, ec='none'))
    for net, lay, (x1, y1, x2, y2), w in W.new_tracks:
        ax.plot([x1, x2], [y1, y2], color=col.get(lay, 'k'), lw=max(w * 6, 0.5), solid_capstyle='round')
    for net, x, y, dia, hole in W.new_vias:
        ax.add_patch(Circle((x, y), dia / 2, fc='none', ec='k', lw=0.6))
    if box:
        ax.set_xlim(box[0], box[2]); ax.set_ylim(box[3], box[1])
    else:
        ax.set_xlim(-2, 148); ax.set_ylim(111, -2)
    ax.set_aspect('equal'); ax.set_title(title)
    fig.savefig(out_png, bbox_inches='tight'); plt.close(fig)


# ====================================================================== checks + tuning
def acute_check(W, nets=None):
    """Turns at track joints of NEW copper (2 segments of one net/layer meeting): returns (acute, right) lists.
    acute = interior angle < 90 deg (turn > 90): never allowed; right = exactly 90 deg."""
    segs = collections.defaultdict(list)
    for net, lay, (x1, y1, x2, y2), w in W.new_tracks:
        if nets is None or net in nets:
            segs[(net, lay)].append(((x1, y1), (x2, y2)))
    acute, right = [], []
    for (net, lay), ss in segs.items():
        ends = collections.defaultdict(list)
        key = lambda p: (round(p[0], 3), round(p[1], 3))
        for a, b in ss:
            if math.hypot(b[0] - a[0], b[1] - a[1]) < 1e-6:
                continue
            ends[key(a)].append((a, b)); ends[key(b)].append((b, a))
        for k, lst in ends.items():
            if len(lst) != 2:
                continue
            (p, q1), (_, q2) = lst
            u = (q1[0] - p[0], q1[1] - p[1]); v = (q2[0] - p[0], q2[1] - p[1])
            cosang = (u[0] * v[0] + u[1] * v[1]) / (math.hypot(*u) * math.hypot(*v))
            ang = math.degrees(math.acos(max(-1, min(1, cosang))))      # interior angle at the joint
            if ang < 89.0:
                acute.append((net, lay, k, round(ang, 1)))
            elif ang < 91.0:
                right.append((net, lay, k))
    return acute, right


def _clear_poly(W, net, partner, lay, pts, w, pgap=0.18, step=0.02, sepnets=(), sep=0.0):
    """exact-ish clearance of a polyline (width w) on layer lay: sampled every `step` mm against every foreign shape
    (sampling error <= step/2 is added to the requirement), plus the board edge."""
    hw = w / 2
    P = []
    for a, b in zip(pts, pts[1:]):
        L = math.hypot(b[0] - a[0], b[1] - a[1]); n = max(int(L / step), 1)
        P += [(a[0] + (b[0] - a[0]) * t / n, a[1] + (b[1] - a[1]) * t / n) for t in range(n + 1)]
    X = np.array([p[0] for p in P]); Y = np.array([p[1] for p in P])
    bb = (X.min() - 1, Y.min() - 1, X.max() + 1, Y.max() + 1)
    for e in W.sh:
        if lay not in e['layers'] or e['net'] == net:
            continue
        b = e['bbox']
        if b[2] < bb[0] or b[0] > bb[2] or b[3] < bb[1] or b[1] > bb[3]:
            continue
        need = (pgap if e['net'] == partner and e['cls'] == 'trk' else W.TT if e['cls'] == 'trk'
                else W.EDGE if e['cls'] == 'npth' else W.CLR)
        if sep and e['cls'] == 'trk' and e['net'] in sepnets and e['net'] != partner:
            need = max(need, sep)
        if (shape_dist(e['s'], X, Y) - hw).min() < need + step / 2:
            return False
    ix = np.clip(np.round(X / G).astype(int), 0, W.NX - 1); iy = np.clip(np.round(Y / G).astype(int), 0, W.NY - 1)
    return bool((W.edge_dist[iy, ix] - hw >= W.EDGE + G).all())


def bump_poly(a, b, n, h, side, c=0.1, top=0.3, gapb=0.3):
    """octilinear serpentine on segment a->b: n trapezoid bumps of height h on `side` (+1 left normal, -1 right),
    centred on the segment. All corners are 45-degree. Returns the polyline a ... b."""
    L = math.hypot(b[0] - a[0], b[1] - a[1]); ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
    nx, ny = uy * side, -ux * side
    wb = 4 * c + top; span = n * wb + (n - 1) * gapb; x = (L - span) / 2
    loc = [(0.0, 0.0), (x, 0.0)]
    for i in range(n):
        loc += [(x + c, c), (x + c, h - c), (x + 2 * c, h), (x + 2 * c + top, h), (x + 3 * c + top, h - c),
                (x + 3 * c + top, c), (x + wb, 0.0)]
        x += wb
        if i < n - 1:
            x += gapb; loc.append((x, 0.0))
    loc.append((L, 0.0))
    return [(a[0] + u * ux + v * nx, a[1] + u * uy + v * ny) for u, v in loc]


def tune_pair(W, P, N, tol=0.05, c=0.1, top=0.3, gapb=0.3, hmax=0.6, margin=0.25, log=print):
    """Add serpentine bumps to the shorter net of a pair until |L(P) - L(N)| <= tol. Bumps go on NEW straight segments
    of the shorter net (longest first), on the side away from the partner. Returns final skew (P - N)."""
    K = 4 * c * (2 - math.sqrt(2))
    for it in range(40):
        L = net_lengths(W, {P, N}); d = L.get(P, 0) - L.get(N, 0)
        if abs(d) <= tol:
            return d
        S, O = (N, P) if d > 0 else (P, N)
        need = abs(d)
        cands = []
        for i, (net, lay, (x1, y1, x2, y2), w) in enumerate(W.new_tracks):
            if net == S:
                Ls = math.hypot(x2 - x1, y2 - y1)
                if Ls >= 4 * c + top + 2 * margin:
                    cands.append((Ls, i))
        cands.sort(reverse=True)
        done = False
        for Ls, i in cands:
            net, lay, (x1, y1, x2, y2), w = W.new_tracks[i]
            a, b = (x1, y1), (x2, y2)
            nmax = int((Ls - 2 * margin + gapb) / (4 * c + top + gapb))
            for side in (1, -1):
                for n in range(nmax, 0, -1):
                    h = (need / n + K) / 2; ce = c
                    if h < 2 * c:                 # small residual: flank-less bump, chamfer = h/2, adds 2h(sqrt2-1)
                        h = need / n / (2 * (math.sqrt(2) - 1)); ce = h / 2
                        if n > 1 or h < 0.02:
                            continue
                    h = min(h, hmax)
                    pl = bump_poly(a, b, n, h, side, ce, top, gapb)
                    pl = [p for k, p in enumerate(pl) if k == 0 or math.hypot(p[0] - pl[k - 1][0], p[1] - pl[k - 1][1]) > 1e-6]
                    if not _clear_poly(W, S, O, lay, pl, w):
                        continue
                    W.remove_new_track(i)
                    for p, q in zip(pl, pl[1:]):
                        W.add_track(S, lay, p, q, w)
                    done = True
                    break
                if done:
                    break
            if done:
                break
        if not done:
            log(f'    tune {P}/{N}: no room for more bumps (skew {d:+.3f} mm)')
            return d
    L = net_lengths(W, {P, N})
    return L.get(P, 0) - L.get(N, 0)


def tune_len(W, S, need, partner=None, pgap=0.2, c=0.1, top=0.3, gapb=0.3, hmax=1.0, margin=0.25, sepnets=(), sep=0.0,
             wmin=0.1, log=print):
    """Lengthen net S by `need` mm (+-0.02) with octilinear serpentine bumps on its NEW straight segments (width >= wmin,
    longest first, either side). Returns the length still missing (<= 0.02 when done)."""
    K = 4 * c * (2 - math.sqrt(2))
    for it in range(60):
        if need <= 0.02:
            return need
        cands = sorted(((math.hypot(x2 - x1, y2 - y1), i) for i, (net, lay, (x1, y1, x2, y2), w) in enumerate(W.new_tracks)
                        if net == S and w >= wmin - 1e-9 and math.hypot(x2 - x1, y2 - y1) >= 4 * c + top + 2 * margin), reverse=True)
        done = False
        for Ls, i in cands:
            net, lay, (x1, y1, x2, y2), w = W.new_tracks[i]
            a, b = (x1, y1), (x2, y2)
            nmax = int((Ls - 2 * margin + gapb) / (4 * c + top + gapb))
            for n in range(nmax, 0, -1):
                h = (need / n + K) / 2; ce = c
                if h < 2 * c:
                    h = need / n / (2 * (math.sqrt(2) - 1)); ce = h / 2
                    if n > 1 or h < 0.02:
                        continue
                h = min(h, hmax)
                ok = None
                for sd in (1, -1):
                    pl = bump_poly(a, b, n, h, sd, ce, top, gapb)
                    pl = [p for k, p in enumerate(pl) if k == 0 or math.hypot(p[0] - pl[k - 1][0], p[1] - pl[k - 1][1]) > 1e-6]
                    if _clear_poly(W, S, partner, lay, pl, w, pgap=pgap, sepnets=sepnets, sep=sep):
                        ok = pl; break
                if ok is None:
                    continue
                L0 = sum(math.hypot(q[0] - p[0], q[1] - p[1]) for p, q in zip(ok, ok[1:]))
                W.remove_new_track(i)
                for p, q in zip(ok, ok[1:]):
                    W.add_track(S, lay, p, q, w)
                need -= L0 - Ls
                done = True
                break
            if done:
                break
        if not done:
            log(f'    tune {S}: no room (still {need:.3f} mm short)')
            return need
    return need
