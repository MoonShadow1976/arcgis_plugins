# -*- coding: utf-8 -*-
"""
耕地四至邻接计算 - 核心算法模块  (版本 3.8.0)
此文件被 .pyt 导入，避免 .pyt 本身的编码问题。

3.8.0 改动（对角线候选直接跳过）：
- 3.7.10 分桶保留对角线(两正)候选，用真实边距比大小兜底分桶
- 问题：对角线候选两方向都有间隙，边不接触，不是真正的四至邻居
- 新版：在入桶前检查 true_ns>0 且 true_ew>0 (真实边距双正) → 直接跳过
  true = abs(proj) - a_half - b_half (真正边到边距离)
- 两负(重叠)情况仍保留，用真实边距比大小分桶(被包围/小地块在大地块边)

3.7.10 改动（两负/两正分桶改用真实边距比大小）：
- 旧版两负(重叠)/两正(对角)返回 None，caller 用 |proj| 绝对值大的方向兜底
  问题：不考虑 a/b 的 OBB 半宽，宽地块方向 |proj| 大但实际重叠更深，误判
- 新版：用真实边距 edge - a_half 比大小（= proj - a_half - b_half，真正边到边距离）
  - 两负：大的(接近0)=重叠浅=边刚好接触=邻居方向
  - 两正：大的=b 中心在这个方向偏离更多=b 主要分布在这个方向=邻居方向
- 例：罗红 b_ew=12.85 宽，旧版 |proj_ew|>||proj_ns|→西邻居(错)
  新版 true_ew=-51.48 < true_ns=-37.09 → 南邻居(对)

3.7.9 改动（评分公式 nearness 权重提高）：
- 旧版 score = (nearness + perp) / init_med，两者等权
  导致远但对齐好的候选(perp小)打败近但偏移的候选(nearness小)
- 新版 score = (nearness * w + perp) / init_med，w=3.0
- 数学原理：score = nearness * w + perp
  - 当 nearness=0, perp=n 时 score=n
  - 当 nearness=n/w, perp=0 时 score=n/w*w=n
  - 两者相等，说明 perp 每增加 1 单位能"抵消" 1/w 的 nearness
  - 即权重 w 下，perp=0 的近邻最远能防御 n/w 边距离的对手
  - w=3.0：perp=0 的近邻能防御 1/3 自己 perp 距离的对手
    例：perp=9 的近邻能防御 nearness=3 的对手（3*3+0 = 0*3+9）

3.7.8 改动（分桶改为边距离符号判断）：
- 新增 assign_direction_bucket_by_edge：用有符号边距离判断方向
  edge = proj - b_half（只减邻居 b 的半宽，不减 a 的半宽）
  - 一正一负：负方向是邻居方向（b 的边接触 a，b 沿这个方向排列）
  - 两负：两方向都接触（被包围/小地块在大地块边）→ 兜底分桶
  - 两正：两方向都有间隙 → 对角线 → 兜底分桶
- 旧 assign_direction_bucket 用质心投影绝对值，对角邻居误判方向
- 被包围/对角情况用投影绝对值大的方向兜底，避免漏候选
- 固定 ns_axis 指北、ew_axis 指东，proj_ns>0 一定是北，proj_ew>0 一定是东

3.7.7 修复（候选分桶筛选）：
- 分桶：assign_direction_bucket 移除 45° 滞回偏向 d1 长边的逻辑
  旧版在对角邻居（|proj_ns|略>|proj_ew|）时仍分到 E/W 桶
  改为直接按投影绝对值大小判断，投影大的方向贡献更大就该分到那个桶

3.7.6 修复（候选筛选 OBB 边距离改用总和）：
- 3.7.5 用 min(edge_ns, edge_ew) 排序，单方向重叠的远候选 edge=0
  会挤掉真正近的候选，导致 85%+ 四至变渠
- 改用 edge_ns + edge_ew 总和排序，两个方向都近才算近
- 保留 3.7.5 的 nearness 过滤和众数兜底方向

3.7.5 改动（候选筛选改为 OBB 边距离 + 兜底方向改为众数）：
- 候选筛选完全抛弃质心距离，改用 OBB 投影边距离
  对所有地块算 min(edge_ns, edge_ew) 边距离，按边距离排序取前 cand_k 个
  解决大地块邻居因质心距离大而排不进候选池的问题
- _robust_fallback_direction 从算术平均改为角度众数（10度分桶取中位数）
  避免方向相反的近邻互相抵消导致回退标准轴
- local_max_dist 过滤从质心距离改为 nearness（边到边距离）
- 修复 dists 变量未定义的 NameError

3.7.1 修复（nearness 计算错误导致大地块四至全渠）：
- nearness 之前只减去 b 的半宽，未减去 a 的半宽
  对于大地块 a（a_ns=64），nearness 被虚增 ~64，导致渠判定误杀
- 修正：nearness = |proj| - a_half - b_half（实际边到边距离）
- N/S 桶：nearness = |proj_ns| - a_ns - b_ns
- E/W 桶：nearness = |proj_ew| - a_ew - b_ew
- 边验证 max_dist 也改为 max(init_med*1.5, a_ns+a_ew)，大地块用更大范围
- 边验证加 try/except 防止 _edge_contact_score 异常导致日志缺失
- 渠判定改用 OBB 半宽中位（NS/EW 各一个）替代 nearness 中位
  N/S 桶用 NS 方向半宽中位，E/W 桶用 EW 方向半宽中位

3.7 改动（OBB 投影重叠 + 近邻距离评分，移除角度过滤）：
- 不再使用角度一致性过滤（_direction_consistency）来踢出候选
- 法向投影不再作为过滤条件，改为纯评分惩罚项（仅影响排序，不过滤）
- 所有候选均可入桶，最终由边接触验证 + 渠判定决定是否有效
- nearness = max(0.0, nearness) 防止 OBB 重叠计算出负值
- 组合评分：(nearness + perp_proj) / init_med，两个都低才最优

3.6 保留（MABR 替代 PCA 主方向）：
- compute_obb_directions_from_verts 用最小面积包围矩形 (MABR) 计算主方向
- MABR 失败时降级回 PCA 兜底

3.5 保留（统一用质心）：
- compute_obb_directions_from_verts 的 centroid 参数

3.4 保留（调试支持）：
- export_obb_debug_layer

3.3 保留：
- 渠判定用各方向独立全局中位（不按连通簇混算）
- 边接触验证扩大到桶内前 7 候选 + 选评分最优的通过者

3.2 保留：
- score_pair_neighbor 用绝对方位轴投影（保留函数，3.7 不再调用）

3.1 保留：
- _edge_contact_score 几何边接触验证

3.0 保留：
- map_obb_axes_to_cardinal 简化确定性版本 / 弱互惠校正默认关闭
"""

import arcpy
import numpy as np
import math
import os
import sys

IS_PY2 = sys.version_info[0] == 2

NEED_DETAIL_LOG = True


