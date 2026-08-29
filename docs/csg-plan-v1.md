# CSG Plan Contract v1（跨引擎几何重建契约）

> **权威版本**：本文件（主仓库）。aicad 仓库 `docs/csg-plan-v1.md` 为同步副本。
> **状态**：v1 已实机验证（SW 2026 中文版，2026-08-30：4 操作 → 4 特征树，bbox 精确）。
> **对应工具**：主包 `solidworks_features_rebuild_csg(plan)`；aicad 导出器 `interop` 的 `to_csg_plan_v1`。

## 目的

同一份设计意图在两个引擎间迁移：aicad（OCCT 内核）把通道 B 的 CSG 序列 dump 成
本契约 JSON；SolidWorksMCP 按契约在真实 SolidWorks 里长出**同名特征树**
（每个操作对应一个可编辑特征，带参数化草图），而非哑实体。

## 契约

```json
{
  "version": 1,
  "units": "mm",
  "operations": [
    {"op": "box", "name": "base", "size": [60, 40, 20], "at": [0, 0, 0]},
    {"op": "cylinder", "name": "boss", "diameter": 20, "height": 30, "at": [0, 0, 20]},
    {"op": "cut_cylinder", "name": "bore", "diameter": 8, "depth": null, "through": true, "at": [0, 0, 0]},
    {"op": "cone", "name": "tip", "bottom_diameter": 10, "top_diameter": 4, "height": 12, "at": [0, 0, 50]}
  ]
}
```

### 字段

| 字段 | 语义 |
|---|---|
| `version` | 必须 `1`；不匹配报 `INVALID_PARAMETER` |
| `units` | 必须 `"mm"` |
| `operations` | 非空数组，按序应用 |
| `op` | `box` / `cylinder` / `cone` / `cut_cylinder`（v1 与通道 B 现状对齐） |
| `name` | 非空且**唯一**；SW 侧新特征改名为它（特征树可读性） |
| `at` | `[x, y, z]` 毫米；Pos 语义合并于此 |

### v1 堆叠语义（实机验证）

- **实体操作沿轴堆叠**：`at.x = at.y = 0`；`at.z` 必须**等于当前堆顶**
  （首个实体必须在 `[0, 0, 0]`，`box` 必须是第一个操作）。
- 堆叠实现：首个实体在基准面上草图；后续实体在**当前实体顶面**上草图
  （体面走查 `GetBodies2(0,False) → GetFirstFace/GetNextFace`，`face.GetBox()`
  返回 6 元组取 zmin 最大者为顶面，`Select2(False,0)` 后直接画圆拉伸）。
  实测堆叠精确：盒 20 + 柱 30 → bbox z = 50（无布尔误差）。
- `cut_cylinder`：支持 `at.x/at.y` 偏移（孔位），从顶面切；
  `depth: null` + `through: true` = 贯通；`depth` 为正数时盲孔。
- **失败原子回滚**：任一操作失败 → 删除本次新建的全部特征（T10 机制），
  响应携带 `rolled_back` / `rollback_warning`。

### 错误契约

所有校验失败返回 `INVALID_PARAMETER`（消息含 operation 序号与原因）；
几何失败返回 `SW_API_ERROR` 并按上节回滚。

## 后续扩展（不在 v1）

- `at.x/at.y` 非零的实体偏移（需草图偏移或参考几何）；
- 更多 op：cut_box / revolve / pattern / fillet；
- 单位换算（v1 锁 mm，与 MCP 工具约定一致）。
