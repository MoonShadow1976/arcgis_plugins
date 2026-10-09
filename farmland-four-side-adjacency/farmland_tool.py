# -*- coding: utf-8 -*-
"""
Farmland Four-Side Adjacency - Script Tool for ArcGIS 10.1+
=============================================================

This script is designed to be used inside an ArcMap .tbx toolbox as a
"Script Tool". Parameters are read via arcpy.GetParameterAsText(), which
avoids the arcpy.Parameter.datatype bug in ArcGIS 10.1 localized (Chinese)
versions.

How to use (in ArcMap):
1. Right-click a toolbox (.tbx) -> Add -> Script...
2. Label: Farmland Four Side Adjacency
3. Script file: select this .py
4. Configure 12 parameters in the Parameters tab (see PARAMETER TABLE below)
5. Click Finish.

PARAMETER TABLE (configure in the Parameters UI):
# | Display Name                              | Data Type       | Type     | Direction
--+-------------------------------------------+-----------------+----------+----------
0 | Input Farmland Features (polygon)         | Feature Layer   | Required | Input
1 | Feature ID Field                          | Field           | Required | Input
2 | Boundary Person Name Field                | Field           | Required | Input
3 | Canal Name                                | String          | Required | Input
4 | KNN K Value                               | Long            | Required | Input
5 | Angle Tolerance (deg)                     | Double          | Required | Input
6 | Canal Threshold                           | Double          | Required | Input
7 | Max Distance Ratio                        | Double          | Required | Input
8 | Refine Iterations                         | Long            | Required | Input
9 | Diff Table Output Path (optional)         | File            | Optional | Output
10| OBB Debug Layer Output Path (optional)    | Feature Class   | Optional | Output
11| Use Detail Log (trace + debug layer)      | Boolean         | Optional | Input

Filter settings (optional):
- Param 0: Filter = Feature Class, Geometry = Polygon
- Param 1: Filter = Field, Fields = OID, Short, Long, Double, Text
- Param 2: Filter = Field
- Param 9: Filter = File, Extension = xls;csv

Dependencies:
- Param 1 (id_field) -> Obtained from: Param 0 (in_features)
- Param 2 (zjrxm_field) -> Obtained from: Param 0 (in_features)
"""

import arcpy
import os
import sys
import io

# ---- Add script directory to sys.path so we can import farmland_core ----
# When run as a script tool, __file__ may not be set; use arcpy's workspace.
try:
    _script_dir = os.path.dirname(os.path.abspath(__file__))
except Exception:
    _script_dir = os.getcwd()
if _script_dir and _script_dir not in sys.path:
    sys.path.insert(0, _script_dir)

import farmland_core


