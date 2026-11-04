# survey-writing / survey-ops

Claude Code 的中文综述写作规范，拆成两卷 skill。

- **写作卷 `survey-writing`** 管学术判断：这句话说得过不过头、论断配多强的证据、概念怎么定、段落结构成不成立。
- **体系卷 `survey-ops`** 管机械运转：文献核验、全文定位、台账编号、Zotero 写入、批量作业、落盘对账。

一句话判据：**「读起来站不站得住」→ 写作卷；「对账对不对得上」→ 体系卷。** 两卷的交接物写在 `skills/_shared/handoff.md`。

## 它治什么毛病

写综述时最常出、也最难自己发现的三类事：

| 症状 | 它的反应 |
|---|---|
| 「这方法已成主流」，其实只挂了一篇文献 | 判为中／强论断，要求 2 至 3 篇支撑；不够就让你改措辞，而不是放行 |
| 某条引文是从摘要推的，原文没那么说 | 该位置记为 B 级，要求先取全文、再核关键句；核不了就不得承担强论断 |
| 正文加了三条引用，编号全乱 | 跑 diff 报告，台账顺延；正文号与台账号各自独立，任何一方禁止重编号 |

它不会替你写论文，它替你**拦住**那些交稿后才被审稿人指出的问题。

## 安装

需要 **Python 3.8+**（只用标准库，无第三方包）、一个能读 skill 文件的 agent（Claude Code 或同类）。

```bash
git clone https://github.com/hsm-lnx/survey-writing-skill.git
cd survey-writing-skill
```

**Windows**

```powershell
powershell -ExecutionPolicy Bypass -File install.ps1 -ProjectRoot D:\my_survey
```

**macOS / Linux**

```bash
bash install.sh ~/my_survey
```

把 `D:\my_survey` 换成你自己的项目目录。脚本做四件事：

1. 两卷 skill 与 `_shared` 装到 `<项目>/.claude/skills/`——在该项目里开 Claude Code 就会自动加载
2. 建好 `manuscript/ pdfs/ bib/ docs/ reports/ reports/_raw/` 骨架，并写入台账与进度板表头
3. 检查 python / pandoc / curl（后两个可选）
4. 报告还缺哪些可选环境变量

想要全局可用（所有项目都能读）：**不带** `-ProjectRoot`，装到 `~/.claude/skills/`。此时不建项目骨架，只装 skill。

> 若你直接在本仓库目录里跑脚本，它会识别出来并跳过骨架，避免把干净的 clone 弄脏。要在本仓库里试，加 `-SkipSkeleton`。

## 装完怎么用

在项目里打开 Claude Code，直接说人话，不用记命令：

```
帮我把第 3 节过一遍，读着有点飘
帮我核一下这 120 条文献，哪几条撑不住强论断
补一篇关于 XXX 的文献，并写进 4.2
```

规范里的任务分流表会把它分到对应卷。判不准时它会问你：**读起来站不站得住？还是对账对不对得上？**

「补一篇文献并写进来」是唯一必须按固定顺序走的混合任务：写作卷先把论断逐字写出来定强度 → 体系卷去取全文、验著录 → 写作卷按编号和限定词落笔。跳过第一步，体系卷就不知道该找什么等级的证据。

## 关于忠实性核对

这是本快照相对早期版本的主要新增（写作卷 §4.2）。要点是**三级三动作**，不是把所有文献无差别重读一遍：

| 等级 | 含义 | 动作 |
|---|---|---|
| A | 已对照本地原文核实过这个位置 | **不重核**，只做失效检查：转述改过、限定词被删、所指命题换面，任一发生即降 B |
| B | 只有摘要或出版方页面 | **先取全文**，再核支撑该句的那段原文，摘出关键句升 A |
| C | 只有题名或书目元数据 | **先补证**，谈不上核对；取不到就不得独立承担论断 |