def read_centroids(in_features, id_field, zjrxm_field=None):
    """
    读取每个地块的中心点、顶点和指界人姓名。

    返回 (ids, centers, name_map, verts_map)：
    - ids: 要素 ID 列表
    - centers: Nx2 numpy 数组，每行是 (cx, cy)
    - name_map: {oid: str} 指界人姓名
    - verts_map: {oid: [(x,y), ...]} 顶点列表，用于后续多边形重叠判断
    """
    try:
        desc = arcpy.Describe(in_features)
        if hasattr(desc, "FIDSet") and desc.FIDSet:
            arcpy.management.SelectLayerByAttribute(in_features, "CLEAR_SELECTION")
    except Exception:
        pass

    ids = []
    coords = []
    name_map = {}
    verts_map = {}

    fields = [id_field, "SHAPE@"]
    if zjrxm_field:
        fields.append(zjrxm_field)

    with arcpy.da.SearchCursor(in_features, fields) as cur:
        for row in cur:
            oid = row[0]
            geom = row[1]
            if geom is None:
                continue
            c = geom.centroid
            ids.append(oid)
            coords.append((c.X, c.Y))

            if zjrxm_field:
                name_map[oid] = row[2] if row[2] is not None else u""
            else:
                name_map[oid] = u""

            verts = []
            try:
                for part in geom:
                    if part is None:
                        continue
                    for p in part:
                        if p:
                            verts.append((p.X, p.Y))
            except Exception:
                pass
            verts_map[oid] = verts

    centers = np.array(coords, dtype=float) if coords else np.zeros((0, 2))

    # 3.8.0: Check for duplicate IDs - terminate if duplicates found
    unique_ids = set(ids)
    if len(unique_ids) < len(ids):
        dup_count = len(ids) - len(unique_ids)
        import arcpy as _arcpy
        _arcpy.AddError(
            u"ERROR: ID field '{0}' has {1} duplicate values ({2} unique / {3} total). "
            u"Neighbors and OBB results will be incorrect. "
            u"Please use a unique field (e.g. OBJECTID) as the ID field.".format(
                id_field, dup_count, len(unique_ids), len(ids)))
        raise ValueError(
            u"Duplicate ID values in field '{0}': {1} duplicates. "
            u"Use a unique field (e.g. OBJECTID).".format(id_field, dup_count))

    return ids, centers, name_map, verts_map


def _normalize(v):
    n = float(np.linalg.norm(v))
    return v / n if n > 1e-12 else v


def _angle_between_signed_deg(v_from, v_to):
    """v_from 转到 v_to 的有符号角度（度），范围 [-180, 180]。正值为逆时针。"""
    ang = math.degrees(
        math.atan2(v_to[1], v_to[0]) - math.atan2(v_from[1], v_from[0]))
    while ang > 180:
        ang -= 360
    while ang < -180:
        ang += 360
    return float(ang)


def _perpendicular(v):
    """返回 v 的逆时针垂直向量（左法向）。"""
    return np.array([-v[1], v[0]])


def _convex_hull_2d(points):
    """
    Andrew 单调链凸包算法 (O(n log n))。
    输入: [[x,y], ...]  输出: 凸包顶点列表 (逆时针序)。
    """
    pts = sorted(set(map(tuple, points)))
    if len(pts) <= 1:
        return list(pts)
    lower = []
    for p in pts:
        while len(lower) >= 2:
            x1, y1 = lower[-2]
            x2, y2 = lower[-1]
            x3, y3 = p
            cross = (x2 - x1) * (y3 - y1) - (y2 - y1) * (x3 - x1)
            if cross <= 0:
                lower.pop()
            else:
                break
        lower.append(p)
    upper = []
    for p in reversed(pts):
        while len(upper) >= 2:
            x1, y1 = upper[-2]
            x2, y2 = upper[-1]
            x3, y3 = p
            cross = (x2 - x1) * (y3 - y1) - (y2 - y1) * (x3 - x1)
            if cross <= 0:
                upper.pop()
            else:
                break
        upper.append(p)
    return lower[:-1] + upper[:-1]


def _pca_fallback(pts, c):
    """PCA 兜底：当 MABR 不可用时使用。返回 (d1, d2)。"""
    X = pts - c
    cov = np.dot(X.T, X) / max(len(pts) - 1, 1)
    try:
        eigvals, eigvecs = np.linalg.eigh(cov)
        order = np.argsort(eigvals)[::-1]
        eigvecs = eigvecs[:, order]
        d1 = _normalize(eigvecs[:, 0].copy())
        d2 = _perpendicular(d1)
        return d1, d2
    except Exception:
        d = np.array([1.0, 0.0])
        return d, _perpendicular(d)


def compute_obb_directions_from_verts(verts, centroid=None):
    """
    3.6: 用最小面积包围矩形 (MABR) 计算单个多边形的 OBB 两个主方向。
    基于凸包极点旋转卡尺，比 PCA 稳健得多：
    - 仅用极点（凸包顶点），不受内部噪声/凹槽/顶点密度不均影响
    - 对矩形/近矩形地块天然对齐边界方向，不会出现对角线偏移
    - MABR 失败时（凸包退化）降级回 PCA 兜底

    返回 (d1, d2, cx, cy, half_d1, half_d2)：
    - d1, d2: 单位向量，互相垂直，d1 对应 MABR 长边方向
    - cx, cy: 使用的中心（质心）
    - half_d1, half_d2: d1/d2 方向上的半长
    """
    if len(verts) < 3:
        d = np.array([1.0, 0.0])
        return d, _perpendicular(d), 0.0, 0.0, 1.0, 1.0

    pts = np.array(verts, dtype=float)
    if centroid is not None:
        c = np.array(centroid, dtype=float)
    else:
        c = pts.mean(axis=0)

    # Step 1: 凸包
    hull = _convex_hull_2d(pts.tolist())
    if len(hull) < 3:
        d1, d2 = _pca_fallback(pts, c)
    else:
        # Step 2: 旋转卡尺找最小面积包围矩形
        hull_pts = np.array(hull, dtype=float)
        n_hull = len(hull)
        best_area = float('inf')
        best_d1 = None

        for i in range(n_hull):
            p1 = hull_pts[i]
            p2 = hull_pts[(i + 1) % n_hull]
            edge = p2 - p1
            edge_len = float(np.linalg.norm(edge))
            if edge_len < 1e-9:
                continue
            d1_cand = edge / edge_len

            # 旋转对齐 d1_cand 到 x 轴
            angle = math.atan2(d1_cand[1], d1_cand[0])
            cos_a = math.cos(angle)
            sin_a = math.sin(angle)
            rot = np.array([[cos_a, sin_a], [-sin_a, cos_a]])
            rotated = np.dot(rot, hull_pts.T).T

            min_x = float(rotated[:, 0].min())
            max_x = float(rotated[:, 0].max())
            min_y = float(rotated[:, 1].min())
            max_y = float(rotated[:, 1].max())
            area = (max_x - min_x) * (max_y - min_y)

            if area < best_area:
                best_area = area
                best_d1 = d1_cand

        if best_d1 is None:
            d1, d2 = _pca_fallback(pts, c)
        else:
            d1 = best_d1
            d2 = _perpendicular(d1)

    # Step 3: 投影全部顶点计算半长
    X = pts - c
    us = np.dot(X, d1)
    vs = np.dot(X, d2)
    half_d1 = max((float(us.max()) - float(us.min())) / 2.0, 1e-6)
    half_d2 = max((float(vs.max()) - float(vs.min())) / 2.0, 1e-6)

    return d1, d2, float(c[0]), float(c[1]), half_d1, half_d2


def _project_interval(verts, axis):
    """把多边形所有顶点投影到 axis 轴上，返回 (min, max) 区间。向量化实现。"""
    if not verts:
        return 0.0, 0.0
    pts = np.asarray(verts, dtype=float)
    proj = np.dot(pts, axis)
    return float(proj.min()), float(proj.max())


def _interval_overlap_with_gap(lo1, hi1, lo2, hi2):
    """返回 (overlap_len, gap)。正数为真重叠，gap 为间隙。"""
    ov_lo = max(lo1, lo2)
    ov_hi = min(hi1, hi2)
    raw = ov_hi - ov_lo
    if raw > 0:
        return float(raw), 0.0
    return 0.0, float(-raw)


