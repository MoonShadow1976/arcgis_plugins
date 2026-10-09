# Farmland Four-Side Adjacency

An ArcGIS geoprocessing plugin that automatically computes the four-side
neighbours (East / South / West / North) of every farmland parcel and
writes the neighbour's `ZJRXM` (boundary witness name) back into four
fields `DKDZ / DKXZ / DKNZ / DKBZ`. Directions whose distance exceeds a
threshold are marked as a canal (`渠`).

The algorithm is OBB-based (oriented bounding box). It works on
axis-aligned, slanted, rotated and irregular farmland layouts — a
Manhattan grid is not required.

---

## 1. Folder layout

```
farmland-four-side-adjacency/
├── 耕地四至计算.pyt           # ArcGIS 10.2 – 10.8 Python Toolbox
├── farmland_core.py           # core algorithm (imported by both tools)
├── farmland_tool.py           # ArcGIS 10.1 .tbx script tool
├── README.md                  # this file
└── README.zh.md               # Chinese version
```

`farmland_core.py` **must stay in the same directory** as the `.pyt` /
`.py` you launch, because both tools add the script directory to
`sys.path` and then `import farmland_core`.

---

## 2. Deployment

### 2.1 ArcGIS 10.2 – 10.8 (recommended, one-click)

1. Copy the whole folder anywhere on disk (avoid spaces and non-ASCII
   characters in the path if possible).
2. Open ArcMap / ArcGIS Pro with the target MXD / APRX loaded.
3. In the **Catalog** window, expand **Toolboxes → My Toolboxes**.
4. Right-click → **Add Toolbox…**, browse to `耕地四至计算.pyt`. It
   appears as a toolbox named *Farmland Four Side Adjacency*.
5. Double-click the tool inside, fill in the parameters, run.

No `.tbx`, no manual parameter configuration.

> The `.pyt` uses `arcpy.Parameter()` plus `p0.datatype = u"..."` with
> **unicode** strings. On non-English locales of ArcGIS 10.x the
> `datatype` setter rejects byte strings, so unicode is mandatory.

### 2.2 ArcGIS 10.1 (supported, but manual setup required)

**Why manual?** On ArcGIS 10.1 (especially the Chinese build) the
`arcpy.Parameter.datatype` property setter is broken — every datatype
string is rejected, so the `.pyt` cannot load at all. This is a known
Esri bug, not a bug in this plugin.

The workaround is the classic `.tbx + Python script` route using
`farmland_tool.py`. It reads parameters with
`arcpy.GetParameterAsText()` and therefore bypasses the broken setter.

**Steps:**

1. In ArcCatalog, right-click **My Toolboxes** → **New → Toolbox**.
   Name it e.g. `FarmlandFourSide.tbx`.
2. Right-click the new toolbox → **Add → Script…**
3. **General** tab:
   - Name: `FarmlandFourSide`
   - Label: `Farmland Four Side Adjacency`
   - Script File: browse to `farmland_tool.py`
4. **Parameters** tab — add the following **12 parameters in this exact
   order** (the index matters: `farmland_tool.py` reads them by
   position):

   | # | Display Name | Data Type | Type | Direction | Filter |
   |---|---|---|---|---|---|
   | 0 | Input Farmland Features | Feature Layer | Required | Input | Polygon |
   | 1 | Feature ID Field | Field | Required | Input | OID, Short, Long, Double, Text; Obtained from Param 0 |
   | 2 | Boundary Person Field | Field | Required | Input | Obtained from Param 0 |
   | 3 | Canal Name | String | Required | Input | — |
   | 4 | KNN K | Long | Required | Input | — |
   | 5 | Angle Tolerance (deg) | Double | Required | Input | — |
   | 6 | Canal Threshold | Double | Required | Input | — |
   | 7 | Max Distance Ratio | Double | Required | Input | — |
   | 8 | Refine Iterations | Long | Required | Input | — |
   | 9 | Diff Table Output | File | Optional | Output | Extension: `xls;csv` |
   | 10 | OBB Debug Layer Output | Feature Class | Optional | Output | — |
   | 11 | Use Detail Log | Boolean | Optional | Input | — |

5. **Parameter dependencies** — in the Parameters tab, set **Obtained
   from** = Parameter 0 for parameters 1 and 2. This makes the field
   dropdowns populate from the chosen feature layer.
6. Click **Finish**.
7. Run the tool from ArcMap.

**About defaults.** If a parameter is left blank, `farmland_tool.py`
uses its own fallback values (`knn_k=4`, `angle_tol=25`,
`canal_threshold=1.8`, `max_distance_ratio=5`, `refine_iters=3`), so you
do not have to fill in the *Default* column in the wizard.

