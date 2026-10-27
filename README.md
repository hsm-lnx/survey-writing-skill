# survey-writing skill — 通用快照版

一套中文综述写作规范的 Claude Code skill，含文献存在性核验、引用覆盖核对、Zotero 直写通道。

这是 **v3.0-clean 快照**：条文完整，病例已匿名化，不含任何原始项目的正文、文献编号、文件路径或行号。

## 三步部署

```powershell
git clone <本仓库地址> survey-writing-skill
cd survey-writing-skill
powershell -ExecutionPolicy Bypass -File install.ps1
```

`install.ps1` 会做四件事：把 skill 拷到 `~\.claude\skills\survey-writing\`、在当前目录建写作骨架、检查 `python` / `pandoc` / `curl`、提示你还缺哪些环境变量。

装到某个具体项目里（而不是全局）：

```powershell
powershell -ExecutionPolicy Bypass -File install.ps1 -ProjectRoot D:\my_survey
```

POSIX 环境用 `bash install.sh [项目目录]`。

## 密钥

**本包不含任何密钥，也不需要大模型 API key。** 只有两个可选的外部服务凭证，填法见 [`KEY_SETUP.md`](KEY_SETUP.md)：

| 变量 | 何时需要 | 不给会怎样 |
|---|---|---|
| `AMINER_API_KEY` | 跑 `aminer_search.py`（中文文献、无 DOI 老文献） | 该脚本报错退出；Crossref / arXiv 两层照常可用 |
| `ZOTERO_USER_ID` + `ZOTERO_API_KEY` | 跑 `zotero_client.py`（§10 直写通道） | 该脚本报错退出；skill 其余部分不受影响 |

密钥一律走环境变量，仓库里只有 `.env.example` 占位符。

## 包内结构

```
skills/survey-writing/
├── SKILL.md                         规范条文 v3.0-clean（§0–§13）
├── references/citation_style_notes.md   著录转换规则（IEEE / GB-T 7714 / 缩写表）
├── templates/section_workflow.md        章节五步循环模板
└── scripts/
    ├── verify_round1.py            存在性核验：Crossref DOI + 书目 + arXiv
    ├── aminer_search.py            存在性核验：AMiner 层（需 AMINER_API_KEY）
    ├── arxiv_curl.py               arXiv API 的 curl 兜底（urllib 被 406 时）
    ├── cite_coverage.py            正文引用覆盖核对（§4.1）
    └── zotero_client.py            Zotero Web API 直写通道（§10）
tools/convert.cmd                   docx → markdown（pandoc）
```

## 依赖

- **Python 3.8+**，仅标准库，无第三方包
- **pandoc**（`tools/convert.cmd` 用），非必需
- **curl**（`arxiv_curl.py` 用），非必需

## 建议的项目布局

部署后在项目根建好这套骨架，脚本默认按此读写：

```
manuscript/      正文
bib/verified.md  文献台账（只增不改、编号顺延）
docs/            progress.md / claims.md / concepts.md
reports/         回执与报告
reports/_raw/    接口原始返回逐条落盘
```

## 关于病例

§0 元规则要求「新条文只能由已确诊病例逼出（附病例位置）」。快照版只保留一行匿名摘要作为线索，**病例原文不在本包内**。用起来之后请在你自己的项目里重建病例档案（建议 `reports/cases/`），否则条文会失去自检能力。

## 更新

本包是快照，不跟上游自动同步。需要新条文时，按 §0 在你自己的项目里长出来，再决定是否回灌本仓库。