def main():
    IS_PY2 = sys.version_info[0] == 2

    def log(msg):
        if IS_PY2:
            if isinstance(msg, str):
                try:
                    msg = msg.decode("utf-8")
                except Exception:
                    try:
                        msg = msg.decode("gbk")
                    except Exception:
                        msg = unicode(msg, errors="replace")
            arcpy.AddMessage(unicode(msg))
        else:
            arcpy.AddMessage(str(msg))

    # ---- Read parameters ----
    in_features = arcpy.GetParameterAsText(0)
    id_field = arcpy.GetParameterAsText(1)
    zjrxm_field = arcpy.GetParameterAsText(2)
    canal_name = arcpy.GetParameterAsText(3)
    if not canal_name:
        canal_name = u"\u6e20"  # default to canal name

    try:
        knn_k = int(arcpy.GetParameterAsText(4) or 4)
        angle_tol = float(arcpy.GetParameterAsText(5) or 25.0)
        canal_threshold = float(arcpy.GetParameterAsText(6) or 1.8)
        max_distance_ratio = float(arcpy.GetParameterAsText(7) or 5.0)
        refine_iters = int(arcpy.GetParameterAsText(8) or 3)
    except Exception as e:
        log(u"Parameter parse error: {0}".format(e))
        return

    diff_csv = arcpy.GetParameterAsText(9) or None
    debug_fc_base = arcpy.GetParameterAsText(10) or None
    # 3.8.0: NEED_DETAIL_LOG controls detail log and in-memory debug layer
    need_detail_log = False
    try:
        _p11 = arcpy.GetParameterAsText(11)
        if _p11 and _p11.lower() in (u"true", u"1", u"yes"):
            need_detail_log = True
    except Exception:
        pass

    # ---- Clear selection (avoid processing only selected features) ----
    try:
        desc = arcpy.Describe(in_features)
        if hasattr(desc, "FIDSet") and desc.FIDSet:
            arcpy.management.SelectLayerByAttribute(in_features, "CLEAR_SELECTION")
            log(u"Cleared selection")
    except Exception:
        pass

    log(u"Starting farmland four-side adjacency calculation...")

    # 3.8.0: Log all parameters with explanations
    log(u"--- Parameters ---")
    log(u"  Input: {0} (ID field: {1}, ZJRXM field: {2})".format(in_features, id_field, zjrxm_field))
    log(u"  Canal name: {0}".format(canal_name))
    log(u"  KNN k: {0} (neighbors per parcel for global direction estimation)".format(knn_k))
    log(u"  Angle tolerance: {0} deg (half-angle of direction cone)".format(angle_tol))
    log(u"  Canal threshold: {0} (multiplier for canal gap detection)".format(canal_threshold))
    log(u"  Max distance ratio: {0} (max search distance = centroid median x this)".format(max_distance_ratio))
    log(u"  Refine iterations: {0} (local direction refinement rounds)".format(refine_iters))
    log(u"  Diff table: {0}".format(diff_csv or u"(none)"))
    log(u"  Debug layer: {0}".format(debug_fc_base or u"(in_memory if detail log on)"))
    log(u"  Detail log: {0}".format(str(need_detail_log)))
    log(u"--- End parameters ---")

    # ---- Read centroids + names + polygon vertices (for shape-aware neighbor scoring) ----
    ids, centers, name_map, verts_map = farmland_core.read_centroids(
        in_features, id_field, zjrxm_field)
    log(u"Read {0} features (with vertices for polygon-aware scoring)".format(len(ids)))
    if len(ids) < 2:
        arcpy.AddWarning(u"Need at least 2 features")
        return

    # ---- Run core algorithm ----
    result = farmland_core.compute_four_side_adjacency(
        ids, centers, name_map, verts_map,
        knn_k=knn_k,
        angle_tol_deg=angle_tol,
        canal_threshold=canal_threshold,
        max_distance_ratio=max_distance_ratio,
        refine_iters=refine_iters,
        canal_name=canal_name,
        logger=log,
        need_detail_log=need_detail_log)

    # ---- Ensure output fields exist (only four-side fields, no remark) ----
    output_fields = [
        ("DKDZ", "TEXT", 255),
        ("DKXZ", "TEXT", 255),
        ("DKNZ", "TEXT", 255),
        ("DKBZ", "TEXT", 255),
    ]
    existing = {f.name for f in arcpy.ListFields(in_features)}
    for fn, ftype, flen in output_fields:
        if fn not in existing:
            arcpy.management.AddField(in_features, fn, ftype, field_length=flen)
            log(u"Added field: {0}".format(fn))

    direction_to_field = {
        "E": "DKDZ",
        "W": "DKXZ",
        "S": "DKNZ",
        "N": "DKBZ",
    }

    # ---- Backup old values (for diff table) ----
    old_values = {}
    read_fields_old = [id_field, "DKDZ", "DKXZ", "DKNZ", "DKBZ"]
    has_dkmc = "DKMC" in existing
    has_zjrxm = zjrxm_field in existing
    if has_dkmc:
        read_fields_old.append("DKMC")
    if has_zjrxm and zjrxm_field != id_field:
        read_fields_old.append(zjrxm_field)

    with arcpy.da.SearchCursor(in_features, read_fields_old) as cur:
        for row in cur:
            oid = row[0]
            old_values[oid] = {
                "DKDZ": row[1] or "",
                "DKXZ": row[2] or "",
                "DKNZ": row[3] or "",
                "DKBZ": row[4] or "",
            }
            if has_dkmc:
                old_values[oid]["DKMC"] = row[5] or ""
            if has_zjrxm and zjrxm_field != id_field:
                old_values[oid]["ZJRXM"] = row[6] or ""

    # ---- Write back results (only four-side fields) ----
    update_fields = [id_field, "DKDZ", "DKXZ", "DKNZ", "DKBZ"]
    updated = 0
    canal_count = 0

    with arcpy.da.UpdateCursor(in_features, update_fields) as cur:
        for row in cur:
            oid = row[0]
            if oid not in result:
                continue
            e = result[oid]

            row[1] = e["E"]
            row[2] = e["W"]
            row[3] = e["S"]
            row[4] = e["N"]

            cur.updateRow(row)
            updated += 1
            canal_count += sum(1 for k in ("E", "W", "S", "N") if e[k + "_canal"])

    log(u"Done. Updated {0} features".format(updated))
    log(u"Canal/no-neighbor directions: {0}".format(canal_count))

    # ---- Generate diff table ----
    if diff_csv:
        # 3.8.0: Delete existing diff file to avoid ERROR 000258
        try:
            if os.path.exists(diff_csv):
                os.remove(diff_csv)
                log(u"Removed existing diff file: {0}".format(diff_csv))
        except Exception as e:
            log(u"Warning: could not remove existing diff file: {0}".format(e))
        include_zjrxm = has_zjrxm and zjrxm_field != id_field
        _export_diff_table(
            diff_csv, result, old_values,
            has_dkmc, include_zjrxm, IS_PY2, log)

    # 3.8.0: debug layer export - controlled by need_detail_log
    # export only when need_detail_log=True or debug_fc_base path is given
    if need_detail_log or debug_fc_base:
        log(u"--- 3.4.2 OBB debug layer export ---")
        try:
            farmland_core.export_obb_debug_layer(
                in_features, id_field,
                output_fc_base=debug_fc_base if debug_fc_base else None,
                zjrxm_field=zjrxm_field, logger=log)
        except Exception as e:
            try:
                raw = str(e)
            except Exception:
                raw = repr(e)
            if IS_PY2 and isinstance(raw, str):
                try:
                    emsg = raw.decode("utf-8")
                except Exception:
                    try:
                        emsg = raw.decode("gbk")
                    except Exception:
                        emsg = raw.decode("ascii", errors="replace")
            else:
                emsg = str(raw)
            log(u"\u8c03\u8bd5\u56fe\u5c42\u5bfc\u51fa\u5931\u8d25: " + emsg)


