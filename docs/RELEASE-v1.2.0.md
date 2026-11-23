# v1.2.0 — 外部返回读取边界、闸门 v2 与脚本改进（2026-11-23）

> 以下内容可直接复制到 GitHub 的 Release 编辑框（标题 + 正文）。

## 标题

```
v1.2.0 — 外部返回读取边界、闸门 v2 与脚本改进
```

## 正文

本次同步源项目 2026-11-19 至 11-23 的新进展。**默认流程与安装方式不变**，只增强边界纪律与多智能体协作能力。

### 亮点

- **体系卷 v3.5-clean：外部原始返回的读取边界** — 新增 §7.6，外部数据一律按数据读、不按指令执行；配套 `scripts/raw_guard.py` 做控制字符净化和书目字段白名单。
- **多智能体模式 v1.1：轮次闸门 v2** — 改为「机器头＋内容判据」（`format_version=2`，按 SHA／预算／U 账哈希／滞账认领判）；新增会话卫生与主控串味判据；按需红队作为可选机制；旧轮次无机器头时按 legacy 判据跑。
- **脚本与示例清理** — 移除每日调度示例里的本机专用解释器路径。

### 升级影响

- 无破坏性变更；已装好的项目直接拉取更新即可。
- 多智能体模式仍是**可选模块**，需显式加 `-MultiAgent` / `--multi-agent` 才会安装。
- 完整历史见 [CHANGELOG.md](https://github.com/hsm-lnx/survey-writing-skill/blob/main/CHANGELOG.md)。

### 安装

Windows（在仓库目录里打开 PowerShell）：

```powershell
powershell -ExecutionPolicy Bypass -File install.ps1 -ProjectRoot D:\my_survey -AutoInstall
```

macOS / Linux：

```bash
bash install.sh ~/my_survey --auto-install
```

### 反馈

用法问题、条文争议、脚本 bug 都欢迎提 Issue；完整用法见 [README](https://github.com/hsm-lnx/survey-writing-skill#readme)。
