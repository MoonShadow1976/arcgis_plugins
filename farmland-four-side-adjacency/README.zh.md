# 耕地四至邻接计算插件

一个 ArcGIS 地理处理插件，用来自动计算每块耕地的四至邻居
（东/南/西/北），把邻居地块的 `ZJRXM`（指界人姓名）回写到四个字段
`DKDZ / DKXZ / DKNZ / DKBZ`。距离超过阈值的方向判为「渠」。

算法基于 OBB（有向包围盒），支持正南北、斜网格、不规则农田布局，
不要求曼哈顿式排列。

---

## 1. 目录结构

```
farmland-four-side-adjacency/
├── 耕地四至计算.pyt           # ArcGIS 10.2 – 10.8 的 Python Toolbox
├── farmland_core.py           # 核心算法（两个工具都导入它）
├── farmland_tool.py           # ArcGIS 10.1 的 .tbx 脚本工具
├── README.md                  # 英文说明
└── README.zh.md               # 本文件
```

`farmland_core.py` **必须与 `.pyt` / `.py` 放在同一目录**，因为两个
工具都会把脚本目录加入 `sys.path` 再 `import farmland_core`。

---

## 2. 部署方法

### 2.1 ArcGIS 10.2 – 10.8（推荐，一键式）

1. 把整个文件夹复制到磁盘任意位置（路径尽量不要有空格和中文）。
2. 打开 ArcMap / ArcGIS Pro，加载目标 MXD/APRX。
3. 在 **Catalog（目录）** 窗口里展开 **Toolboxes → My Toolboxes**。
4. 右键 → **Add Toolbox…（添加工具箱）**，选择
   `耕地四至计算.pyt`，会以 *Farmland Four Side Adjacency* 工具箱出现。
5. 双击工具箱里的工具，填参数，运行。

不需要 `.tbx`，不需要手工配置参数。

> `.pyt` 使用 `arcpy.Parameter()` 加 `p0.datatype = u"..."`（unicode
> 字符串）。ArcGIS 10.x 非英文 locale 下 `datatype` setter 会拒绝
> 字节字符串，必须用 unicode。

### 2.2 ArcGIS 10.1（支持，但需要手动配置）

**为什么要手动？** 在 ArcGIS 10.1（尤其是中文版）里，
`arcpy.Parameter.datatype` 属性 setter 是坏的 —— 任何数据类型字符串
都会被拒绝，所以 `.pyt` 根本加载不了。这是 Esri 的已知 bug，不是本
插件的问题。

绕过办法就是经典的 `.tbx + Python 脚本` 方案，用
`farmland_tool.py`。它用 `arcpy.GetParameterAsText()` 读参数，
绕开了坏掉的 setter。

**步骤：**

1. 在 ArcCatalog 里，右键 **My Toolboxes** → **新建 → 工具箱**，
   命名为例如 `FarmlandFourSide.tbx`。
2. 右键新建的工具箱 → **添加 → 脚本…**。
3. **常规（General）** 页：
   - 名称：`FarmlandFourSide`
   - 标签：`耕地四至计算`
   - 脚本文件：选择 `farmland_tool.py`
4. **参数（Parameters）** 页 —— 按顺序添加下列 **12 个参数**
   （顺序很重要，`farmland_tool.py` 是按位置读参数的）：

   | # | 显示名称 | 数据类型 | 类型 | 方向 | 过滤器 |
   |---|---|---|---|---|---|
   | 0 | 输入耕地要素(面) | Feature Layer 要素图层 | 必填 | 输入 | Polygon |
   | 1 | 地块ID字段 | Field 字段 | 必填 | 输入 | OID, Short, Long, Double, Text；获取自 参数0 |
   | 2 | 指界人姓名字段 | Field 字段 | 必填 | 输入 | 获取自 参数0 |
   | 3 | 渠名 | String 字符串 | 必填 | 输入 | — |
   | 4 | 近邻K值 | Long 长整型 | 必填 | 输入 | — |
   | 5 | 方向夹角容差(度) | Double 双精度 | 必填 | 输入 | — |
   | 6 | 渠判定阈值 | Double 双精度 | 必填 | 输入 | — |
   | 7 | 最大搜索距离倍数 | Double 双精度 | 必填 | 输入 | — |
   | 8 | 局部方向修正迭代次数 | Long 长整型 | 必填 | 输入 | — |
   | 9 | 差异表输出路径(可选) | File 文件 | 可选 | 输出 | 扩展名：`xls;csv` |
   | 10 | OBB调试图层输出路径(可选) | Feature Class 要素类 | 可选 | 输出 | — |
   | 11 | 使用详细日志 | Boolean 布尔 | 可选 | 输入 | — |

