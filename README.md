# COMSOL AI

[English](README.md) | [中文](README_zh.md)

COMSOL Multiphysics automation skills — programmatic simulation via Python.

> **Version**: 1.2.0

## Install

```bash
# Register this marketplace (one time)
/plugin marketplace add 2p1c/comsol_ai

# Install the COMSOL skill
/plugin install comsol@comsol-skills
```

## What's included

| Skill | Description |
|-------|-------------|
| `comsol` | COMSOL model creation, physics setup, meshing, parametric/time-domain studies, and result extraction via mph + COMSOL Java API. Verified against COMSOL 6.2. |

## Prerequisites

- COMSOL Multiphysics 6.0–6.3
- Python 3.x with `mph`, `numpy`, `pandas`

## Repository structure

```
skills/comsol/                  # The Claude Code skill
├── SKILL.md                    # Skill instructions & API patterns
├── scripts/                    # Bundled utility scripts
└── references/                 # API reference, debugging log, examples
examples/                       # Runnable example: laser ultrasound
├── laser_ultrasound_model.py   # Build & solve simulation
├── plot_results.py             # Visualize results
└── requirements.txt            # Example dependencies
.claude-plugin/
└── marketplace.json            # Plugin registry manifest
```

## Changelog

### v1.2.0 (2026-05-11)

- 新增 `comsolbatch` 求解模式：实时文本进度输出（替代无 GUI 的 mph solve）
- 新增 `--build-only` CLI 参数：构建后停止，方便在 COMSOL GUI 中检查
- 新增 `--config` CLI 参数：通过外部 JSON 文件覆盖默认配置
- 新增 Ctrl+C 优雅中断：求解器完成当前时间步后停止，不丢已解数据
- 新增 `study.set("plot", "on")` 和 `probesel="all"` 求解进度设置
- 修复 `SolverLog` 在客户端 API 不可用问题 → 改用 comsolbatch 日志
- 修复 `ModelUtil.showProgress(true)` 崩溃（JVM 无 Swing toolkit）
- 修复 comsolbatch 输出目录不存在问题
- 新增 Entry 8 调试记录（SolverLog 不可用 + progress window 不可用）

### v1.1.0 (2026-05-11)

- 新增双语 README（中文/English）支持语言切换
- 新增 marketplace 插件市场结构（`.claude-plugin/marketplace.json`）
- 新增版本号跨文件同步（SKILL.md / marketplace.json / README）
- 新增 CLI 项目规则文件 CLAUDE.md
- 重组目录结构：`skill/` → `skills/comsol/`，符合官方规范
- 将 Python 脚本从 `assets/` 移至 `scripts/`
- 更新 SKILL.md frontmatter（添加 `compatibility`、`metadata` 字段）

### v1.0.1 (2026-05-11)

- 修复 selection 类型标签（`Box`/`Ball` 替代 `BoxSelection`/`BallSelection`）
- 修复 `entitydim` 必须传字符串类型（`"2"` 而非 `2`）
- 修复 Box selection 的 `condition` 含义（是实体包含类型，非坐标过滤）
- 修复 Ball selection 的半径属性名为 `"r"`（非 `"radius"`）
- 修复命名选择调用方式（用 `.named()` 替代 `.set()`）
- 修复 `Free` BC 的 selection 不可编辑（默认自动管理）
- 修复 `DomainPointProbe` 不可用，改用 `CutPoint3D`
- 修复 GBK 控制台下 Unicode 字符输出报错
- 新增材料属性名发现（`density`、`youngsmodulus` 等，含短名 `rho`、`E`）

### v1.0.0 (2026-05-11)

- 首个版本：COMSOL 自动化技能（mph + Java API 混合架构）
- 激光超声仿真完整示例（热传导 → 热膨胀 → 固体力学 → Lamb 波）
- 已验证的 API 标签表（物理场、边界条件、材料属性、选择类型）
- 调试知识积累机制（`debugging-log.md` 自改进）
- 容错降级策略（stand-alone → client-server 回退）