def score_pair_neighbor(verts_i, verts_j, center_i, center_j,
                        init_med, max_dist, dir_label=None):
    """
    3.2 重写：投影必须投在绝对方位轴上，不能用质心连线方向。

    - dir_label='E'/'W'（东西向邻居）：
      沿东西轴(1,0)看距离和间隙，沿南北轴(0,1)看投影重叠。
    - dir_label='S'/'N'（南北向邻居）：
      沿南北轴(0,1)看距离和间隙，沿东西轴(1,0)看投影重叠。
    - dir_label=None（兼容旧调用）：退化为连线方向投影。

    这样斜对角地块在南北轴（或东西轴）上的投影不重叠 → overlap=0 → 被淘汰。

    返回 (dist, score)，不适合（距离超 far）返回 None。
    """
    diff = center_j - center_i
    dist = float(np.linalg.norm(diff))
    if dist <= 0:
        return None
    if max_dist is not None and dist > max_dist:
        return None

    # 3.2 核心：投影轴用绝对方位，不用连线方向
    EW = np.array([1.0, 0.0])   # 东西轴
    NS = np.array([0.0, 1.0])   # 南北轴

    if dir_label in ('E', 'W'):
        along = EW    # 沿东西方向看距离/间隙
        across = NS   # 沿南北方向看投影重叠
    elif dir_label in ('S', 'N'):
        along = NS    # 沿南北方向看距离/间隙
        across = EW   # 沿东西方向看投影重叠
    else:
        # 兼容：无方向标签时用连线方向（不应在 3.2 主流程中触发）
        along = _normalize(diff)
        across = _perpendicular(along)

    # 1) 法向（垂直于邻居方向）投影重叠 → 两块地在「相邻边方向」是否对齐
    a_lo, a_hi = _project_interval(verts_i, across)
    b_lo, b_hi = _project_interval(verts_j, across)
    overlap_len, gap_across = _interval_overlap_with_gap(a_lo, a_hi, b_lo, b_hi)

    # 2) 沿邻居方向投影间隙 → 两块地之间隔着多远
    u_lo, u_hi = _project_interval(verts_i, along)
    v_lo, v_hi = _project_interval(verts_j, along)
    _, gap_along = _interval_overlap_with_gap(u_lo, u_hi, v_lo, v_hi)

    # 法向投影的「典型尺度」= 两块地在法向上的长度平均
    a_len = a_hi - a_lo
    b_len = b_hi - b_lo
    scale_across = max((a_len + b_len) * 0.5, 1e-6)

    # 综合评分（越小越好）
    dist_norm = dist / max(init_med, 1e-6)
    gap_along_norm = gap_along / max(init_med, 1e-6)
    overlap_ratio = overlap_len / scale_across
    gap_across_norm = gap_across / scale_across

    score = (dist_norm * 1.8
             + gap_along_norm * 2.5
             - overlap_ratio * 1.2
             + gap_across_norm * 1.0)

    return (dist, float(score))


def _edge_contact_score(verts_i, verts_j, max_dist, angle_tol_deg=20.0):
    """
    3.1 新增：检查两个多边形之间是否存在"近距离平行边对"。

    真正的边邻居（共享一条边或近距离平行边）会有一对边：
    - 方向近似平行（夹角 < angle_tol_deg）
    - 中点距离 < max_dist
    - 边长相当

    斜对角点接触的地块之间不会存在这样的边对。

    返回 (best_contact, min_dist)：
    - best_contact: 最佳边对的接触质量（平行度 × min(边长) / 距离），越大越好
    - min_dist: 所有平行边对中的最小中点距离（无平行边对则 inf）
    """
    if len(verts_i) < 3 or len(verts_j) < 3:
        return 0.0, float('inf')

    pts_i = np.asarray(verts_i, dtype=float)
    pts_j = np.asarray(verts_j, dtype=float)
    n_i = len(pts_i)
    n_j = len(pts_j)

    cos_tol = math.cos(math.radians(angle_tol_deg))
    best_contact = 0.0
    best_dist = float('inf')

    for k in range(n_i - 1):
        a1 = pts_i[k]
        a2 = pts_i[k + 1]
        va = a2 - a1
        len_a = float(np.linalg.norm(va))
        if len_a < 1e-9:
            continue

        for m in range(n_j - 1):
            b1 = pts_j[m]
            b2 = pts_j[m + 1]
            vb = b2 - b1
            len_b = float(np.linalg.norm(vb))
            if len_b < 1e-9:
                continue

            # 方向平行性
            cos_ab = abs(float(np.dot(va, vb))) / (len_a * len_b)
            if cos_ab < cos_tol:
                continue

            # 中点距离
            mid_a = (a1 + a2) * 0.5
            mid_b = (b1 + b2) * 0.5
            d = float(np.linalg.norm(mid_b - mid_a))
            if d > max_dist:
                continue

            if d < best_dist:
                best_dist = d
            # 接触质量 = 平行度 × 较短边长 / 距离
            contact = cos_ab * min(len_a, len_b) / max(d, 1e-6)
            if contact > best_contact:
                best_contact = contact

    return float(best_contact), float(best_dist)


# 四个绝对方位的单位向量
_CARDINAL_VECTORS = {
    'E': np.array([1.0, 0.0]),
    'W': np.array([-1.0, 0.0]),
    'S': np.array([0.0, -1.0]),
    'N': np.array([0.0, 1.0]),
}


def _direction_consistency(diff_vec, dir_label, angle_tol_deg=30.0):
    """
    3.1 新增：检查连线方向与目标绝对方位的一致性。

    若 diff_vec 与 dir_label 对应的绝对方位单位向量夹角 > angle_tol_deg，
    返回 False（不允许进入该桶）。

    例：45° 斜对角邻居的连线方向偏离 E/N 各 45° > 30° → 被拒绝进入 E 和 N 桶。
    """
    target = _CARDINAL_VECTORS.get(dir_label)
    if target is None:
        return True
    diff_norm = float(np.linalg.norm(diff_vec))
    if diff_norm < 1e-9:
        return True
    cos_ang = float(np.dot(diff_vec, target)) / diff_norm
    cos_tol = math.cos(math.radians(angle_tol_deg))
    return cos_ang >= cos_tol


def _robust_fallback_direction(centers, i, k=5, fallback_axis=None):
    """
    当地块没有顶点数据时，用周围 k 个最近邻的连线方向做主方向。

    3.7.1 改动：用角度众数替代算术平均。
    - 算术平均会被方向相反的近邻抵消（mean_len 过小 → 回退标准轴）
    - 众数：把近邻方向按 10° 分桶，取出现次数最多的桶的中位数方向
    - 这样能找到主导方向，不受相反方向抵消影响

    返回 (d1, d2)。
    """
    if fallback_axis is None:
        fallback_axis = np.array([1.0, 0.0])  # 默认东西轴
    n = len(centers)
    if n < 2:
        return fallback_axis, _perpendicular(fallback_axis)
    diff = centers - centers[i]
    ds = np.sqrt(np.add.reduce(diff * diff, axis=1))
    ds[i] = np.inf
    nn_count = min(k, n - 1)
    if nn_count <= 0:
        return fallback_axis, _perpendicular(fallback_axis)
    order = np.argsort(ds)[:nn_count]
    angles = []
    for jj in order:
        v = diff[jj]
        nv = float(np.linalg.norm(v))
        if nv > 1e-12:
            # 用角度（度，0-180，方向无极性所以折叠到 0-180）
            ang = math.degrees(math.atan2(v[1], v[0])) % 180.0
            angles.append(ang)
    if not angles:
        return fallback_axis, _perpendicular(fallback_axis)

    # 10° 分桶找众数
    bucket_size = 10.0
    buckets = {}
    for a in angles:
        b = int(a / bucket_size)
        if b not in buckets:
            buckets[b] = []
        buckets[b].append(a)
    # 取出现次数最多的桶
    best_bucket = max(buckets, key=lambda x: len(buckets[x]))
    best_angles = buckets[best_bucket]
    # 取该桶的中位数方向
    median_angle = float(np.median(best_angles))
    d1 = np.array([math.cos(math.radians(median_angle)),
                   math.sin(math.radians(median_angle))])
    return d1, _perpendicular(d1)