5. **参数依赖** —— 在参数页里，把参数 1 和 2 的「获取自
   （Obtained from）」都设为参数 0。这样字段下拉框会自动从选中的
   要素图层里填充。
6. 点击 **完成**。
7. 在 ArcMap 里运行。

**默认值说明。** 如果某个参数留空，`farmland_tool.py` 会使用自己
的默认值（`knn_k=4`、`angle_tol=25`、`canal_threshold=1.8`、
`max_distance_ratio=5`、`refine_iters=3`），所以向导里的「默认值」
列不填也能跑。

---

## 3. 参数说明

| # | 参数 | 含义 |
|---|---|---|
| 0 | `in_features` | 输入的耕地多边形图层。结果**直接回写到这个图层**。 |
| 1 | `id_field` | 唯一 ID 字段。**必须唯一** —— 有重复值会中止运行。不确定就用 `OBJECTID`。 |
| 2 | `zjrxm_field` | 存放指界人姓名（`ZJRXM`）的字段。邻居的值会被写入你的四至字段。 |
| 3 | `canal_name` | 某方向无邻居或超阈值时写入的文本。默认「渠」。 |
| 4 | `knn_k` | 兜底方向估计时每块地取的近邻数量（仅当地块顶点数 < 3 时使用）。 |
| 5 | `angle_tol` | 遗留参数（方向锥半角）。为兼容性保留 —— 当前算法基于 OBB，不实际使用。 |
| 6 | `canal_threshold` | OBB 半宽中位数的倍数。`nearness > 半宽中位 × 该值` → 渠。 |
| 7 | `max_distance_ratio` | 全局搜索半径 = `init_med × 该值`。大地块会自动放大搜索半径。 |
| 8 | `refine_iters` | 遗留参数。为兼容性保留。 |
| 9 | `diff_csv` | 可选 `.xls` 差异表。变化的单元格黄色高亮。 |
| 10 | `debug_fc_base` | 可选 OBB 调试图层路径。留空 = 内存 + 自动加入地图。 |
| 11 | `need_detail_log` | 勾选后：(1) 输出每块地的邻居搜索轨迹到日志；(2) 强制生成内存调试图层。 |

**输出字段（不存在时自动创建）：**

| 字段 | 方向 |
|---|---|
| `DKDZ` | 东 |
| `DKXZ` | 西 |
| `DKNZ` | 南 |
| `DKBZ` | 北 |

不修改其他任何字段。特别是 `DKBZXX`（备注）不会被触碰。

---

## 4. 算法说明（v3.8.0）

### 4.1 流程概览

```
读要素
  └─ 质心、顶点、姓名
     └─ (逐地块) 用 MABR 计算 OBB（凸包上旋转卡尺）
        └─ OBB 两条轴映射到绝对方位 N/S/E/W
           └─ 候选筛选（边距离求和，取前 K）
              └─ 逐候选：对角线跳过 → 方向分桶 → nearness
                 └─ 逐桶：评分 → 边接触验证（前 7 个）
                    └─ 同一邻居跨桶去重
                       └─ 渠判定（OBB 半宽中位数）
                          └─ 回写
```

### 4.2 逐地块 OBB（MABR）

对每个多边形计算最小面积包围矩形：

1. 求凸包（Andrew 单调链，O(n log n)）。
2. 在凸包边上做旋转卡尺 —— 对每条凸包边的方向 `d1_cand`，
   把全部凸包点旋转到该方向为 x 轴的坐标系里，算
   `area = (max_x-min_x)*(max_y-min_y)`，保留最小值。
3. 凸包退化（< 3 点）时回退到 PCA。

**为什么用 MABR 不用 PCA？** PCA 对顶点密度和凹口很敏感。一个矩形
地块如果顶点分布不均，PCA 主方向会偏。MABR 只用凸包极点，矩形会
完美对齐它真实的边。

地块 `i` 的结果：
- `d1, d2` —— 互相垂直的单位轴，`d1` 是 MABR 长边。
- `h1, h2` —— 每个方向上的半长。
- `centroid` —— 来自 `arcpy` 的 `.centroid`，不是顶点算术平均。

### 4.3 OBB 轴映射到绝对方位

`map_obb_axes_to_cardinal(d1, d2)` 给每条轴打标签：

- 计算 `dot(d1, N)` 和 `dot(d1, E)`。
- 绝对值大的那个决定这条轴是 `NS` 类还是 `EW` 类。
- 符号给出 `N+ / S+ / E+ / W+`。

如果两条轴意外落到同一类（45° 附近的数值噪声），与 `N` 更对齐的
那条留在 `NS`，另一条强制改为 `EW`。

