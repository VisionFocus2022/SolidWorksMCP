
### N31 增补（2026-09-01）：契约 v2——polygon_prism + swept_arc（仅重建方向）

- v2 完全保留 v1 4-op；新增两**首建 op**：`polygon_prism`（正 N 边棱柱，可继续堆叠）
  与 `swept_arc`（圆弧 torus 段，唯一操作）。v1 计划含 v2 op 报错（版本门）。
- **方向边界（决策）**：v2 op 仅 SW 重建方向。aicad 导出方向延后——通道 B AST
  识别器认 Box/Cylinder/Cone 构造节点，polygon=profile+extrude 两步识别属后续
  扩展；互证改用「脚本直连」模式（build123d RegularPolygon+extrude 与 SW
  create_polygon 各自建模）。
- **互证结果（实机 2026-09-01，tools/validate/csg_roundtrip.py 双案例）**：
  ring_v1 rel_diff=2.9e-16（机器精度）；hex_v2 rel_diff=**0.0**（跨引擎体积
  逐位一致）——「契约+互证」方法论（本 ADR 决策 2）第三次生效且精度新高。
