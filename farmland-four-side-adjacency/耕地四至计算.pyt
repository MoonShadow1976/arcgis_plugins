# -*- coding: utf-8 -*-
"""
Farmland Four-Side Adjacency - Python Toolbox (.pyt) for ArcGIS 10.2+

NOTE: This .pyt works on ArcGIS 10.2+ (including 10.8). On ArcGIS 10.1
Chinese builds, the arcpy.Parameter.datatype setter is broken and rejects
every datatype string, so the .pyt cannot load. For 10.1, use the
companion farmland_tool.py as a Script Tool inside a .tbx toolbox instead.

Only four-side fields are written: DKDZ (East), DKXZ (West),
DKNZ (South), DKBZ (North). The remark field (DKBZXX) is NOT touched.

IMPORTANT: All Chinese text in this file uses \u escapes because the .pyt
parser in ArcMap 10.x may mishandle raw UTF-8 Chinese characters.
"""
import arcpy
import os
import sys

# Add .pyt directory to sys.path for importing farmland_core
try:
    _pyt_dir = os.path.dirname(os.path.abspath(__file__))
except Exception:
    _pyt_dir = os.path.dirname(os.path.abspath(unicode(__file__).encode("gbk")))
if _pyt_dir and _pyt_dir not in sys.path:
    sys.path.insert(0, _pyt_dir)

import farmland_core


class Toolbox(object):
    def __init__(self):
        self.label = "Farmland Four Side Adjacency"
        self.alias = "FarmlandFourSide"
        self.description = (
            u"Calculate farmland four-side (East/South/West/North) adjacent "
            u"neighbors, following the actual parcel layout direction "
            u"(supporting slanted grids and non-orthogonal layouts). Gaps "
            u"along the same row or column are treated as canals and marked "
            u"with the specified canal name. Only writes DKDZ/DKXZ/DKNZ/DKBZ."
        )
        self.tools = [FarmlandFourSideAdjacency]