def _nearest_cardinal_axis(v):
    """
    求一个单位向量 v 最接近哪条「地图绝对方位轴」。
    返回 ('NS', sign) 或 ('EW', sign)：
    - NS 轴：sign=+1 更偏北 (N)，sign=-1 更偏南 (S)
    - EW 轴：sign=+1 更偏东 (E)，sign=-1 更偏西 (W)
    同时返回与最近轴的夹角（度，0~45）
    """
    # 四个标准方向
    N = np.array([0.0, 1.0])
    E = np.array([1.0, 0.0])
    S = np.array([0.0, -1.0])
    W = np.array([-1.0, 0.0])
    # 用点积绝对值比较轴，用符号判断南北/东西
    cos_ns = float(np.dot(v, N))      # >0 偏北 <0 偏南
    cos_ew = float(np.dot(v, E))      # >0 偏东 <0 偏西
    if abs(cos_ns) >= abs(cos_ew):
        ang_deg = float(math.degrees(math.acos(min(1.0, abs(cos_ns)))))
        return 'NS', (1 if cos_ns >= 0 else -1), ang_deg
    else:
        ang_deg = float(math.degrees(math.acos(min(1.0, abs(cos_ew)))))
        return 'EW', (1 if cos_ew >= 0 else -1), ang_deg


def map_obb_axes_to_cardinal(d1, d2):
    """
    3.0 简化版：把 OBB 两条轴 d1/d2 映射到地图绝对方位 N/E/S/W。

    规则（确定性，无 45° 死区分支）：
    1) 每条轴独立取与 N/E/S/W 四个标准方向点积绝对值最大者，作为该轴的所属方位类
       （'NS' 或 'EW'），并记录符号得到 'N+'/'S+'/'E+'/'W+' 标签。
    2) 若 d1 和 d2 撞到同一类（理论上两轴垂直不会撞，但数值噪声/退化时可能）：
       - 与 N 轴点积绝对值大者定为 NS，另一条强制定为 EW；
       - 强制改类型时，符号仍用与该类主轴（NS 用 N，EW 用 E）点积的符号。
    返回 dict: {'d1': label1, 'd2': label2}，label 形如 'N+'/'S+'/'E+'/'W+'。
    """
    N = np.array([0.0, 1.0])
    E = np.array([1.0, 0.0])

    def axis_to_label(axis):
        """返回 (label, axis_type, sign) 。axis_type='NS'/'EW'。"""
        cos_n = float(np.dot(axis, N))
        cos_e = float(np.dot(axis, E))
        if abs(cos_n) >= abs(cos_e):
            return ('N+' if cos_n >= 0 else 'S+', 'NS', 1 if cos_n >= 0 else -1)
        else:
            return ('E+' if cos_e >= 0 else 'W+', 'EW', 1 if cos_e >= 0 else -1)

    lbl1, type1, sign1 = axis_to_label(d1)
    lbl2, type2, sign2 = axis_to_label(d2)

    # 两轴撞到同一类 → 强制分开
    if type1 == type2:
        dot1_n = abs(float(np.dot(d1, N)))
        dot2_n = abs(float(np.dot(d2, N)))
        if dot1_n >= dot2_n:
            # d1 留在 NS，d2 强制改为 EW
            lbl1 = 'N+' if sign1 > 0 else 'S+'
            cos2_e = float(np.dot(d2, E))
            lbl2 = 'E+' if cos2_e >= 0 else 'W+'
        else:
            # d2 留在 NS，d1 强制改为 EW
            lbl2 = 'N+' if sign2 > 0 else 'S+'
            cos1_e = float(np.dot(d1, E))
            lbl1 = 'E+' if cos1_e >= 0 else 'W+'

    return {'d1': lbl1, 'd2': lbl2}


def assign_direction_bucket_by_edge(proj_ns, proj_ew, a_ns, a_ew, b_ns, b_ew):
    """
    3.7.10: 基于边距离符号的分桶，两负/两正时用真实边距比大小。

    前提：caller 已固定 ns_axis 指北、ew_axis 指东，所以
    proj_ns > 0 → j 在 i 北方，proj_ew > 0 → j 在 i 东方。

    edge_ns = proj_ns - b_ns  （只减邻居 b 的半宽，不减 a 的半宽）
    edge_ew = proj_ew - b_ew

    判断规则：
    - edge < 0：b 的中心投影落在 a 的边以内 → 该方向有边重叠
    - edge > 0：b 的中心投影在 a 的边以外 → 该方向有间隙

    分桶决策：
    - 一正一负：正的方向（有间隙）是邻居方向
    - 两负（都重叠）或两正（对角线）：
      用真实边距 edge - a_half 比大小（减去 a 的半宽得到真正边到边距离）
        true_ns = edge_ns - a_ns = proj_ns - a_ns - b_ns
        true_ew = edge_ew - a_ew = proj_ew - a_ew - b_ew
      谁大谁就是邻居方向：
        - 两负：大的（接近0）= 重叠浅 = 边刚好接触 = 邻居方向
        - 两正：大的 = b 中心在这个方向偏离更多 = b 主要分布在这个方向 = 邻居方向

    返回：'E'/'W'/'S'/'N' 之一
    """
    edge_ns = abs(proj_ns) - b_ns
    edge_ew = abs(proj_ew) - b_ew

    ns_is_gap = edge_ns > 0    # NS 方向有间隙 → 可能是 N/S 邻居
    ew_is_gap = edge_ew > 0    # EW 方向有间隙 → 可能是 E/W 邻居

    if ns_is_gap and not ew_is_gap:
        # NS 方向有间隙，EW 方向重叠 → N/S 邻居（proj_ns 符号即方向）
        return 'N' if proj_ns >= 0 else 'S'
    elif ew_is_gap and not ns_is_gap:
        # EW 方向有间隙，NS 方向重叠 → E/W 邻居（proj_ew 符号即方向）
        return 'E' if proj_ew >= 0 else 'W'
    else:
        # 两负（都重叠）或两正（对角线）：用真实边距比大小
        # true = edge - a_half = proj - a_half - b_half（真正边到边距离）
        true_ns = edge_ns - a_ns
        true_ew = edge_ew - a_ew
        if true_ns >= true_ew:
            # NS 方向边距大（重叠浅或间隙大）→ N/S 邻居
            return 'N' if proj_ns >= 0 else 'S'
        else:
            # EW 方向边距大 → E/W 邻居
            return 'E' if proj_ew >= 0 else 'W'


def _dedup_same_neighbor(neighbors_map):
    """同一个邻居 j 同时出现在多个方向 → 只保留评分最好的方向。"""
    nb_to_dirs = {}
    for dk, val in neighbors_map.items():
        if val is None:
            continue
        j, score = val[1], val[2]
        if j not in nb_to_dirs:
            nb_to_dirs[j] = []
        nb_to_dirs[j].append((dk, score))
    for j, lst in nb_to_dirs.items():
        if len(lst) > 1:
            lst.sort(key=lambda x: x[1])
            for dk, _ in lst[1:]:
                neighbors_map[dk] = None
    return neighbors_map


# 绝对方位的「反向」映射
_OPPOSITE_DIR = {"E": "W", "W": "E", "S": "N", "N": "S"}


