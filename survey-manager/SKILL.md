---
name: "survey-manager"
display_name: "综述工作台"
display_name_en: "Survey Workbench"
description: "从模糊题目到可交付中文综述：建文献库、搭骨架、逐段写、逐条核，并托管每日新文献 Alert。"
description_zh: "一个 skill 内含写作卷与体系卷：写作卷管学术判断，体系卷管文献核验、台账、Zotero、对账与每日 Alert 分诊，两卷按交接契约协同。"
description_en: "An all-in-one skill for Chinese literature reviews: literature verification, outline building, drafting, faithfulness checks, and daily alert triage."
examples_zh:
  - "我想写一篇激光焊接过程监测的中文综述，范围还没想好"
  - "按第 3 章的提纲把文献收进来，并核验著录"
  - "核一下 3.2 的引文，哪几条撑不住「主流」这个说法"
  - "把每天的 WOS 提醒接进来，自动分诊并出简报"
examples_en:
  - "I want to write a Chinese review on laser welding process monitoring; help me scope it."
  - "Build the literature library for chapter 3 and verify every reference."
  - "Check whether the citations in section 3.2 really support the claim that the method is mainstream."
  - "Set up daily Web of Science alert triage and generate a brief."
version: "1.0.1"
author: "hsm-lnx"
---

# 中文综述工作台（合并包）

本 skill 把综述工作拆成两个**内部模块**，但以**一个 skill** 交付。这样上传到一次只能加载一个 skill 的平台时，两卷仍在同一个技能里，能互相读取、互相交接，不会出现「装了写作卷、找不到体系卷」的断链。

## 两个模块

| 模块 | 文件 | 管什么 | 判据 |
|---|---|---|---|
| 写作卷 | `references/survey-writing.md` | 学术判断：论断强度、引文匹配、概念定义、段落与章节结构、句法 | 读起来站不站得住 |
| 体系卷 | `references/survey-ops.md` | 机械运转：文献核验、全文定位、台账编号、Zotero、批量作业、落盘对账、每日 Alert 监控 | 对账对不对得上 |

**所有路径以本 skill 根目录为基准**：`references/`、`scripts/`、`templates/`、`tools/`。

## 怎么配合

两卷不是两个各干各的 skill，而是同一条生产线的上下游。完整契约在 `references/handoff.md`，核心是固定顺序：

1. **写作卷先定强度**：把将被支撑的那句话逐字写出来，判断弱／中／强／最高（写作卷 §2）。
2. **体系卷再取证**：核著录、取全文、入台账，回传编号＋A/B/C 等级＋不许丢的限定词。
3. **写作卷最后落笔**：按回传的编号、等级和限定词写，不得外推。

混合任务（补文献并写进正文）必须按这个顺序，不能跳步。**禁止先攒文献再编论点；禁止拿到编号就写、丢掉限定词。**

## 任务分流

接到任务先判断归哪一卷，只读对应模块，不要两卷整读。

| 任务 | 先读哪个 |
|---|---|
| 选题收敛／搭章节骨架／写一段／改一段／段落结构体检／概念命名／引文撑不撑得住 | `references/survey-writing.md` |
| 核文献／取全文／台账 diff／编号顺延／Zotero 写入／批量作业／覆盖与证据行校验 | `references/survey-ops.md` |
| 接每日 Alert／拉信分诊／生成新文献简报 | `references/survey-ops.md` §16 + `references/daily-lit.md` |
| 补文献并落笔／忠实性核对缺全文／台账变更影响正文／概念变动要同步台账 | 先读 `references/handoff.md`，再按接口调用两卷 |

判不准时问用户一句：**「读起来站不站得住，还是对账对不对得上？」**

## 跨卷交接的四个接口

细则见 `references/handoff.md`，这里只列最小字段：

