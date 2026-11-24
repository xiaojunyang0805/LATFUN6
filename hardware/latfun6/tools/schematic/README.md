# Schematic helper scripts (MIT)

Offline helpers for driving EasyEDA Pro through the MCP. They read the saved project (`EPRJ`, default `hardware/EDA/Latfun6.eprj`) read-only.

| Script | Purpose |
|---|---|
| `pins.py` | Absolute pin positions and outward directions for every part on a page (`PAGE=p1`). Output: `pins_<page>.json` |
| `netmap_b1.py` | B1 power: pin → net map (2-pin parts by pin number, ICs by pin name), plus intentional no-connects |
| `groups_b1.py` | B1 functional clusters, their order on the page, and the frame |
| `cluster.py` | Cluster layout: passives horizontal, each beside the IC pin it connects to. Output: move list |
| `stubs.py` | 20-unit net stubs for every mapped pin. Shortens stubs that would touch another net, and reports conflicts |
| `wirecheck.py` | Compares saved wires against the planned stubs (missing or duplicated) |
| `attrcheck.py` | Flags parts with blank instance-attribute overrides (the v1.0.3 move-tool damage) |

Workflow per block: place parts → `cluster.py` → move (rotate first, then set x/y) → save → `pins.py` → `stubs.py` → draw in batches of ≤ 30 → save → `wirecheck.py` and `attrcheck.py`.