def apply_weak_reciprocity(neighbors, n, angle_diff_threshold_deg=45.0):
    """
    弱互惠校正：若 i 认为 j 是它的 D 方向邻居，但 j 认为 i 所在方向不是反方向(oppo_D)
    且偏差 > angle_diff_threshold_deg，则把 i→j 降级为 None（改为渠）。
    neighbors[i] 结构: {"E":(dist,j,score),"W":...,"S":...,"N":...}（None 代表无）。
    统计被降级数量并返回。
    """
    degraded = 0
    for i in range(n):
        for dk in ("E", "W", "S", "N"):
            nb = neighbors[i].get(dk)
            if nb is None:
                continue
            j = nb[1]
            oppo_dk = _OPPOSITE_DIR[dk]
            # j 的 oppo_dk 方向的邻居是不是 i？
            j_nb = neighbors[j].get(oppo_dk)
            if j_nb is not None and j_nb[1] == i:
                continue  # 完全互惠，OK
            # j 有没有在其他方向指向 i？若有，看角度差
            j_points_to_i_dir = None
            for dk2 in ("E", "W", "S", "N"):
                n2 = neighbors[j].get(dk2)
                if n2 is not None and n2[1] == i:
                    j_points_to_i_dir = dk2
                    break
            if j_points_to_i_dir is None:
                # j 完全没指回 i：这条边大概率是不对称误连，降级
                neighbors[i][dk] = None
                degraded += 1
                continue
            # 两个方向相差多少「方位跳格」
            order = ["E", "S", "W", "N"]
            pos_a = order.index(oppo_dk)
            pos_b = order.index(j_points_to_i_dir)
            step = abs(pos_a - pos_b)
            if step > 2:
                step = 4 - step
            # step=0: 完全一致；step=1: 差 90°；step=2: 差 180°
            # 对应角度差 ≈ step * 90°
            if step * 90.0 > angle_diff_threshold_deg:
                neighbors[i][dk] = None
                degraded += 1
    return degraded