---

## 3. Parameters

| # | Name | Meaning |
|---|---|---|
| 0 | `in_features` | Input farmland polygon layer. Results are written **back into this layer**. |
| 1 | `id_field` | Unique ID field. **Must be unique** — duplicates abort the run. Use `OBJECTID` if unsure. |
| 2 | `zjrxm_field` | Field holding the boundary witness name (`ZJRXM`). The neighbour's value is written into your four-side field. |
| 3 | `canal_name` | Text written when a direction has no neighbour or exceeds the canal threshold. Default `渠`. |
| 4 | `knn_k` | Per-parcel neighbour count for the fallback direction estimate (only used when a parcel has fewer than 3 vertices). |
| 5 | `angle_tol` | Legacy parameter (cone half-angle). Reserved for compatibility — the current algorithm is OBB-based and does not use it. |
| 6 | `canal_threshold` | Multiplier on the median OBB half-width. `nearness > median_half × this` → canal. |
| 7 | `max_distance_ratio` | Global search radius = `init_med × this`. Large parcels automatically expand their radius. |
| 8 | `refine_iters` | Legacy parameter. Reserved for compatibility. |
| 9 | `diff_csv` | Optional `.xls` diff table. Changed cells are highlighted in yellow. |
| 10 | `debug_fc_base` | Optional OBB debug layer path. Leave blank for in-memory + auto-add-to-map. |
| 11 | `need_detail_log` | If checked: (1) writes per-parcel neighbour trace to the message log; (2) forces the in-memory debug layer. |

**Output fields (created automatically if missing):**

| Field | Direction |
|---|---|
| `DKDZ` | East |
| `DKXZ` | West |
| `DKNZ` | South |
| `DKBZ` | North |

No other field is touched. In particular `DKBZXX` (remark) is left alone.

---

## 4. Algorithm (v3.8.0)

### 4.1 Pipeline overview

```
read features
  └─ centroids, vertices, names
     └─ (per-parcel) compute OBB via MABR (rotating calipers on convex hull)
        └─ map OBB axes to absolute N/S/E/W
           └─ candidate selection (edge-distance sum, top-K)
              └─ per-candidate: diagonal skip → direction bucket → nearness
                 └─ per-bucket: score → edge-contact validation (top 7)
                    └─ dedup same neighbour across buckets
                       └─ canal decision (median OBB half-width)
                          └─ write back
```

### 4.2 Per-parcel OBB via MABR

For every polygon we compute a Minimum-Area Bounding Rectangle:

