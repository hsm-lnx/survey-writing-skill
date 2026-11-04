# survey-writing / survey-ops — 综述写作双卷 skill

一套中文综述写作规范，拆成两卷 Claude Code skill：

| 卷 | 管什么 | 判据 |
|---|---|---|
| `survey-writing` | 写作与学术判断：句子怎么写、论断配多强证据、概念怎么定、结构成不成立、引文撑不撑得住 | 「读起来站不站得住」 |
| `survey-ops` | 机械运转：核验脚本、全文取得、台账 diff、编号顺延、Zotero 写入、批量作业、落盘对账 | 「对账对不对得上」 |

两卷之间的交接物（补文献请求、验证回执、台账变更、概念同步、混合任务顺序）写死在 `skills/_shared/handoff.md`。

这是 **v3.1-clean 快照**：条文完整，病例已匿名化，不含任何原始项目的正文、文献编号、文件路径或行号。

## 三步部署

```powershell
git clone <本仓库地址> survey-writing-skill
cd survey-writing-skill
powershell -ExecutionPolicy Bypass -File install.ps1
```

`install.ps1` 会做四件事：把两卷 skill 与 `_shared` 拷到 `~\.claude\skills\`、在当前目录建写作骨架（含 `pdfs/`）、检查 `python` / `pandoc` / `curl`、提示你还缺哪些环境变量。

装到某个具体项目里（而不是全局）：

```powershell
powershell -ExecutionPolicy Bypass -File install.ps1 -ProjectRoot D:\my_survey
```

POSIX 环境用 `bash install.sh [项目目录]`。

## 密钥

**本仓库不含任何密钥**，`.env.example` 里只有占位符。

关于「要不要大模型 API key」，分三层说清楚：

1. **本包自身不需要模型 key。** 包里全是条文与 Python 脚本，没有任何一处调用大模型 API，因此没有 `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` 之类的配置项。
2. **模型由你使用的 agent 提供，用你自己的账号与额度。** 你在 Claude Code 或别的 agent 里跑这套 skill，认证走那个 agent 自己的登录／密钥体系，与本仓库无关，本仓库也无从读取。
3. **脚本只需要两个可选的外部文献服务凭证**，不给也不影响其余功能：

| 变量 | 何时需要 | 不给会怎样 |
|---|---|---|
| `AMINER_API_KEY` | 跑 `aminer_search.py`（中文文献、无 DOI 老文献） | 该脚本报错退出；Crossref / arXiv 两层照常可用 |
| `ZOTERO_USER_ID` + `ZOTERO_API_KEY` | 跑 `zotero_client.py`（§10 直写通道） | 该脚本报错退出；skill 其余部分不受影响 |

填法见 [`KEY_SETUP.md`](KEY_SETUP.md)。一律走环境变量，脚本不读取 `.env` 文件，也不得硬编码 key。

## 包内结构

```
skills/
├── survey-writing/                      写作卷（学术判断）
│   ├── SKILL.md                         §0–§6、§9、§11–§14
│   ├── references/citation_style_notes.md   著录转换规则（IEEE / GB-T 7714 / 缩写表）
│   └── templates/section_workflow.md        章节五步循环模板
├── survey-ops/                          体系卷（机械运转）
│   ├── SKILL.md                         §6A、§7、§8、§10、§15
│   └── scripts/
│       ├── verify_round1.py             存在性核验：Crossref DOI + 书目 + arXiv
│       ├── aminer_search.py             AMiner 层（需 AMINER_API_KEY）
│       ├── arxiv_curl.py                arXiv API 的 curl 兜底（urllib 被 406 时）
│       ├── cite_coverage.py             正文引用覆盖核对（§4.1）
│       ├── faithfulness_check.py        忠实性核对证据行校验（§4.2）
│       └── zotero_client.py             Zotero Web API 直写通道（§10）
└── _shared/handoff.md                   两卷交接契约
tools/convert.cmd                        docx → markdown（pandoc）
```

## 两卷怎么分工

拿到一句话，先按判据分卷，再动手：

| 用户怎么说 | 去哪 |
|---|---|
| 「这段读着飘／太满／撑不住」 | 写作卷 §0 §2 §13，先判论断强度 |
| 「这条引文对不对／够不够」 | 写作卷 §4 §4.1 §4.2，先看 A/B/C 等级 |
| 「补一篇文献并写进来」 | **混合任务**：写作卷写论断 → 体系卷取证 → 写作卷落笔 |
| 「录入／核验／对账／编号／备份」 | 体系卷 §6A §7 §8 §10 |
| 纯查询、图表工程、投稿格式、结构重排 | 两卷都不加载，按批处理 |

**判不准时**：问「读起来站不站得住？」→ 写作卷；问「对账对不对得上？」→ 体系卷。

## 关于忠实性核对（§4.2）

这是本快照相对早期版本的主要新增。要点是**三级三动作**，不是无差别地把所有文献重读一遍：

| 等级 | 动作 |
|---|---|
| A（已对照原文） | **不重核**，只做失效检查：转述强度升格、限定词被删、所指命题换面，任一发生即降 B |
| B（只有摘要） | **先取全文**，再核支撑该句的那段原文，摘出关键句升 A |
| C（只有书目） | **先补证**，谈不上核对；取不到则不得独立承担论断 |

核对结论必须落成证据行（五列），并跑校验器：

```
python skills/survey-ops/scripts/faithfulness_check.py <证据表.md> -c <manuscript.md>
```

它机械判五件事：表结构、强度与等级枚举、B/C 不得承担强论断、升 A 须摘原文、论断原文须在正文中逐字找到（找不到即正文已改、等级失效）。退出码 0 才可交付。`--template` 印空表头。

## 依赖

- **Python 3.8+**，仅标准库，无第三方包
- **pandoc**（`tools/convert.cmd` 用），非必需
- **curl**（`arxiv_curl.py` 用），非必需

## 建议的项目布局

部署后在项目根建好这套骨架，脚本默认按此读写：

```
manuscript/      正文
pdfs/            本地全文（§4.2 核对用）
bib/verified.md  文献台账（只增不改、编号顺延）
docs/            progress.md / claims.md / concepts.md
reports/         回执与报告
reports/_raw/    接口原始返回、改动前备份
```

## 关于病例

§0 元规则要求「新条文只能由已确诊病例逼出（附病例位置）」。快照版只保留一行匿名摘要作为线索，**病例原文不在本包内**。用起来之后请在你自己的项目里重建病例档案（建议 `reports/cases/`），否则条文会失去自检能力。

## 更新

本包是快照，不跟上游自动同步。需要新条文时，按 §0 在你自己的项目里长出来，再决定是否回灌本仓库。