def compute_four_side_adjacency(ids, centers, name_map, verts_map=None,
                                knn_k=4,
                                angle_tol_deg=25.0,
                                canal_threshold=1.8,
                                max_distance_ratio=5.0,
                                refine_iters=3,
                                canal_name=u"渠",
                                logger=None,
                                need_detail_log=None):
    """
    主入口：耕地四至邻接计算。

    新算法（局部几何自适应 + 绝对方位语义）：
    - verts_map: {oid: [(x,y),...]}  若为 None 或元素不足，退化为仅质心+多近邻方向
    - E/W/S/N 语义：地图绝对方位，不再是地块自己的局部坐标；
      通过 map_obb_axes_to_cardinal 把 OBB 两条轴映射到 NS/EW，再按投影符号定 N/S/E/W
    - angle_tol_deg / refine_iters：保留用于旧代码兼容，新算法不再使用
    """
    # 新算法不再使用 angle_tol_deg / refine_iters，保留仅为兼容旧 .pyt 调用
    del angle_tol_deg, refine_iters
    n = len(ids)
    if n == 0:
        return {}
    if n == 1:
        return {ids[0]: {"E": canal_name, "W": canal_name,
                         "S": canal_name, "N": canal_name,
                         "E_canal": True, "W_canal": True,
                         "S_canal": True, "N_canal": True}}

    def log(msg):
        if logger:
            try:
                logger(msg)
            except Exception:
                pass

    if verts_map is None:
        verts_map = {}

    # ---- 基础统计：最近邻间距中位数 ----
    init_dists = []
    for i in range(n):
        diff = centers - centers[i]
        d = np.sqrt(np.add.reduce(diff * diff, axis=1))
        d[i] = np.inf
        init_dists.append(float(np.min(d)))
    init_med = float(np.median(init_dists)) if init_dists else 1.0
    if init_med <= 0:
        init_med = 1.0
    log(u"初始平均间距≈{0:.3f}".format(init_med))

    cur_max_dist = init_med * max_distance_ratio
    # 候选邻居数：KNN 用这个（越大越稳但越慢）
    cand_k = max(knn_k * 3, 10)

    # ---- 每个地块独立算自己的 OBB 方向 + 绝对方位映射（不依赖全局方向） ----
    obb_info = []       # [(d1, d2, half_d1, half_d2), ...]
    cardinal_map = []   # [map_obb_axes_to_cardinal(d1, d2), ...] 预计算，避免每候选重算
    no_vertex_count = 0
    for i, oid in enumerate(ids):
        verts = verts_map.get(oid, [])
        if len(verts) >= 3:
            d1, d2, _, _, h1, h2 = compute_obb_directions_from_verts(
                verts, centroid=centers[i])
        else:
            # 退化：用周围 5 个最近邻的平均连线方向做主方向（比单个 NN 稳）
            no_vertex_count += 1
            d1, d2 = _robust_fallback_direction(centers, i, k=5)
            h1 = h2 = init_med * 0.5
        obb_info.append((d1, d2, h1, h2))
        cardinal_map.append(map_obb_axes_to_cardinal(d1, d2))
    if no_vertex_count > 0:
        log(u"已完成 {0} 个地块的独立 OBB 方向计算（{1} 个缺失顶点，已用多近邻平均方向兜底）".format(
            n, no_vertex_count))
    else:
        log(u"已完成 {0} 个地块的独立 OBB 方向计算 + 绝对方位映射".format(n))

    # ---- 邻居搜索：质心 KNN 候选 + 任意方向多边形重叠评分 + 本地块四向分桶 ----
    neighbors = [None] * n
    bucket_stats = {"E": 0, "W": 0, "S": 0, "N": 0}

    # 3.7.1: 收集每个地块的 NS/EW 半宽，用于渠判定（替代 nearness 中位）
    all_ns_half = []
    all_ew_half = []

    axes_card = cardinal_map  # alias, more readable below

    for i in range(n):
        pi = centers[i]
        oid_i = ids[i]
        d1_i, d2_i, h1_i, h2_i = obb_info[i]
        axes_i = axes_card[i]
        verts_i = verts_map.get(oid_i, [])

        # 3.7.8: 确定 a 的 NS/EW 轴及半宽，并固定轴正向指向 N 和 E
        # 这样 proj_ns>0 一定是北，proj_ew>0 一定是东，全局统一
        # d1 是 MABR 长边，d2 是短边；通过 cardinal 映射判断哪条是 NS 哪条是 EW
        lbl_d1 = axes_i['d1']
        lbl_d2 = axes_i['d2']
        if lbl_d1[0] in ('N', 'S'):
            # d1 是 NS 轴：'N+'→轴正向指北，'S+'→轴正向指南，取反让 ns_axis 指北
            ns_axis_i = d1_i if lbl_d1[0] == 'N' else -d1_i
            # d2 是 EW 轴：'E+'→轴正向指东，'W+'→轴正向指西，取反让 ew_axis 指东
            ew_axis_i = d2_i if lbl_d2[0] == 'E' else -d2_i
            a_ns = h1_i
            a_ew = h2_i
        else:
            # d1 是 EW 轴
            ew_axis_i = d1_i if lbl_d1[0] == 'E' else -d1_i
            ns_axis_i = d2_i if lbl_d2[0] == 'N' else -d2_i
            a_ns = h2_i
            a_ew = h1_i

        all_ns_half.append(a_ns)
        all_ew_half.append(a_ew)

        # 1) 3.7.6: OBB 边距离筛选候选（用 edge_ns + edge_ew 排序）
        # 3.7.5 用 min(edge_ns, edge_ew)，单方向重叠的远候选 edge=0 会挤掉近邻
        # 改用 edge_ns + edge_ew 总和，两个方向都近才算近，避免误入候选池
        edge_proxies = []
        for j in range(n):
            if j == i:
                continue
            d1_j, d2_j, h1_j, h2_j = obb_info[j]
            # 把 j 的 OBB 半宽投影到 i 的 NS/EW 轴上
            b_ns_proj = h1_j * abs(float(np.dot(d1_j, ns_axis_i))) + \
                        h2_j * abs(float(np.dot(d2_j, ns_axis_i)))
            b_ew_proj = h1_j * abs(float(np.dot(d1_j, ew_axis_i))) + \
                        h2_j * abs(float(np.dot(d2_j, ew_axis_i)))
            # 质心向量在 i 的 NS/EW 轴上的投影
            diff_vec_j = centers[j] - pi
            proj_ns_j = abs(float(np.dot(diff_vec_j, ns_axis_i)))
            proj_ew_j = abs(float(np.dot(diff_vec_j, ew_axis_i)))
            # 两个方向边距离，取总和（两个方向都近才算近）
            edge_ns = max(0.0, proj_ns_j - a_ns - b_ns_proj)
            edge_ew = max(0.0, proj_ew_j - a_ew - b_ew_proj)
            edge_proxies.append((edge_ns + edge_ew, j))

        edge_proxies.sort(key=lambda x: x[0])
        cand_idx = [j for _, j in edge_proxies[:min(cand_k, len(edge_proxies))]]

        # 3.7: 大地块自适应搜索半径
        # 全局 max_dist = init_med × 5 对大地块太小（质心距离天然大）
        # 用地块自身 OBB 半宽放大搜索半径：max(cur_max_dist, a_ns + a_ew)
        local_max_dist = max(cur_max_dist, a_ns + a_ew)

        # 3.7 调试日志
        name_i = name_map.get(oid_i, u"")
        trace_lines = []
        trace_lines.append(u"--- [{0}] OID={1} 邻居搜索开始 (init_med={2:.3f}, cur_max_dist={3:.3f}, local_max_dist={4:.3f})".format(
            name_i, oid_i, init_med, cur_max_dist, local_max_dist))
        trace_lines.append(u"  OBB: d1=({0:.4f},{1:.4f}), d2=({2:.4f},{3:.4f})  a_ns={4:.2f} a_ew={5:.2f}".format(
            d1_i[0], d1_i[1], d2_i[0], d2_i[1], a_ns, a_ew))

        # 2) 3.7.8: 分桶 + OBB 投影评分
        buckets = {"E": [], "W": [], "S": [], "N": []}
        for j in cand_idx:
            if j == i:
                continue

            oid_j = ids[j]
            name_j = name_map.get(oid_j, u"")
            diff_vec = centers[j] - pi
            dist_j = float(np.sqrt(np.dot(diff_vec, diff_vec)))

            # 质心向量在 a 的 NS/EW 轴上的投影（分桶和评分都要用）
            proj_ns = float(np.dot(diff_vec, ns_axis_i))
            proj_ew = float(np.dot(diff_vec, ew_axis_i))

            verts_j = verts_map.get(oid_j, [])
            if len(verts_i) >= 3 and len(verts_j) >= 3:
                # 3.7 核心：把 b 的顶点投影到 a 的 NS/EW 轴上
                pts_j = np.array(verts_j, dtype=float)
                b_proj_ns = np.dot(pts_j, ns_axis_i)
                b_proj_ew = np.dot(pts_j, ew_axis_i)
                b_ns = (float(b_proj_ns.max()) - float(b_proj_ns.min())) / 2.0
                b_ew = (float(b_proj_ew.max()) - float(b_proj_ew.min())) / 2.0

                # 3.8.0: 对角线跳过 — 真实边距双正(两方向都有间隙)直接淘汰
                # true = abs(proj) - a_half - b_half (真正边到边距离)
                true_ns = abs(proj_ns) - a_ns - b_ns
                true_ew = abs(proj_ew) - a_ew - b_ew
                if true_ns > 0 and true_ew > 0:
                    trace_lines.append(u"  [{0}->{1}] dist={2:.2f} \u5bf9\u89d2\u7ebf(true_ns={3:.2f}, true_ew={4:.2f}\u53cc\u6b63), \u8df3\u8fc7".format(
                        name_i, name_j, dist_j, true_ns, true_ew))
                    continue

                # 3.7.10: 用边距离符号分桶
                # 一正一负→正方向是邻居；两负/两正→真实边距大的方向是邻居
                edge_ns_raw = abs(proj_ns) - b_ns
                edge_ew_raw = abs(proj_ew) - b_ew
                ns_is_gap = edge_ns_raw > 0
                ew_is_gap = edge_ew_raw > 0
                dk = assign_direction_bucket_by_edge(
                    proj_ns, proj_ew, a_ns, a_ew, b_ns, b_ew)
                if (ns_is_gap and ew_is_gap) or (not ns_is_gap and not ew_is_gap):
                    # 两正(对角)或两负(重叠)→用了真实边距比大小兜底
                    bucket_note = u"\u5156\u5e95"
                else:
                    bucket_note = u"\u8fb9\u8ddd"

                if dk in ('N', 'S'):
                    nearness = abs(proj_ns) - a_ns - b_ns
                    nearness = max(0.0, nearness)
                    perp_proj = abs(proj_ew)
                else:
                    nearness = abs(proj_ew) - a_ew - b_ew
                    nearness = max(0.0, nearness)
                    perp_proj = abs(proj_ns)

                if nearness > local_max_dist:
                    trace_lines.append(u"  [{0}->{1}] dist={2:.2f} bucket={3}({4}) nearness={5:.2f} > local_max_dist={6:.2f}, \u6dd8\u6c4d".format(
                        name_i, name_j, dist_j, dk, bucket_note, nearness, local_max_dist))
                    continue

                dist_ij = nearness
                # 3.7.9: nearness 权重提高，perp 作为次要 tiebreaker
                # 数学原理：score = nearness * w + perp (w=3.0)
                #   - nearness=0, perp=n  => score = n
                #   - nearness=n/w, perp=0 => score = n/w * w = n
                #   - perp 每增加1单位能"抵消" 1/w 的 nearness
                #   - 权重 w 下，perp=0 的近邻最远能防御 n/w 边距离的对手
                #   - w=3.0：perp=0 的近邻能防御 1/3 自己 perp 距离的对手
                #     例：perp=9 的近邻能防御 nearness=3 的对手（3*3+0 = 0*3+9）
                w_near = 5.0
                score_ij = (nearness * w_near + perp_proj) / max(init_med, 1e-6)
                trace_lines.append(u"  [{0}->{1}] dist={2:.2f} bucket={3}({4}) proj_ns={5:.2f} proj_ew={6:.2f} b_ns={7:.2f} b_ew={8:.2f} nearness={9:.2f} perp={10:.2f} score={11:.3f} (w={12:.1f}) => \u5165\u6876".format(
                    name_i, name_j, dist_j, dk, bucket_note, proj_ns, proj_ew, b_ns, b_ew, nearness, perp_proj, score_ij, w_near))
            else:
                # 退化：无顶点数据，用质心距离兜底，分桶用投影符号
                if abs(proj_ns) >= abs(proj_ew):
                    dk = 'N' if proj_ns >= 0 else 'S'
                else:
                    dk = 'E' if proj_ew >= 0 else 'W'
                d_ij = dist_j
                if d_ij > local_max_dist:
                    trace_lines.append(u"  [{0}->{1}] dist={2:.2f} bucket={3} => \u8d85\u51falocal_max_dist={4:.2f}, \u6dd8\u6c4d(\u9000\u5316)".format(
                        name_i, name_j, dist_j, dk, local_max_dist))
                    continue
                dist_ij, score_ij = d_ij, d_ij / max(init_med, 1e-6)
                trace_lines.append(u"  [{0}->{1}] dist={2:.2f} bucket={3} \u9000\u5316(\u65e0\u9876\u70b9) nearness=N/A score={4:.3f} => \u5165\u6876".format(
                    name_i, name_j, dist_j, dk, score_ij))

            buckets[dk].append((score_ij, dist_ij, int(j)))

        # 3) 每个方向桶取评分最优 + 边接触几何验证
        result_i = {"E": None, "W": None, "S": None, "N": None}
        # 3.7.1: 边验证距离也用 local_max_dist，大地块需要更大的验证范围
        edge_check_max_dist = max(init_med * 1.5, a_ns + a_ew)
        for dk in ("E", "W", "S", "N"):
            lst = buckets[dk]
            if not lst:
                trace_lines.append(u"  方向{0}: 空 (无候选入桶)".format(dk))
                continue
            lst.sort(key=lambda x: x[0])
            top_n = min(7, len(lst))
            best_valid = None
            for ci in range(top_n):
                cand_sc, cand_d, cand_j = lst[ci]
                cand_name = name_map.get(ids[cand_j], u"")
                verts_j = verts_map.get(ids[cand_j], [])
                contact = -1.0
                edge_dist = float('inf')
                if len(verts_i) >= 3 and len(verts_j) >= 3:
                    try:
                        contact, edge_dist = _edge_contact_score(
                            verts_i, verts_j, edge_check_max_dist, angle_tol_deg=20.0)
                    except Exception as ex:
                        trace_lines.append(u"  方向{0} 候选#{1} [{2}] _edge_contact_score异常: {3} => 跳过边验证".format(
                            dk, ci + 1, cand_name, unicode(ex) if isinstance(ex, Exception) else str(ex)))
                        contact = 0.0
                        edge_dist = float('inf')
                    if contact < 0.1:
                        trace_lines.append(u"  方向{0} 候选#{1} [{2}] score={3:.3f} nearness={4:.2f} contact={5:.3f} edge_dist={6:.2f} => 接触<0.1, 淘汰".format(
                            dk, ci + 1, cand_name, cand_sc, cand_d, contact, edge_dist))
                        continue
                trace_lines.append(u"  方向{0} 候选#{1} [{2}] score={3:.3f} nearness={4:.2f} contact={5:.3f} => 通过边验证".format(
                    dk, ci + 1, cand_name, cand_sc, cand_d, contact if contact >= 0 else -1))
                if best_valid is None or cand_sc < best_valid[0]:
                    best_valid = (cand_sc, cand_d, cand_j)
            if best_valid is not None:
                sc, d, j = best_valid
                result_i[dk] = (d, j, sc)
                bucket_stats[dk] += 1
                trace_lines.append(u"  方向{0} 最终选中: [{1}] nearness={2:.2f} score={3:.3f}".format(
                    dk, name_map.get(ids[j], u""), d, sc))
            else:
                trace_lines.append(u"  方向{0}: 前{1}候选全部未通过边验证".format(dk, top_n))

        # 4) 同一邻居多方向冲突
        result_i = _dedup_same_neighbor(result_i)
        neighbors[i] = result_i

        _detail = NEED_DETAIL_LOG if need_detail_log is None else need_detail_log
        if _detail:
            for tl in trace_lines:
                log(tl)

    log(u"四向命中统计: E={E}, W={W}, S={S}, N={N}".format(**bucket_stats))

    # ---- 3.0：弱互惠性校正默认关闭（2.x 版误杀大量合理单向连接，导致很多渠） ----
    # 如需重新启用，把下面 4 行取消注释即可；建议阈值放到 60°~90° 而不是 45°。
    # deg_count = apply_weak_reciprocity(neighbors, n, angle_diff_threshold_deg=45.0)
    # if deg_count > 0:
    #     log(u"弱互惠性校正：降级了 {0} 条非互惠的方向连接（改为渠）".format(deg_count))

    # ---- 3.7.1 渠判定：用 OBB 半宽中位替代 nearness 中位 ----
    # 旧版（3.3）：用各方向 nearness 中位 × canal_threshold 作为渠阈值
    #   问题：nearness 受地块大小影响，大地块的 nearness 天然大，拉高中位，小地块的远邻居不判渠
    # 新版（3.7.1）：用所有地块的 OBB 半宽中位作为基准
    #   N/S 桶用 NS 方向半宽中位，E/W 桶用 EW 方向半宽中位
    #   nearness（边到边距离）> 半宽中位 × canal_threshold → 渠
    ns_half_med = float(np.median(all_ns_half)) if all_ns_half else init_med
    ew_half_med = float(np.median(all_ew_half)) if all_ew_half else init_med
    # floor 保护
    floor_med = init_med * 0.5
    if ns_half_med < floor_med:
        ns_half_med = floor_med
    if ew_half_med < floor_med:
        ew_half_med = floor_med
    log(u"OBB 半宽中位: NS={:.2f}  EW={:.2f}  floor={:.2f}  canal_threshold={:.2f}".format(
        ns_half_med, ew_half_med, floor_med, canal_threshold))

    # ---- 写结果 ----
    result = {}
    for i in range(n):
        oid = ids[i]
        entry = {"E": canal_name, "W": canal_name,
                 "S": canal_name, "N": canal_name,
                 "E_canal": True, "W_canal": True,
                 "S_canal": True, "N_canal": True}
        for key in ("E", "W", "S", "N"):
            nb = neighbors[i].get(key)
            if nb is None:
                continue
            dist = nb[0]  # nearness（边到边距离）
            other_id = ids[nb[1]]
            other_name = name_map.get(other_id, u"")
            # N/S 桶用 NS 半宽中位，E/W 桶用 EW 半宽中位
            dm = ns_half_med if key in ("N", "S") else ew_half_med
            if dm > 0 and dist > dm * canal_threshold:
                continue  # 距离超阈值 → 保持「渠」
            entry[key] = other_name if other_name else canal_name
            entry[key + "_canal"] = False
        result[oid] = entry

    return result