| 接口 | 方向 | 必须带的东西 |
|---|---|---|
| 补文献请求 | 写作 → 体系 | 论断原文、强度要求、证据类型、现用占位、时效 |
| 验证回执 | 体系 → 写作 | 编号、A/B/C 等级、权威出处、**不许丢的限定词** |
| 台账变更 | 体系 → 写作 | 条号＋改了什么＋依据，由写作卷做冲击扫描 |
| 概念与台账同步 | 写作 → 体系 | 概念名／定义／首现位置／复用范围，同批更新 `docs/concepts.md` |

## 共享产物

两卷读写同一套项目文件；每日监控是可选模块，单独放在 `daily/`，不改动这套骨架：

```
manuscript/       正文
pdfs/             本地全文
bib/verified.md   文献台账（只增不改、编号顺延）
docs/             progress.md / claims.md / concepts.md
reports/          回执与报告
reports/_raw/     接口原始返回、改动前备份
daily/            每日 Alert 监控工作目录（可选；config.json 含授权码，禁止提交）
```

## 脚本

| 脚本 | 用途 |
|---|---|
| `scripts/verify_round1.py` | Crossref DOI／书目、arXiv 存在性核验 |
| `scripts/aminer_search.py` | AMiner 层（需 `AMINER_API_KEY`） |
| `scripts/arxiv_curl.py` | arXiv API 的 curl 兜底 |
| `scripts/cite_coverage.py` | 正文引用覆盖核对 |
| `scripts/faithfulness_check.py` | 忠实性证据行校验 |
| `scripts/zotero_client.py` | Zotero Web API 直写通道 |

用法见体系卷对应节。脚本只用 Python 标准库；密钥只走环境变量，缺 key 时脚本直接报错退出，不降级为「查询无果」。

每日 Alert 监控脚本在 `scripts/daily/`，先跑 `init_daily.py` 生成工作目录：

| 脚本 | 用途 |
|---|---|
| `scripts/daily/init_daily.py` | 初始化 `daily/`：建目录、复制脚本、生成配置与分诊模板 |
| `scripts/daily/pull_mail.py` | IMAP 拉取 Alert 邮件，按 Message-ID 去重 |
| `scripts/daily/parse_alerts.py` | 把 Alert HTML 解析成 `_parsed.md` |
| `scripts/daily/enrich_crossref.py` | 题名→DOI→著录/摘要，并与台账、正文、历史简报对重 |
| `scripts/daily/run_daily.ps1` / `.sh` | 每日总调度（Windows / macOS·Linux） |
| `scripts/daily/check_alert_links.py` / `uid_gaps.py` | 只读诊断 |
| `scripts/daily/SOURCE.md` | 与原 `mail_daily` 工作版的逐项来源对照 |

边界：日报只做分诊，不写台账、不改正文；纳入仍走 `references/handoff.md` 的取证流程。详见 `references/daily-lit.md`。

每日监控的核心脚本直接复制自原 `mail_daily` 工作版，不是替代实现：`parse_alerts.py` 逐字节相同，其余只改配置路径与解释器定位；真实 `config.json`、历史邮件、简报与去重台账未随包分发。

## 部署与体检

1. 体检脚本在本 skill 的 `tools/doctor.py`。装到项目 `.claude/skills/survey-manager/` 后，从项目根目录跑 `python .claude/skills/survey-manager/tools/doctor.py --project-root .`；也可把它复制成 `.claude/doctor.py` 后按本地安装版路径跑。它检查 Python、pandoc、Zotero 与外部接口；配置 AMiner／Zotero 密钥用 `--configure`。平台沙箱里不能装本地软件时，至少确认 Python 3.8+ 且能访问 Crossref／arXiv。体检只读，不改文献库。
2. 建议在项目里建上述目录骨架；病例写到 `reports/cases/`，改动正文前先备份到 `reports/_raw/`。
3. 密钥只走环境变量：`AMINER_API_KEY`、`ZOTERO_USER_ID`、`ZOTERO_API_KEY`。申请与填写方法见 `references/KEY_SETUP.md`；任何文件都不得写入 key。唯一例外是每日监控的邮箱授权码：只存在本机 `daily/config.json`，由 `.gitignore` 排除，禁止提交或外传。
