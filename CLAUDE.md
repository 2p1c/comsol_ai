# CLAUDE.md

## 项目规则

### 每次修改必须同步更新

1. **版本号同步**：修改 `skills/comsol/` 下任何文件后，检查是否需要 bump 版本号。三个文件的版本号必须一致：
   - `skills/comsol/SKILL.md` → `metadata.version`
   - `.claude-plugin/marketplace.json` → `metadata.version`
   - `README.md` / `README_zh.md` → 顶部版本号

2. **README 更新日志**：每次修改在 `README.md` 和 `README_zh.md` 的 Changelog 区域新增一条，格式：
   ```markdown
   - 简短描述做了什么
   ```
   如果是新版本，先加 `### vX.Y.Z (YYYY-MM-DD)` 行，再列出条目。

3. **调试日志**：每次发现新的 COMSOL API 行为（错误/正确用法），追加到 `skills/comsol/references/debugging-log.md`，格式：
   ```markdown
   ## Entry N — YYYY-MM-DD: 简短描述
   - **COMSOL**: X.Y, **mph**: X.Y.Z, **OS**: [Windows/Linux/macOS]

   ### 症状
   - **根因**:
   - **解决方案**:
   ```

4. **API 参考同步**：如果发现新的 API 标签或旧标签被证伪，同步更新 `skills/comsol/references/api-reference.md`。

### 版本号规则

- 使用语义化版本：`主版本.次版本.修订号`（如 `1.1.0`）
- 新增功能/文件 → bump 次版本（1.0.1 → 1.1.0）
- Bug 修复 → bump 修订号（1.1.0 → 1.1.1）
- 重大架构变更 → bump 主版本（1.x.x → 2.0.0）

### 文件清单

```
skills/comsol/SKILL.md                    # 技能入口
skills/comsol/references/api-reference.md # API 标签字典（已验证）
skills/comsol/references/debugging-log.md # 调试知识积累
skills/comsol/references/laser-ultrasound.md # 激光超声示例
skills/comsol/scripts/                    # 仿真脚本
.claude-plugin/marketplace.json           # 插件市场清单
README.md                                 # 英文说明 + 更新日志
README_zh.md                              # 中文说明 + 更新日志
```