# ==================== 3.4 调试导出 ====================

def _add_to_current_map(fc_path, layer_name, log=None):
    """
    把 fc_path 对应的 feature class 做成图层并加到当前地图 TOC。
    兼容 ArcGIS Pro (arcpy.mp) 和 ArcMap (arcpy.mapping)。
    """
    try:
        result = arcpy.management.MakeFeatureLayer(fc_path, layer_name)
        layer = result[0]
    except Exception as e:
        if log:
            log(u"MakeFeatureLayer failed for {0}: {1}".format(layer_name, e))
        return False
    # ArcGIS Pro
    try:
        aprx = arcpy.mp.ArcGISProject("CURRENT")
        m = aprx.listMaps()[0]
        m.addLayer(layer)
        if log:
            log(u"Added layer to Pro map: {0}".format(layer_name))
        return True
    except Exception:
        pass
    # ArcMap
    try:
        mxd = arcpy.mapping.MapDocument("CURRENT")
        df = arcpy.mapping.ListDataFrames(mxd)[0]
        arcpy.mapping.AddLayer(df, layer, "AUTO_ARRANGE")
        if log:
            log(u"Added layer to ArcMap data frame: {0}".format(layer_name))
        return True
    except Exception:
        pass
    if log:
        log(u"Warning: could not add layer to map (no CURRENT map document). "
            u"Layer {0} exists at {1}".format(layer_name, fc_path))
    return False