1. Convex hull (Andrew's monotone chain, O(n log n)).
2. Rotating calipers on the hull edges — for each hull edge direction
   `d1_cand`, rotate all hull points into that frame, compute
   `area = (max_x-min_x)*(max_y-min_y)`, keep the minimum.
3. Fall back to PCA if the hull degenerates (< 3 points).

**Why MABR instead of PCA?** PCA is sensitive to vertex density and
concave notches. A rectangular field whose vertices are unevenly
distributed will get a skewed principal axis. MABR only uses hull
extremes, so a rectangle comes out perfectly aligned with its real
edges.

The result for parcel `i` is:
- `d1, d2` — perpendicular unit axes; `d1` is the long side of the MABR.
- `h1, h2` — half-length along each axis.
- `centroid` — from `arcpy`'s `.centroid`, not the vertex mean.

### 4.3 Mapping OBB axes to cardinal directions

`map_obb_axes_to_cardinal(d1, d2)` labels each axis:

- Compute `dot(d1, N)` and `dot(d1, E)`.
- Whichever has the larger absolute value decides `NS` vs `EW`.
- The sign gives `N+ / S+ / E+ / W+`.

If the two axes happen to land in the same class (numerical noise near
45°), the one more aligned with `N` stays `NS` and the other is forcibly
reassigned to `EW`.

Then for parcel `i`:

```
ns_axis_i = d1 if d1 is the N/S axis else d2  (flipped so +ns points North)
ew_axis_i = the other axis                    (flipped so +ew points East)
a_ns, a_ew = corresponding half-lengths
```

**After this step, `proj_ns > 0` universally means "the candidate is to
the North of i"**, regardless of how i is rotated. This is the key that
makes the algorithm work on slanted grids — each parcel has its own
local frame, but the four buckets always mean absolute North / South /
East / West on the map.

### 4.4 Candidate selection

For parcel `i` and every other `j`, project `j`'s OBB half-widths onto
`i`'s NS / EW axes:

```
proj_ns_j = |dot(centroid_j - centroid_i, ns_axis_i)|
proj_ew_j = |dot(centroid_j - centroid_i, ew_axis_i)|

b_ns = h1_j * |dot(d1_j, ns_axis_i)| + h2_j * |dot(d2_j, ns_axis_i)|
b_ew = h1_j * |dot(d1_j, ew_axis_i)| + h2_j * |dot(d2_j, ew_axis_i)|

edge_ns = max(0, proj_ns_j - a_ns - b_ns)
edge_ew = max(0, proj_ew_j - a_ew - b_ew)

proxy = edge_ns + edge_ew
```

Sort by `proxy` ascending, take the top
`cand_k = max(knn_k*3, 10)` as candidates.

**Why the sum, not the min?** v3.7.5 used `min(edge_ns, edge_ew)`, which
let a distant parcel that is edge-overlapping in one direction get
`edge = 0` and jump into the candidate pool ahead of real neighbours.
The sum requires *both* directions to be near — that is the geometry of
a true side neighbour.

### 4.5 Diagonal skip (v3.8.0)

For each candidate `j`, project `j`'s vertices onto `i`'s NS / EW axes
to get the true half-extents `b_ns`, `b_ew`, then:

```
true_ns = |proj_ns| - a_ns - b_ns
true_ew = |proj_ew| - a_ew - b_ew
```

These are the **true edge-to-edge distances** in each direction.

**If `true_ns > 0` AND `true_ew > 0`, skip the candidate.** Both
directions have a positive gap → the two parcels are diagonal, their
edges do not touch, and they cannot be four-side neighbours.

This fixes v3.7.10, which still allowed diagonal candidates into the
bucket and relied on scoring to reject them. Rejecting early is both
faster and more accurate.

### 4.6 Direction bucket (`assign_direction_bucket_by_edge`)

For surviving candidates:

```
edge_ns = |proj_ns| - b_ns
edge_ew = |proj_ew| - b_ew
ns_is_gap = edge_ns > 0
ew_is_gap = edge_ew > 0
```

- **One positive, one negative** → the positive direction is the
  neighbour direction. That is a clean side neighbour; `proj_ns >= 0`
  decides N vs S, `proj_ew >= 0` decides E vs W.
- **Both negative** (both edges overlap) → this happens when one parcel
  is enclosed by, or sits on the edge of, a larger one. Fall back to the
  true edge distances `true_ns`, `true_ew`; **the larger one wins** — it
  means the overlap is shallower in that direction, i.e. that is where
  the shared edge is.
- **Both positive** → normally diagonal (already filtered by 4.5), but
  can still occur at the tolerance boundary. Same tiebreak as above.

**Why "true edge distance" instead of `|proj|`?** Consider a very wide
parcel `b` (b_ew = 12.85 m) to the south of `a`. `|proj_ew|` may be
larger than `|proj_ns|` simply because `b` is wide, which would wrongly
pick East. The true edge distance subtracts both half-widths, so it
measures the actual physical gap along each axis and picks correctly.

### 4.7 Nearness, perpendicular offset, score

For bucket `dk`:

```
if dk is N/S:
    nearness = max(0, |proj_ns| - a_ns - b_ns)
    perp     = |proj_ew|
else:
    nearness = max(0, |proj_ew| - a_ew - b_ew)
    perp     = |proj_ns|

if nearness > local_max_dist: reject
local_max_dist = max(init_med * max_distance_ratio, a_ns + a_ew)

score = (nearness * 5.0 + perp) / init_med
```

- `nearness` — the true edge-to-edge distance along the neighbour
  direction. Small = close.
- `perp` — the lateral offset of the candidate. Small = well aligned.
- The `5.0` weight (v3.7.9 raised it from 1.0) makes distance dominate:
  a near-but-slightly-off candidate beats a far-but-perfectly-aligned
  one. This matches farmer intuition: the parcel right next to me is my
  neighbour, even if the shared edge is only 60 % long.

`local_max_dist` uses `max(global, a_ns + a_ew)` because a big parcel's
true neighbours are naturally at a large centroid distance.

### 4.8 Edge-contact validation

For each direction bucket, sort by score, then try the top **7**
candidates. For each one, run `_edge_contact_score(verts_i, verts_j)`:

- Walk every edge of `i` and every edge of `j`.
- Consider edge pairs whose directions are parallel within 20°.
- For those, compute the midpoint distance.
- `contact = cos_parallel × min(len_a, len_b) / max(dist, eps)`.
- Accept if `contact >= 0.1`.

This is the geometric "are these two polygons actually sharing an edge"
test. Diagonal point-touching polygons have no close parallel edge pair,
so `contact ≈ 0` and they are rejected. A small anti-parallel corner
touch might pass the direction bucket but fails here.

The first candidate (lowest score) that passes validation is chosen.

### 4.9 Dedup across buckets

A candidate can land in more than one bucket (e.g. a parcel directly to
the NE where N and E are both borderline). `_dedup_same_neighbor` keeps
only the direction with the smallest score and clears the other.

### 4.10 Canal decision

Before the final write-back, compute:

```
ns_half_med = median(all a_ns)   # over all parcels
ew_half_med = median(all a_ew)
floor_med   = init_med * 0.5

ns_half_med = max(ns_half_med, floor_med)
ew_half_med = max(ew_half_med, floor_med)
```

Then for each direction on each parcel:

```
dm = ns_half_med if direction is N/S else ew_half_med
if nearness > dm * canal_threshold:
    keep canal  (do not write the neighbour's name)
else:
    write neighbour's ZJRXM
```

**Why median half-width instead of median nearness?** v3.3 used median
nearness, but nearness scales with parcel size, so a few huge parcels
inflate the median and small parcels never get flagged as canals. The
median OBB half-width is a stable geometric scale independent of how far
a particular candidate happens to be.

---

## 5. Debugging

### 5.1 Detail log

Check **Use Detail Log**. `farmland_core` will emit, per parcel:

```
--- [name] OID=123 邻居搜索开始 (init_med=..., cur_max_dist=..., local_max_dist=...)
  OBB: d1=(...), d2=(...)  a_ns=... a_ew=...
  [A->B] dist=... bucket=N(边距) proj_ns=... b_ns=... nearness=... perp=... score=... => 入桶
  [A->C] dist=... 对角线(true_ns=..., true_ew=...双正), 跳过
  方向E 候选#1 [D] score=... nearness=... contact=... => 通过边验证
  方向E 最终选中: [D] nearness=... score=...
  方向W: 空 (无候选入桶)
```

This is enough to reproduce any decision the algorithm made.

### 5.2 OBB debug layers

Two ways to get the debug layers:

- Check **Use Detail Log** and leave Param 10 blank → three layers are
  created in `in_memory` and added to the current map. Nothing is
  written to disk.
- Set Param 10 to a path → layers are written to disk **and** added to
  the map.

Three layers are produced:

| Layer | Geometry | Contents |
|---|---|---|
| `*_OBB` | Polygon | Minimum-area bounding rectangle of each parcel. |
| `*_CENT` | Point | Parcel centroid. |
| `*_DIR` | Polyline | Two rays per parcel: the OBB axis that maps to **N** and the one that maps to **E**, drawn from the centroid. |

Symbolize `*_DIR` by the `CARDINAL` field (`N` / `E`) — that is the
quickest way to verify that a rotated parcel's local frame is being
mapped to the correct absolute directions.

---

## 6. Version history (highlights)

| Version | Change |
|---|---|
| 3.8.0 | Skip diagonal candidates early (`true_ns > 0 and true_ew > 0`). Duplicate-ID detection aborts the run. `need_detail_log` parameter added. |
| 3.7.10 | Tiebreak in `assign_direction_bucket_by_edge` now uses true edge-to-edge distance instead of raw `|proj|`. |
| 3.7.9 | Score weight: `nearness * w + perp` with `w = 5.0` (was `nearness + perp`). |
| 3.7.8 | Direction bucket switched from centroid projection to signed edge distance. |
| 3.7.6 | Candidate selection uses `edge_ns + edge_ew` instead of `min(...)`. |
| 3.7.1 | Fixed `nearness` to subtract both `a_half` and `b_half`. |
| 3.6 | Switched from PCA to MABR for OBB directions. |
| 3.5 | Use `arcpy`'s `.centroid` consistently. |
| 3.1 | Added `_edge_contact_score` geometric validation. |

---

## 7. Known limitations

- **Duplicate IDs.** `read_centroids` aborts the run if the ID field has
  duplicates. Use `OBJECTID` unless you need something else.
- **Zero-vertex geometries.** Parcels with fewer than 3 vertices fall
  back to centroid-KNN direction estimation. This is much less
  reliable; do not use it for production if you can avoid it.
- **Very thin parcels.** If `a_ns` or `a_ew` is close to zero, the
  half-width projections in `b_ns` / `b_ew` can be noisy. The floor on
  `ns_half_med` / `ew_half_med` mitigates this but does not eliminate it.
- **Parcels inside other parcels.** The algorithm treats the enclosing
  parcel as a candidate and will bucket it correctly, but the
  edge-contact validation may reject it (no shared edge). This is
  usually the right behaviour.
- **`angle_tol_deg` / `refine_iters`** are read by the script tools for
  backward compatibility but are not used by v3.x. They are kept in the
  parameter list so existing `.tbx` / `.pyt` configurations do not break.