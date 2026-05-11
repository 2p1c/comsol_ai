# COMSOL AI

[English](README.md) | [中文](README_zh.md)

COMSOL Multiphysics 自动化技能——通过 Python 程序化建模与仿真。

> **版本**: 1.1.0

## 安装

```bash
# 注册插件市场（仅需一次）
/plugin marketplace add 2p1c/comsol_ai

# 安装 COMSOL 技能
/plugin install comsol@comsol-skills
```

## 包含内容

| 技能 | 说明 |
|-------|-------------|
| `comsol` | COMSOL 建模、物理场设置、网格划分、参数化/时域研究、结果提取。基于 mph + COMSOL Java API，已通过 COMSOL 6.2 实机验证。 |

## 环境要求

- COMSOL Multiphysics 6.0–6.3
- Python 3.x + `mph`、`numpy`、`pandas`

## 仓库结构

```
skills/comsol/          # 技能目录
├── SKILL.md            # 技能说明
├── scripts/            # 仿真脚本
├── references/         # API 参考、调试日志、示例
.claude-plugin/
└── marketplace.json    # 插件市场清单
```

## 更新日志

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