def export_obb_debug_layer(in_features, id_field, output_fc_base=None,
                            zjrxm_field=None, logger=None):
    """
    3.4.2 调试：把每个地块的 OBB、质心、方向向量绘制成三个图层，
    并直接添加到当前地图 TOC（不需要手动导入）。

    - output_fc_base=None（默认）：在 in_memory 工作空间创建，直接加到地图，
      不落盘，工具结束后图层仍在地图中（直到关闭 ArcMap/Pro）。
    - output_fc_base=路径：落盘到指定路径 + 加到地图。

    输出三个图层：
      {base}_OBB    - 多边形，每个地块的最小外接矩形（4 个角点）
      {base}_CENT   - 点，每个地块的 OBB 中心（顶点平均）
      {base}_DIR    - 折线，每个地块的 d1（长边）和 d2（短边）方向向量
    """
    log = logger or (lambda m: None)
    log(u"OBB debug layer export starting...")

    desc = arcpy.Describe(in_features)
    sr = desc.spatialReference

    # 读数据
    ids, centers, name_map, verts_map = read_centroids(
        in_features, id_field, zjrxm_field)
    n = len(ids)
    if n == 0:
        log(u"No data to export")
        return

    # 3.4.2 决定工作空间和基础名
    if output_fc_base:
        # 落盘模式
        out_workspace = os.path.dirname(output_fc_base)
        if not out_workspace:
            out_workspace = arcpy.env.workspace or "."
        base_name = os.path.basename(output_fc_base)
        base_lower = base_name.lower()
        if base_lower.endswith(".shp"):
            base_name = base_name[:-4]
        elif base_lower.endswith(".shp.xml"):
            base_name = base_name[:-8]
    else:
        # in_memory 模式（默认，不落盘，直接加到地图）
        out_workspace = "in_memory"
        base_name = "obb_debug"

    log(u"Workspace: {0}, base: {1}".format(out_workspace, base_name))

    # 删除已存在的（in_memory 或磁盘）
    for suffix in ("_OBB", "_CENT", "_DIR"):
        fc_try = os.path.join(out_workspace, base_name + suffix)
        if arcpy.Exists(fc_try):
            try:
                arcpy.management.Delete(fc_try)
            except Exception:
                pass

    # 3.4.2 关键修复：用 CreateFeatureclass 的返回值作为真实 FC 路径
    #   旧版忽略了返回值，自拼路径对 shapefile 会缺 .shp 后缀，导致 InsertCursor
    #   找不到 FC → shp 文件为空
    fc_obb = arcpy.management.CreateFeatureclass(
        out_workspace, base_name + "_OBB", "POLYGON", spatial_reference=sr)[0]
    fc_cent = arcpy.management.CreateFeatureclass(
        out_workspace, base_name + "_CENT", "POINT", spatial_reference=sr)[0]
    fc_dir = arcpy.management.CreateFeatureclass(
        out_workspace, base_name + "_DIR", "POLYLINE", spatial_reference=sr)[0]

    log(u"Created FCs: OBB={0}, CENT={1}, DIR={2}".format(fc_obb, fc_cent, fc_dir))

    # 加字段
    for fc in [fc_obb, fc_cent, fc_dir]:
        arcpy.management.AddField(fc, "OID_STR", "TEXT", field_length=50)
        arcpy.management.AddField(fc, "DKMC", "TEXT", field_length=80)
        arcpy.management.AddField(fc, "DIR_LABEL", "TEXT", field_length=10)
        arcpy.management.AddField(fc, "ANGLE", "DOUBLE")
    arcpy.management.AddField(fc_dir, "CARDINAL", "TEXT", field_length=5)
    arcpy.management.AddField(fc_obb, "HALF_D1", "DOUBLE")
    arcpy.management.AddField(fc_obb, "HALF_D2", "DOUBLE")

    # 计算每个地块的 OBB / 中心 / 方向
    obb_polys = []      # [(poly, oid_str, name, ang_d1, half1, half2), ...]
    cent_points = []    # [(point, oid_str, name)]
    dir_lines = []      # [(line, oid_str, name, 'd1'/'d2', angle, cardinal)]

    for i, oid in enumerate(ids):
        verts = verts_map.get(oid, [])
        if len(verts) >= 3:
            d1, d2, _, _, h1, h2 = compute_obb_directions_from_verts(
                verts, centroid=centers[i])
        else:
            d1, d2 = _robust_fallback_direction(centers, i, k=5)
            h1 = h2 = 1.0
        # 3.5: 统一用质心，不用顶点算术平均
        cx, cy = float(centers[i][0]), float(centers[i][1])

        center = np.array([cx, cy])
        p1 = center + d1 * h1 + d2 * h2
        p2 = center - d1 * h1 + d2 * h2
        p3 = center - d1 * h1 - d2 * h2
        p4 = center + d1 * h1 - d2 * h2
        arr = arcpy.Array([
            arcpy.Point(float(p1[0]), float(p1[1])),
            arcpy.Point(float(p2[0]), float(p2[1])),
            arcpy.Point(float(p3[0]), float(p3[1])),
            arcpy.Point(float(p4[0]), float(p4[1])),
            arcpy.Point(float(p1[0]), float(p1[1]))])
        obb_poly = arcpy.Polygon(arr, sr)

        # 3.7: _DIR 图层改为绘制 d1/d2 中指向正北和正东的射线
        # 通过 map_obb_axes_to_cardinal 判断 d1/d2 哪条映射到 N、哪条映射到 E
        # 然后取该轴指向 N（或 E）的方向（正或负）绘制射线
        card = map_obb_axes_to_cardinal(d1, d2)

        # 确定指向正北的射线方向和半宽
        if card['d1'][0] in ('N', 'S'):
            # d1 是 NS 轴
            north_dir = d1 if card['d1'] == 'N+' else -d1
            north_half = h1
            # d2 是 EW 轴
            east_dir = d2 if card['d2'] == 'E+' else -d2
            east_half = h2
        else:
            # d1 是 EW 轴
            east_dir = d1 if card['d1'] == 'E+' else -d1
            east_half = h1
            # d2 是 NS 轴
            north_dir = d2 if card['d2'] == 'N+' else -d2
            north_half = h2

        n_end = center + north_dir * north_half * 0.5
        e_end = center + east_dir * east_half * 0.5
        n_line = arcpy.Polyline(arcpy.Array([
            arcpy.Point(float(cx), float(cy)),
            arcpy.Point(float(n_end[0]), float(n_end[1]))]), sr)
        e_line = arcpy.Polyline(arcpy.Array([
            arcpy.Point(float(cx), float(cy)),
            arcpy.Point(float(e_end[0]), float(e_end[1]))]), sr)

        ang_n = float(math.degrees(math.atan2(north_dir[1], north_dir[0])))
        ang_e = float(math.degrees(math.atan2(east_dir[1], east_dir[0])))

        oid_str = str(oid)
        name = name_map.get(oid, u"")

        obb_polys.append((obb_poly, oid_str, name, 0.0, h1, h2))
        cent_points.append((arcpy.Point(float(cx), float(cy)), oid_str, name))
        dir_lines.append((n_line, oid_str, name, "N", ang_n, "N"))
        dir_lines.append((e_line, oid_str, name, "E", ang_e, "E"))

    # 写入 OBB 图层
    with arcpy.da.InsertCursor(
        fc_obb, ["SHAPE@", "OID_STR", "DKMC", "DIR_LABEL", "ANGLE",
                 "HALF_D1", "HALF_D2"]) as cur:
        for poly, oid_str, name, ang_d1, h1, h2 in obb_polys:
            cur.insertRow([poly, oid_str, name, "obb", ang_d1, float(h1), float(h2)])

    # 写入质心图层
    with arcpy.da.InsertCursor(
        fc_cent, ["SHAPE@", "OID_STR", "DKMC", "DIR_LABEL", "ANGLE"]) as cur:
        for pt, oid_str, name in cent_points:
            cur.insertRow([pt, oid_str, name, "cent", 0.0])

    # 写入方向向量图层
    with arcpy.da.InsertCursor(
        fc_dir, ["SHAPE@", "OID_STR", "DKMC", "DIR_LABEL", "ANGLE",
                 "CARDINAL"]) as cur:
        for line, oid_str, name, lbl, ang, card in dir_lines:
            cur.insertRow([line, oid_str, name, lbl, ang, card])

    log(u"Written {0} parcels to 3 layers".format(n))

    # 3.4.2 直接加到当前地图 TOC（不用手动导入）
    _add_to_current_map(fc_obb, base_name + "_OBB_lyr", log=log)
    _add_to_current_map(fc_cent, base_name + "_CENT_lyr", log=log)
    _add_to_current_map(fc_dir, base_name + "_DIR_lyr", log=log)

    log(u"OBB debug layers added to current map. "
        u"Symbolize _DIR by CARDINAL field to see absolute N/S/E/W labels.")