def _export_diff_table(diff_csv, result, old_values,
                       has_dkmc, include_zjrxm, IS_PY2, log):
    """Generate styled diff table (HTML format, Excel compatible)."""
    log(u"Generating diff table: {0}".format(diff_csv))

    out_path = diff_csv
    if out_path.lower().endswith(u".csv"):
        out_path = out_path[:-4] + u".xls"

    YELLOW = u"background-color:#FFFF00;"
    HEADER_BG = u"background-color:#4472C4;color:#FFFFFF;font-weight:bold;"
    ROW_ALT = u"background-color:#D9E1F2;"

    def esc(v):
        s = unicode(v) if v is not None else u""
        s = s.replace(u"&", u"&amp;").replace(u"<", u"&lt;").replace(u">", u"&gt;")
        return s

    lines = []
    lines.append(u'<html xmlns:o="urn:schemas-microsoft-com:office:office"')
    lines.append(u' xmlns:x="urn:schemas-microsoft-com:office:excel"')
    lines.append(u' xmlns="http://www.w3.org/TR/REC-html40">')
    lines.append(u'<head><meta http-equiv="content-type" content="text/html; charset=utf-8">')
    lines.append(u"<style>td,th{border:1px solid #888;padding:3px 6px;font-family:'Microsoft YaHei';font-size:11pt;}</style>")
    lines.append(u"</head><body><table>")

    header = [u"OBJECTID"]
    if has_dkmc:
        header.append(u"DKMC")
    if include_zjrxm:
        header.append(u"ZJRXM")
    header += [
        u"DKDZ_old", u"DKDZ_new", u"DKDZ_chg",
        u"DKXZ_old", u"DKXZ_new", u"DKXZ_chg",
        u"DKNZ_old", u"DKNZ_new", u"DKNZ_chg",
        u"DKBZ_old", u"DKBZ_new", u"DKBZ_chg",
        u"change_count",
    ]
    lines.append(u"<tr>" + u"".join(u'<th style="{0}">{1}</th>'.format(HEADER_BG, esc(h)) for h in header) + u"</tr>")

    changed_count = 0
    unchanged_count = 0
    row_idx = 0

    for oid in result.keys():
        e = result[oid]
        old = old_values.get(oid, {})

        new_vals = {
            "DKDZ": e["E"], "DKXZ": e["W"],
            "DKNZ": e["S"], "DKBZ": e["N"],
        }

        row_cells = []
        row_cells.append((oid, False))
        if has_dkmc:
            row_cells.append((old.get("DKMC", u""), False))
        if include_zjrxm:
            row_cells.append((old.get("ZJRXM", u""), False))

        change_count = 0
        for fname in [u"DKDZ", u"DKXZ", u"DKNZ", u"DKBZ"]:
            old_v = old.get(fname, u"") or u""
            new_v = new_vals.get(fname, u"") or u""
            is_changed = (old_v != new_v)
            if is_changed:
                change_count += 1
            row_cells.append((old_v, is_changed))
            row_cells.append((new_v, is_changed))
            row_cells.append((u"Y" if is_changed else u"", is_changed))

        row_cells.append((change_count, change_count > 0))

        row_bg = ROW_ALT if (row_idx % 2 == 1) else u""
        if change_count > 0:
            changed_count += 1
        else:
            unchanged_count += 1

        cells_html = u""
        for val, highlight in row_cells:
            cell_style = YELLOW if highlight else row_bg
            cells_html += u'<td style="{0}">{1}</td>'.format(cell_style, esc(val))
        lines.append(u"<tr>" + cells_html + u"</tr>")
        row_idx += 1

    lines.append(u"</table></body></html>")

    html_text = u"\r\n".join(lines)
    write_path = out_path.encode("gbk") if IS_PY2 else out_path
    with open(write_path, "wb") as f:
        f.write(html_text.encode("utf-8"))

    log(u"Diff table generated: {0}".format(out_path))
    log(u"  changed: {0}, unchanged: {1}".format(changed_count, unchanged_count))


if __name__ == "__main__":
    main()
