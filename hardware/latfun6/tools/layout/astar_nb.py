"""Compiled (numba) octilinear multi-layer A* for lfr job scripts.
State = (layer, y, x, dir) with dir -1 (fresh: start or just after a via) or 0..7 (lfr.DIRS order). From a moving
state only straight or +-45-degree turns; diagonal steps may not cut a blocked corner. Via moves at vok cells.
    path = astar(free[L,H,W] bool, cost[L,H,W] f32 (per-cell step cost, >0), vok[H,W] bool,
                 sx, sy, slay[L] bool, sdir[L,8] bool, tx, ty, glay[L] bool, gdir[L,8] bool,
                 bend, via, hweight, maxexp)  ->  int32[n,3] (x, y, layer) or empty
"""
import numpy as np
from numba import njit

DX = np.array([1, 1, 0, -1, -1, -1, 0, 1], np.int64)
DY = np.array([0, 1, 1, 1, 0, -1, -1, -1], np.int64)
DL = np.array([1.0, 2 ** 0.5, 1.0, 2 ** 0.5, 1.0, 2 ** 0.5, 1.0, 2 ** 0.5])


@njit(cache=True)
def _push(hk, hv, n, k, v):
    i = n
    hk[i] = k; hv[i] = v
    while i > 0:
        p = (i - 1) >> 1
        if hk[p] <= hk[i]:
            break
        hk[p], hk[i] = hk[i], hk[p]
        hv[p], hv[i] = hv[i], hv[p]
        i = p
    return n + 1


@njit(cache=True)
def _pop(hk, hv, n):
    k0 = hk[0]; v0 = hv[0]
    n -= 1
    hk[0] = hk[n]; hv[0] = hv[n]
    i = 0
    while True:
        l = 2 * i + 1
        if l >= n:
            break
        r = l + 1
        c = l
        if r < n and hk[r] < hk[l]:
            c = r
        if hk[i] <= hk[c]:
            break
        hk[c], hk[i] = hk[i], hk[c]
        hv[c], hv[i] = hv[i], hv[c]
        i = c
    return k0, v0, n