单位是**引用位置**，不是文献——同一篇文献在不同位置的证据等级可以不同。

核对结论必须落成证据行（五列：正文位置／论断原文／强度／原文关键句／原等级→新等级），并跑校验器：

```
python .claude/skills/survey-ops/scripts/faithfulness_check.py 证据表.md -c 正文.md
```

它机械判五件事：表结构完整、强度与等级枚举合法、B/C 级不得承担强论断、升 A 必须摘了原文、论断原文能在正文中逐字找到（找不到即正文已改，等级失效）。退出码 0 才算过。`--template` 印空表头。

## 密钥

**本仓库不含任何密钥**，`.env.example` 里只有占位符。关于「要不要大模型 API key」，分三层：

1. **本包自身不需要模型 key。** 包里全是条文和 Python 脚本，没有任何一处调用大模型 API，所以没有 `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` 这类配置项。
2. **模型由你使用的 agent 提供，用你自己的账号与额度。** 认证走 Claude Code（或别的 agent）自己的登录／密钥体系，与本仓库无关，本仓库也无从读取。
3. **脚本只需要两个可选的外部文献服务凭证**，不给也不影响其余功能：

| 变量 | 何时需要 | 不给会怎样 |
|---|---|---|
| `AMINER_API_KEY` | 跑 `aminer_search.py`（中文文献、无 DOI 老文献） | 该脚本报错退出；Crossref / arXiv 两层照常可用 |
| `ZOTERO_USER_ID` + `ZOTERO_API_KEY` | 跑 `zotero_client.py`（Zotero 直写通道） | 该脚本报错退出；skill 其余部分不受影响 |

一律走环境变量：脚本不读 `.env` 文件，也不得硬编码 key。填法见 [`KEY_SETUP.md`](KEY_SETUP.md)。

## 包内结构

```
skills/
├── survey-writing/                      写作卷（学术判断）
│   ├── SKILL.md                         §0–§6、§9、§11–§14
│   ├── references/citation_style_notes.md   著录转换规则
│   └── templates/section_workflow.md        章节五步循环模板
├── survey-ops/                          体系卷（机械运转）
│   ├── SKILL.md                         §6A、§7、§8、§10、§15
│   └── scripts/
│       ├── verify_round1.py             存在性核验：Crossref DOI + 书目 + arXiv
│       ├── aminer_search.py             AMiner 层（需 AMINER_API_KEY）
│       ├── arxiv_curl.py                arXiv API 的 curl 兜底（urllib 被 406 时）
│       ├── cite_coverage.py             正文引用覆盖核对（写作卷 §4.1）
│       ├── faithfulness_check.py        忠实性核对证据行校验（写作卷 §4.2）
│       └── zotero_client.py             Zotero Web API 直写通道（§10）
└── _shared/handoff.md                   两卷交接契约
tools/convert.cmd                        docx → markdown（pandoc）
```

节号沿用分卷前的编号，不重排——历史记录里的 § 引用照原号读即可。

## 建议的项目布局

脚本默认按这套骨架读写，安装时已自动建好：

```
manuscript/      正文
pdfs/            本地全文，§4.2 核对用
bib/verified.md  文献台账：只增不改、编号顺延
docs/            progress.md / claims.md / concepts.md
reports/         回执与报告
reports/_raw/    接口原始返回、改动前备份
```

## 关于病例

写作卷 §0 有条元规则：**新条文只能由已确诊病例逼出**。快照版每条只保留一行匿名摘要作为线索，病例原文不在本包内。用起来之后请在自己的项目里重建病例档案（建议 `reports/cases/`），否则条文会慢慢失去自检能力。

## 依赖与更新

- Python 3.8+，仅标准库
- pandoc（`tools/convert.cmd` 用）、curl（`arxiv_curl.py` 用），都非必需

本包是**节点快照**，不跟上游自动同步。需要新条文时，按 §0 在你自己的项目里长出来，再决定是否回灌本仓库。