然后对地块 `i`：

```
ns_axis_i = d1 如果是 N/S 轴，否则 d2   （翻转使 +ns 指北）
ew_axis_i = 另一条轴                    （翻转使 +ew 指东）
a_ns, a_ew = 对应的半长
```

**经过这一步，`proj_ns > 0` 在全局都意味着「候选块在 i 的北边」**，
不管 i 自己怎么旋转。这就是算法能处理斜网格的关键 —— 每块地有
自己的局部坐标系，但四个桶永远代表地图上的绝对南/北/东/西。

### 4.4 候选筛选

对地块 `i` 与任意 `j`，把 `j` 的 OBB 半宽投影到 `i` 的 NS/EW 轴上：

```
proj_ns_j = |dot(centroid_j - centroid_i, ns_axis_i)|
proj_ew_j = |dot(centroid_j - centroid_i, ew_axis_i)|

b_ns = h1_j * |dot(d1_j, ns_axis_i)| + h2_j * |dot(d2_j, ns_axis_i)|
b_ew = h1_j * |dot(d1_j, ew_axis_i)| + h2_j * |dot(d2_j, ew_axis_i)|

edge_ns = max(0, proj_ns_j - a_ns - b_ns)
edge_ew = max(0, proj_ew_j - a_ew - b_ew)

proxy = edge_ns + edge_ew
```

按 `proxy` 升序排序，取前 `cand_k = max(knn_k*3, 10)` 个作为候选。

**为什么用求和不用取最小？** v3.7.5 用 `min(edge_ns, edge_ew)`，结果
一个在某方向上边重叠的远地块会得到 `edge = 0`，排到真正邻居前面
挤进候选池。求和要求**两个方向都近**，这才是真正的侧向邻居几何。

### 4.5 对角线跳过（v3.8.0）

对每个候选 `j`，把 `j` 的顶点投影到 `i` 的 NS/EW 轴，得到真实半长
`b_ns`、`b_ew`，然后：

```
true_ns = |proj_ns| - a_ns - b_ns
true_ew = |proj_ew| - a_ew - b_ew
```

这两个是各方向上**真正的边到边距离**。

**如果 `true_ns > 0` 且 `true_ew > 0`，直接跳过该候选。** 两个方向
都有正间隙 → 两块地是对角关系，边不接触，不可能是四至邻居。

这是对 v3.7.10 的修正 —— 旧版仍让对角候选入桶，靠评分淘汰。提前
拒绝既快又准。

### 4.6 方向分桶（`assign_direction_bucket_by_edge`）

对存活的候选：

```
edge_ns = |proj_ns| - b_ns
edge_ew = |proj_ew| - b_ew
ns_is_gap = edge_ns > 0
ew_is_gap = edge_ew > 0
```

- **一正一负** → 正的那个方向就是邻居方向。这是干净的侧向邻居；
  `proj_ns >= 0` 决定 N 还是 S，`proj_ew >= 0` 决定 E 还是 W。
- **两负（两边都重叠）** → 出现在一块地被大地块包围、或贴在大地块
  边上的情况。用真实边距 `true_ns`、`true_ew` 兜底，**谁大谁赢** ——
  大意味着那个方向上重叠更浅，也就是共享边在那个方向。
- **两正** → 正常情况是对角（已被 4.5 过滤），但在容差边界上仍可能
  出现。兜底规则同上。

**为什么用「真实边距」而不是 `|proj|`？** 设想一块很宽的地块 `b`
（b_ew = 12.85 m）在 `a` 南边。`|proj_ew|` 可能比 `|proj_ns|` 大，
仅仅因为 `b` 宽，就会错误地分到东边。真实边距把两个半宽都减掉，
度量的是每个轴上的实际物理间隙，就能选对。

### 4.7 nearness、perp 与评分

对方向桶 `dk`：

```
如果 dk 是 N/S：
    nearness = max(0, |proj_ns| - a_ns - b_ns)
    perp     = |proj_ew|
否则：
    nearness = max(0, |proj_ew| - a_ew - b_ew)
    perp     = |proj_ns|

如果 nearness > local_max_dist：淘汰
local_max_dist = max(init_med * max_distance_ratio, a_ns + a_ew)

score = (nearness * 5.0 + perp) / init_med
```

- `nearness` —— 沿邻居方向的真实边到边距离。越小越近。
- `perp` —— 候选的横向偏移。越小越对齐。
- `5.0` 的权重（v3.7.9 从 1.0 提上来的）让距离占主导：近但稍微偏
  的候选能打败远但完全对齐的候选。这符合农民直觉 —— 紧挨着我的地
  就是我的邻居，哪怕共享