@njit(cache=True)
def _compact(hk, hv, n, g, W, H, tx, ty, hweight):
    """drop stale heap entries (key above the entry's current g + h), then re-heapify"""
    m = 0
    for i in range(n):
        s = hv[i]
        r = s // 9
        x = r % W; r //= W
        y = r % H
        dx = abs(x - tx); dy = abs(y - ty)
        if hk[i] <= g[s] + hweight * (max(dx, dy) + 0.41421356 * min(dx, dy)) + 1e-3:
            hk[m] = hk[i]; hv[m] = s; m += 1
    for i in range(m // 2 - 1, -1, -1):
        j = i
        while True:
            l = 2 * j + 1
            if l >= m:
                break
            c = l
            if l + 1 < m and hk[l + 1] < hk[l]:
                c = l + 1
            if hk[j] <= hk[c]:
                break
            hk[c], hk[j] = hk[j], hk[c]
            hv[c], hv[j] = hv[j], hv[c]
            j = c
    return m


@njit(cache=True)
def astar(free, cost, vok, sx, sy, slay, sdir, tx, ty, glay, gdir, bend, via, hweight, maxexp, viac):
    L, H, W = free.shape
    N = L * H * W * 9
    g = np.full(N, np.inf, np.float32)
    came = np.full(N, -1, np.int32)
    cap = 3_000_000
    hk = np.empty(cap, np.float64)
    hv = np.empty(cap, np.int64)
    n = 0
    for l in range(L):
        if slay[l] and free[l, sy, sx]:
            s = ((l * H + sy) * W + sx) * 9
            g[s] = 0.0
            dx = abs(sx - tx); dy = abs(sy - ty)
            n = _push(hk, hv, n, hweight * (max(dx, dy) + 0.41421356 * min(dx, dy)), s)
    nexp = 0
    goal = -1
    while n > 0:
        f, s, n = _pop(hk, hv, n)
        d = s % 9 - 1
        r = s // 9
        x = r % W; r //= W
        y = r % H; l = r // H
        gc = g[s]
        dxh = abs(x - tx); dyh = abs(y - ty)
        if f > gc + hweight * (max(dxh, dyh) + 0.41421356 * min(dxh, dyh)) + 1e-3:
            continue                                   # stale entry
        nexp += 1
        if nexp > maxexp:
            break
        if x == tx and y == ty and glay[l] and (gdir[l, d] if d >= 0 else gc > 0.0):   # via arrival ok
            goal = s
            break
        if n + 12 >= cap:
            n = _compact(hk, hv, n, g, W, H, tx, ty, hweight)
            if n + 12 >= cap:
                break
        for j in range(3 if d >= 0 else 8):
            if d < 0:
                k = j
                if x == sx and y == sy and not sdir[l, k]:
                    continue
            else:
                k = d if j == 0 else ((d + 1) % 8 if j == 1 else (d + 7) % 8)
            nx = x + DX[k]; ny = y + DY[k]
            if nx < 0 or ny < 0 or nx >= W or ny >= H or not free[l, ny, nx]:
                continue
            if DX[k] != 0 and DY[k] != 0 and not (free[l, y, nx] and free[l, ny, x]):
                continue
            ng = gc + DL[k] * cost[l, ny, nx]
            if d >= 0 and k != d:
                ng += bend
            t = ((l * H + ny) * W + nx) * 9 + k + 1
            if ng < g[t]:
                g[t] = ng; came[t] = s
                ex = abs(nx - tx); ey = abs(ny - ty)
                n = _push(hk, hv, n, ng + hweight * (max(ex, ey) + 0.41421356 * min(ex, ey)), t)
        if vok[y, x] and d >= 0:
            for l2 in range(L):
                if l2 != l and free[l2, y, x]:
                    t = ((l2 * H + y) * W + x) * 9
                    ng = gc + via + viac[y, x]
                    if ng < g[t]:
                        g[t] = ng; came[t] = s
                        n = _push(hk, hv, n, ng + hweight * (max(dxh, dyh) + 0.41421356 * min(dxh, dyh)), t)
    if goal < 0:
        return np.empty((0, 3), np.int32)
    cnt = 0
    s = goal
    while s >= 0:
        cnt += 1; s = came[s]
    out = np.empty((cnt, 3), np.int32)
    s = goal; i = cnt - 1
    while s >= 0:
        r = s // 9
        out[i, 0] = r % W; r //= W
        out[i, 1] = r % H; out[i, 2] = r // H
        i -= 1; s = came[s]
    return out


@njit(cache=True)
def astar_region(free, cost, vok, sx, sy, slay, sdir, tx, ty, gmask, bend, via, hweight, maxexp, viac):
    """as astar, but the goal is any cell with gmask[l, y, x] (entered moving); (tx, ty) only steers the heuristic"""
    L, H, W = free.shape
    N = L * H * W * 9
    g = np.full(N, np.inf, np.float32)
    came = np.full(N, -1, np.int32)
    cap = 3_000_000
    hk = np.empty(cap, np.float64)
    hv = np.empty(cap, np.int64)
    n = 0
    for l in range(L):
        if slay[l] and free[l, sy, sx]:
            s = ((l * H + sy) * W + sx) * 9
            g[s] = 0.0
            dx = abs(sx - tx); dy = abs(sy - ty)
            n = _push(hk, hv, n, hweight * (max(dx, dy) + 0.41421356 * min(dx, dy)), s)
    nexp = 0
    goal = -1
    while n > 0:
        f, s, n = _pop(hk, hv, n)
        d = s % 9 - 1
        r = s // 9
        x = r % W; r //= W
        y = r % H; l = r // H
        gc = g[s]
        dxh = abs(x - tx); dyh = abs(y - ty)
        if f > gc + hweight * (max(dxh, dyh) + 0.41421356 * min(dxh, dyh)) + 1e-3:
            continue                                   # stale entry
        nexp += 1
        if nexp > maxexp:
            break
        if d >= 0 and gmask[l, y, x]:
            goal = s
            break
        if n + 12 >= cap:
            n = _compact(hk, hv, n, g, W, H, tx, ty, hweight)
            if n + 12 >= cap:
                break
        for j in range(3 if d >= 0 else 8):
            if d < 0:
                k = j
                if x == sx and y == sy and not sdir[l, k]:
                    continue
            else:
                k = d if j == 0 else ((d + 1) % 8 if j == 1 else (d + 7) % 8)
            nx = x + DX[k]; ny = y + DY[k]
            if nx < 0 or ny < 0 or nx >= W or ny >= H or not free[l, ny, nx]:
                continue
            if DX[k] != 0 and DY[k] != 0 and not (free[l, y, nx] and free[l, ny, x]):
                continue
            ng = gc + DL[k] * cost[l, ny, nx]
            if d >= 0 and k != d:
                ng += bend
            t = ((l * H + ny) * W + nx) * 9 + k + 1
            if ng < g[t]:
                g[t] = ng; came[t] = s
                ex = abs(nx - tx); ey = abs(ny - ty)
                n = _push(hk, hv, n, ng + hweight * (max(ex, ey) + 0.41421356 * min(ex, ey)), t)
        if vok[y, x] and d >= 0:
            for l2 in range(L):
                if l2 != l and free[l2, y, x]:
                    t = ((l2 * H + y) * W + x) * 9
                    ng = gc + via + viac[y, x]
                    if ng < g[t]:
                        g[t] = ng; came[t] = s
                        n = _push(hk, hv, n, ng + hweight * (max(dxh, dyh) + 0.41421356 * min(dxh, dyh)), t)
    if goal < 0:
        return np.empty((0, 3), np.int32)
    cnt = 0
    s = goal
    while s >= 0:
        cnt += 1; s = came[s]
    out = np.empty((cnt, 3), np.int32)
    s = goal; i = cnt - 1
    while s >= 0:
        r = s // 9
        out[i, 0] = r % W; r //= W
        out[i, 1] = r % H; out[i, 2] = r // H
        i -= 1; s = came[s]
    return out