class FarmlandFourSideAdjacency(object):
    def __init__(self):
        self.label = "Farmland Four Side Adjacency"
        self.description = (
            u"(ver. 3.8.1) "
            u"Calculates East, South, West, and North side adjacent parcels "
            u"along the actual farmland layout direction. Handles slanted "
            u"(non-axis-aligned) grids by first detecting global row/column "
            u"directions via nearest-neighbor edge direction histograms, then "
            u"searching for neighbors within a directional cone around each "
            u"direction. Supports regional direction variations through local "
            u"direction refinement iterations. Large gaps along the same row "
            u"or column are flagged as canals, with the user-specified canal "
            u"name written to the corresponding four-side fields. "
            u"Output fields: DKDZ (East), DKXZ (West), DKNZ (South), "
            u"DKBZ (North)."
        )
        self.canRunInBackground = False

    def getParameterInfo(self):
        # IMPORTANT: In ArcGIS 10.x (especially 10.1), Parameter.datatype setter
        # requires UNICODE strings. Passing byte strings (str) triggers
        # "DataType property invalid input value" error. All datatype values must be u"...".
        # Note: even with unicode, 10.1 Chinese builds reject all datatypes;
        # use the .tbx + farmland_tool.py path on 10.1.
        # All Chinese display names / descriptions use \u escapes to avoid
        # .pyt parser encoding issues in ArcMap 10.x.
        params = []

        p0 = arcpy.Parameter()
        p0.displayName = u"\u8f93\u5165\u8015\u5730\u8981\u7d20(\u9762)"
        p0.name = "in_features"
        p0.datatype = u"GPFeatureLayer"
        p0.parameterType = "Required"
        p0.direction = "Input"
        try:
            p0.filter.list = [u"Polygon"]
        except Exception:
            pass
        p0.description = u"\u8f93\u5165\u5f85\u5904\u7406\u7684\u8015\u5730\u5730\u5757\u9762\u8981\u7d20\u56fe\u5c42\uff0c\u5fc5\u987b\u4e3a Polygon \u7c7b\u578b\u3002\u5de5\u5177\u4f1a\u5728\u6b64\u56fe\u5c42\u4e0a\u8ba1\u7b97\u6bcf\u4e2a\u5730\u5757\u7684\u56db\u81f3\u90bb\u5c45\u5e76\u5199\u56de\u539f\u56fe\u5c42\u5c5e\u6027\u8868\u3002"
        params.append(p0)

        p1 = arcpy.Parameter()
        p1.displayName = u"\u5730\u5757ID\u5b57\u6bb5"
        p1.name = "id_field"
        p1.datatype = u"Field"
        p1.parameterType = "Required"
        p1.direction = "Input"
        p1.parameterDependencies = [p0.name]
        try:
            p1.filter.list = [u"OID", u"Short", u"Long", u"Double", u"Text"]
        except Exception:
            pass
        p1.description = u"\u5730\u5757\u7684\u552f\u4e00\u6807\u8bc6\u5b57\u6bb5\uff0c\u901a\u5e38\u9009\u7528 OBJECTID\u3002\u8be5\u5b57\u6bb5\u7528\u4e8e\u5728\u90bb\u5c45\u641c\u7d22\u4e0e\u7ed3\u679c\u8f93\u51fa\u4e2d\u552f\u4e00\u5339\u914d\u6bcf\u4e2a\u5730\u5757\u3002"
        params.append(p1)

        p2 = arcpy.Parameter()
        p2.displayName = u"\u6307\u754c\u4eba\u59d3\u540d\u5b57\u6bb5"
        p2.name = "zjrxm_field"
        p2.datatype = u"Field"
        p2.parameterType = "Required"
        p2.direction = "Input"
        p2.parameterDependencies = [p0.name]
        p2.description = u"\u5b58\u50a8\u6307\u754c\u4eba\u59d3\u540d\u7684\u5b57\u6bb5\uff08\u5982 ZJRXM\uff09\u3002\u5de5\u5177\u4f1a\u5c06\u90bb\u5c45\u5730\u5757\u7684\u6307\u754c\u4eba\u59d3\u540d\u5199\u5165\u5f53\u524d\u5730\u5757\u7684\u56db\u81f3\u5b57\u6bb5\uff08DKDZ/DKXZ/DKNZ/DKBZ\uff09\u3002"
        params.append(p2)

        p3 = arcpy.Parameter()
        p3.displayName = u"\u6e20\u540d"
        p3.name = "canal_name"
        p3.datatype = u"GPString"
        p3.parameterType = "Required"
        p3.direction = "Input"
        p3.value = u"\u6e20"
        p3.description = u"\u5f53\u67d0\u65b9\u5411\u65e0\u90bb\u5c45\u6216\u90bb\u5c45\u8ddd\u79bb\u8d85\u8fc7\u6e20\u5224\u5b9a\u9608\u503c\u65f6\uff0c\u5199\u5165\u56db\u81f3\u5b57\u6bb5\u7684\u9ed8\u8ba4\u6587\u672c\uff0c\u9ed8\u8ba4\u4e3a\u201c\u6e20\u201d\u3002\u53ef\u6539\u4e3a\u5176\u4ed6\u540d\u79f0\u5982\u201c\u6c34\u6e20\u201d\u201c\u6392\u6c34\u6c9f\u201d\u7b49\u3002"
        params.append(p3)

        p4 = arcpy.Parameter()
        p4.displayName = u"\u8fd1\u90bbK\u503c"
        p4.name = "knn_k"
        p4.datatype = u"GPLong"
        p4.parameterType = "Required"
        p4.direction = "Input"
        p4.value = 4
        p4.description = u"\u5168\u5c40\u65b9\u5411\u4f30\u8ba1\u65f6\uff0c\u6bcf\u4e2a\u5730\u5757\u53d6\u8d28\u5fc3\u8ddd\u79bb\u6700\u8fd1\u7684 K \u4e2a\u90bb\u5c45\u6765\u7edf\u8ba1\u884c/\u5217\u65b9\u5411\u76f4\u65b9\u56fe\u3002\u9ed8\u8ba4 4\uff0c\u7530\u5757\u5e03\u5c40\u89c4\u5219\u65f6\u53ef\u589e\u5927\uff0c\u5e03\u5c40\u7a00\u758f\u65f6\u53ef\u51cf\u5c0f\u3002"
        params.append(p4)

        p5 = arcpy.Parameter()
        p5.displayName = u"\u65b9\u5411\u5939\u89d2\u5bb9\u5dee(\u5ea6)"
        p5.name = "angle_tol"
        p5.datatype = u"GPDouble"
        p5.parameterType = "Required"
        p5.direction = "Input"
        p5.value = 25.0
        p5.description = u"\u65b9\u5411\u9525\u534a\u89d2\uff08\u5ea6\uff09\u3002\u6cbf\u884c/\u5217\u65b9\u5411 \u00b1 \u6b64\u89d2\u5ea6\u5185\u89c6\u4e3a\u540c\u884c\u65b9\u5411\u3002\u9ed8\u8ba4 25\u3002\u5141\u8bb8\u4e00\u5b9a\u7684\u65b9\u5411\u504f\u5dee\uff0c\u8fc7\u5c0f\u4f1a\u6f0f\u6389\u504f\u659c\u90bb\u5c45\uff0c\u8fc7\u5927\u4f1a\u8bef\u7eb3\u5bf9\u89d2\u90bb\u5c45\u3002"
        params.append(p5)

        p6 = arcpy.Parameter()
        p6.displayName = u"\u6e20\u5224\u5b9a\u9608\u503c"
        p6.name = "canal_threshold"
        p6.datatype = u"GPDouble"
        p6.parameterType = "Required"
        p6.direction = "Input"
        p6.value = 1.8
        p6.description = u"\u6e20\u5224\u5b9a\u4e58\u6570\u3002\u5f53\u67d0\u65b9\u5411\u6700\u8fd1\u90bb\u5c45\u7684\u8fb9\u8ddd\u79bb > OBB \u534a\u5bbd\u4e2d\u4f4d\u6570 \u00d7 \u6b64\u503c\u65f6\uff0c\u5224\u5b9a\u4e3a\u9694\u6e20\u3002\u9ed8\u8ba4 1.8\u3002\u503c\u8d8a\u5927\u5bb9\u5fcd\u8d8a\u5927\u7684\u95f4\u9699\uff0c\u8d8a\u5c0f\u8d8a\u5bb9\u6613\u5224\u6e20\u3002"
        params.append(p6)

        p7 = arcpy.Parameter()
        p7.displayName = u"\u6700\u5927\u641c\u7d22\u8ddd\u79bb\u500d\u6570"
        p7.name = "max_distance_ratio"
        p7.datatype = u"GPDouble"
        p7.parameterType = "Required"
        p7.direction = "Input"
        p7.value = 5.0
        p7.description = u"\u6700\u5927\u641c\u7d22\u8ddd\u79bb = \u8d28\u5fc3\u8ddd\u79bb\u4e2d\u4f4d\u6570 \u00d7 \u6b64\u503c\u3002\u9650\u5236\u5019\u9009\u90bb\u5c45\u7684\u641c\u7d22\u8303\u56f4\uff0c\u9632\u6b62\u8de8\u533a\u57df\u9519\u8bef\u8fde\u63a5\u3002\u9ed8\u8ba4 5\u3002\u5927\u5730\u5757\u533a\u53ef\u9002\u5f53\u589e\u5927\uff0c\u5bc6\u96c6\u533a\u53ef\u51cf\u5c0f\u3002"
        params.append(p7)

        p8 = arcpy.Parameter()
        p8.displayName = u"\u5c40\u90e8\u65b9\u5411\u4fee\u6b63\u8fed\u4ee3\u6b21\u6570"
        p8.name = "refine_iters"
        p8.datatype = u"GPLong"
        p8.parameterType = "Required"
        p8.direction = "Input"
        p8.value = 3
        p8.description = u"\u5c40\u90e8\u65b9\u5411\u4fee\u6b63\u7684\u8fed\u4ee3\u8f6e\u6570\u3002\u6bcf\u8f6e\u6839\u636e\u5df2\u627e\u5230\u7684\u90bb\u5c45\u65b9\u5411\u91cd\u65b0\u4f30\u8ba1\u5c40\u90e8\u884c/\u5217\u65b9\u5411\uff0c\u5904\u7406\u533a\u57df\u65b9\u5411\u53d8\u5316\u3002\u9ed8\u8ba4 3\u3002\u65b9\u5411\u4e00\u81f4\u533a\u53ef\u51cf\u5c0f\uff0c\u5e03\u5c40\u590d\u6742\u533a\u53ef\u589e\u5927\u3002"
        params.append(p8)

        p9 = arcpy.Parameter()
        p9.displayName = u"\u5dee\u5f02\u8868\u8f93\u51fa\u8def\u5f84(\u53ef\u9009)"
        p9.name = "diff_csv"
        p9.datatype = u"DEFile"
        p9.parameterType = "Optional"
        p9.direction = "Output"
        p9.description = u"\u53ef\u9009\u3002\u8f93\u51fa\u524d\u540e\u5bf9\u6bd4\u7684 .xls \u5dee\u5f02\u8868\uff0c\u5dee\u5f02\u5355\u5143\u683c\u9ec4\u8272\u9ad8\u4eae\u3002\u7559\u7a7a\u5219\u4e0d\u751f\u6210\u3002\u7528\u4e8e\u68c0\u67e5\u54ea\u4e9b\u5730\u5757\u7684\u56db\u81f3\u88ab\u4fee\u6539\u3002"
        params.append(p9)

        p10 = arcpy.Parameter()
        p10.displayName = u"OBB\u8c03\u8bd5\u56fe\u5c42\u8f93\u51fa\u8def\u5f84(\u53ef\u9009,\u7559\u7a7a\u7528\u5185\u5b58)"
        p10.name = "debug_fc_base"
        p10.datatype = u"DEFeatureclass"
        p10.parameterType = "Optional"
        p10.direction = "Output"
        p10.description = u"\u53ef\u9009\u3002\u7559\u7a7a = \u5728\u5185\u5b58\u4e2d\u521b\u5efa\u8c03\u8bd5\u56fe\u5c42\u5e76\u81ea\u52a8\u52a0\u5165\u5f53\u524d\u5730\u56fe\uff08\u4e0d\u843d\u76d8\uff09\uff1b\u586b\u8def\u5f84 = \u843d\u76d8\u5230\u8be5\u8def\u5f84\u5e76\u52a0\u5165\u5730\u56fe\u3002\u8c03\u8bd5\u56fe\u5c42\u5305\u542b\u4e09\u7c7b\u8981\u7d20\uff1aOBB \u77e9\u5f62\u3001\u8d28\u5fc3\u70b9\u3001\u65b9\u5411\u5411\u91cf\u7ebf\uff0c\u7528\u4e8e\u53ef\u89c6\u5316\u68c0\u67e5\u65b9\u5411\u5224\u65ad\u662f\u5426\u6b63\u786e\u3002"
        params.append(p10)

        p11 = arcpy.Parameter()
        p11.displayName = u"\u4f7f\u7528\u8be6\u7ec6\u65e5\u5fd7(\u542b\u90bb\u5c45\u641c\u7d22\u8f68\u8ff9\u4e0e\u8c03\u8bd5\u56fe\u5c42)"
        p11.name = "need_detail_log"
        p11.datatype = u"GPBoolean"
        p11.parameterType = "Optional"
        p11.direction = "Input"
        p11.description = u"\u52fe\u9009\u540e\uff1a(1) \u8f93\u51fa\u6bcf\u4e2a\u5730\u5757\u7684\u90bb\u5c45\u641c\u7d22\u8f68\u8ff9\u5230 log.txt\uff1b(2) \u5373\u4f7f\u4e0a\u65b9 OBB \u8c03\u8bd5\u56fe\u5c42\u8def\u5f84\u7559\u7a7a\uff0c\u4e5f\u4f1a\u5728\u5185\u5b58\u4e2d\u751f\u6210\u8c03\u8bd5\u56fe\u5c42\u5e76\u52a0\u5165\u5f53\u524d\u5730\u56fe\u3002\u4e0d\u52fe\u9009\u65f6\u4ec5\u8f93\u51fa\u57fa\u672c\u8fdb\u5ea6\uff0c\u4e14\u4e0d\u751f\u6210\u8c03\u8bd5\u56fe\u5c42\u3002"
        params.append(p11)

        return params

    def isLicensed(self):
        return True

    def updateParameters(self, parameters):
        return

    def updateMessages(self, parameters):
        if parameters[9].valueAsText:
            diff_path = parameters[9].valueAsText
            try:
                if os.path.exists(diff_path):
                    parameters[9].setWarningMessage(
                        u"\u6587\u4ef6\u5df2\u5b58\u5728\uff0c\u5c06\u76f4\u63a5\u8986\u76d6\u3002")
            except Exception:
                pass

    def execute(self, parameters, messages):
        in_features = parameters[0].valueAsText
        id_field = parameters[1].valueAsText
        zjrxm_field = parameters[2].valueAsText
        canal_name = parameters[3].valueAsText
        knn_k = int(parameters[4].value)
        angle_tol = float(parameters[5].value)
        canal_threshold = float(parameters[6].value)
        max_distance_ratio = float(parameters[7].value)
        refine_iters = int(parameters[8].value)
        diff_csv = parameters[9].valueAsText
        debug_fc_base = parameters[10].valueAsText if len(parameters) > 10 else None
        # 3.8.0: NEED_DETAIL_LOG controls detail log output and in-memory debug layer
        need_detail_log = False
        if len(parameters) > 11 and parameters[11].value is not None:
            try:
                need_detail_log = bool(parameters[11].value)
            except Exception:
                need_detail_log = False

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

        # Clear selection
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

        ids, centers, name_map, verts_map = farmland_core.read_centroids(
            in_features, id_field, zjrxm_field)
        log(u"Read {0} features (with polygon vertices)".format(len(ids)))
        if len(ids) < 2:
            arcpy.AddWarning(u"Need at least 2 features")
            return

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

        # Only four-side fields (no remark / DKBZXX)
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

        # Backup old values (for diff table)
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

        # Write back results (only four-side fields)
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

        if diff_csv:
            # 3.8.0: Delete existing diff file to avoid ERROR 000258
            try:
                if os.path.exists(diff_csv):
                    os.remove(diff_csv)
                    log(u"Removed existing diff file: {0}".format(diff_csv))
            except Exception as e:
                log(u"Warning: could not remove existing diff file: {0}".format(e))
            include_zjrxm = has_zjrxm and zjrxm_field != id_field
            self._export_diff_table(
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

    def _export_diff_table(self, diff_csv, result, old_values,
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
