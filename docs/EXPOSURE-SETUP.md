# GitHub 曝光设置清单

这份清单把「本地能做的」和「必须在 GitHub 网页上点的」分开。本地部分已完成，剩下的是你在浏览器里按几下的事。

## 一、本地已完成

| 项目 | 文件 | 作用 |
|---|---|---|
| README 开头重排 | `README.md` | 版本日志折叠收起，10 秒内看到「解决什么问题 / 适合谁」 |
| 英文摘要 | `README.md` 第 7 行 | 覆盖英文搜索与 international 访客 |
| 徽章 | `README.md` 顶部 | License / Python / version / stars |
| 演示图 | `docs/demo-flow.svg` | 「一句话需求 → 章节提纲 → 引用核对报告」三步示意 |
| MIT 许可证 | `LICENSE` | 消除筛选阶段的硬缺口 |
| 更新日志 | `CHANGELOG.md` | Release 的素材来源 |
| v1.2.0 Release 文案 | `docs/RELEASE-v1.2.0.md` | 可直接粘贴到 Release 编辑框 |
| 完整实录 | `docs/CASE-STUDY.md` | 可发布到知乎/公众号/掘金的长文（发布前替换 📷 截图） |
| 落地页 | `docs/index.html` | GitHub Pages 首页，用于填 Website 一栏 |

---

## 二、待办 1：仓库详情页信息（约 2 分钟）

进入 `Settings → General`，填：

**Description**（97 字符）：

```
中文综述写作 Claude Code Skill：收敛选题、核验文献库、搭章节骨架、逐段写作与逐条引用核对；支持查全复核、每日文献 Alert、Zotero 与可选多智能体协作，交付可追溯的稿件。
```

**Website**（建好 Pages 后填）：

```
https://hsm-lnx.github.io/survey-writing-skill/
```

**Topics**（按优先级，最多 20 个）：

```
claude-code  claude-skill  academic-writing  literature-review  research
writing-assistant  zotero  citation  python  multi-agent  academic-research  chinese
```

**Include in home page**：勾选 `Releases`；`Packages` 取消（仓库没发布过 Package，勾了也不会显示）；`Deployments` 随意。

---

## 三、待办 2：发布 v1.2.0 Release

1. 打开 `https://github.com/hsm-lnx/survey-writing-skill/releases/new`。
2. Tag 填 `v1.2.0`，Target 选 `main`。
3. 标题和正文直接从 [`docs/RELEASE-v1.2.0.md`](RELEASE-v1.2.0.md) 复制。
4. 勾选 **Set as a latest release**，发布。
5. 回头在 `CHANGELOG.md` 里给每个版本号补上 `releases/tag/vX.Y.Z` 链接（旧版本 tag 若未建，先只补 v1.2.0）。

> 这一步是首页 `Releases` 卡片能否持续露出的前提——每次更新都真的发一次 Release，比改 README 里的版本日志更有效。

---

## 四、待办 3：开启 Discussions

`Settings → Features → Discussions → Set up discussions`，建议建四个类别：

- **Announcements** — 版本发布、改动通知（仅维护者可发）
- **Q&A** — 安装、密钥、用法问题，标记为已回答
- **Ideas** — 新条文、新闸门、新通道提议
- **Show and tell** — 展示大家用它写出来的综述（最有传播力）

开完后把 `README.md §10 FAQ` 里的高频问题搬成 Q&A 帖，置顶一条「从这里开始：安装 → 体检 → 第一次用」，链接回 README §2 / §3 / §5。

---

## 五、待办 4：开启 GitHub Pages

1. `Settings → Pages`。
2. Source 选 `Deploy from a branch`，Branch 选 `main`，目录选 `/docs`。
3. 保存后访问 `https://hsm-lnx.github.io/survey-writing-skill/` 确认能打开。
4. 把该地址填进待办 1 的 Website 栏。

`docs/index.html` 是纯静态单页，无构建步骤；演示图引用同目录的 `demo-flow.svg`。以后改落地页直接改这个文件即可。

---

## 六、待办 5：分发（持续，不是一次性）

| 渠道 | 怎么做 | 优先级 |
|---|---|---|
| 知乎 | 回答「怎么写文献综述 / AI 写综述靠谱吗」，挂 `docs/CASE-STUDY.md` 改写版 | 高 |
| 公众号 / 掘金 / CSDN | 发实操教程，标题带「Claude Code 写综述」「不编文献」 | 高 |
| B 站 / 视频号 | 5 分钟演示：一句话需求 → 提纲 → 核对报告 | 中 |
| awesome 列表 | 给 `awesome-claude-code` 一类仓库和中文科研工具清单提 PR 收录 | 中 |
| Show HN / 英文社区 | 用 README 英文摘要改写，需先有英文落地页 | 低 |

所有分享链接统一带来源参数，例如 `?utm_source=zhihu&utm_medium=answer`，然后在 `Insights → Traffic` 看 Referring sites 和搜索关键词，两周复盘一次，把精力放到真正带来访问量的渠道。

---

## 七、关于 30 秒 GIF

当前仓库里没有真实操作录屏，所以 README 顶部用的是静态 SVG 示意图（`docs/demo-flow.svg`），先把「看不懂」的问题解决掉。

要做真 GIF，需要你本人录一次：

1. 用任意录屏工具（OBS、Windows 游戏栏、ScreenToGif）在 Claude Code 里录 30 秒：说一句需求 → 出章节提纲 → 跑一次引用覆盖脚本。
2. 导出为 `docs/demo.gif`（建议 ≤ 5 MB，宽度 1000px 以内）。
3. 把 `README.md` 第 9 行的 `docs/demo-flow.svg` 换成 `docs/demo.gif`，保留 SVG 作为无动图时的备选。

录屏时注意隐去未公开的题目、DOI 和内部数据。
