# survey-writing / survey-ops：中文综述写作助手

> **版本 1.0.3（2026-11-08）**：两卷 skill 对齐源 skill 最新版——写作卷 v3.6（v3.5 补 §1 首创自称禁令、§5 同一论断只在一处完整承担、§11.10 指代用属性、§12.5 边界义务适用前提、§12A H6 推论逐跳、§13 E9 语域失配；v3.6 把 §14 工序全文移入 `references/14_mechanism.md`），体系卷 v3.3（§8.5 撤稿空置／改派登记、§8.8 Zotero 入库验收六步、§15 演进游标改指纹＋条数）。只更新条文与一份工序参考文件，安装方式不变。
>
> **版本 1.0.2（2026-11-05）**：两卷 skill 对齐源 skill 最新版——写作卷 v3.4（§11 概念台账与首现纪律补强、§11.9 分类双闸门、§13 E8 标签化列举惯性、§14 案例聚合与整体回顾），体系卷 v3.2（§15 同步聚合与整体回顾）。只更新条文，安装方式与目录结构不变。
>
> **版本 1.0.1（2026-11-04）**：新增可选的**每日文献 Alert 监控**——把 Web of Science 等数据库的保存检索接进项目，每天自动拉信、解析、补著录、去重、分诊，有新文献才出简报，没新增就安静。见 [§4.8](#48-邮箱-alert--imap-授权码可选)。

一套给**中文综述写作**用的 Claude Code skill。你给它一个模糊的题目，它按固定流程把这件事做完：

**收敛范围 → 建文献库 → 搭章节骨架 → 逐段写 → 逐条核 → 交付可查的稿子。**

装好之后，在项目里打开 Claude Code，直接用中文说你要做什么，不用记脚本、不用背命令。

> **它不是润色器。** 润色只是最后一道工序。它真正管的是：文献从哪来、能不能查证、每条引文撑不撑得住那句话、章节结构立不立得住、写完之后正文编号和文献台账对不对得上。

**第一次用？** 按 §2 安装 → §3 看体检报告 → §5 走一遍「从模糊题目到章节骨架」。已经装好了，直接看 §6。

**目录：** [它能做什么](#0-它到底能帮你做什么) · [怎么产出](#1-一条综述是怎么产出的) · [安装](#2-五分钟上手) · [体检](#3-体检报告怎么读) · [外部工具](#4-外部工具逐个说明) · [每日监控](#48-邮箱-alert--imap-授权码可选) · [第一次用](#5-第一次用从一个模糊题目开始) · [日常用法](#6-日常怎么用按任务查) · [质量闸门](#7-它拦什么质量闸门) · [FAQ](#10-常见问题faq)

---

## 0. 它到底能帮你做什么

| 阶段 | 你只需要说 | 它产出什么 |
|---|---|---|
| **立题与范围** | 「我想写一篇 XX 的中文综述，范围还没想好」 | 用几个问题收敛读者、篇幅、时间窗、边界；给出章节总纲供你确认 |
| **建文献库** | 「按第 3 章的提纲把文献收进来」 | 逐条检索 Crossref／arXiv／AMiner，核验后写入 `bib/verified.md`，编号顺延；查不到的标 [待验证]，不编造 |
| **日常管理** | 「这周新下的 20 篇入库」「Zotero 里会议论文类型错了，批量改」 | 台账去重、补字段、编号对账、变更 diff；Zotero 批量修正并写入后回读断言 |
| **每日新文献** | 「把每天的 WOS 提醒接进来，自动分诊」 | 拉 Alert 邮件 → 解析 → 补 DOI/摘要 → 与台账/正文对重 → 出候选简报（只分诊，不入账） |
| **搭骨架** | 「第 3 章按这个方向搭骨架」 | 章节总纲 → 段落提纲（每段一句论述指向 + 拟引台账编号），你确认后才动笔 |
| **填血肉** | 「按提纲写 3.2」 | 证据池 → 段稿 → 删引测试 → 【作者 年份】占位替换成 [n] → 本节引用明细表 |
| **自检交付** | 「核一下 3.2，哪几条撑不住『主流』这个说法」 | 引用覆盖报告、忠实性 A/B/C 证据行、结构体检表、句法病句清单 |
| **长期演进** | 「演进 skill」 | 把项目里积累的病例变成新条文，下一轮自动生效 |

**它不是什么：**

- **不是「一句话出整篇」的黑箱。** 章节总纲、段落提纲、结构改动、强论断，这几处都会停下来等你确认。
- **不是只改措辞的润色器。** 句法规则只是最外层，里面还有文献库、论断强度、忠实性核对和结构审查。
- **不会编文献。** 查不到就是查不到，标 [待验证]，绝不伪造 DOI、卷号、页码。
- **不会偷偷改你的正文。** 体系卷不碰正文；写作卷改动前先备份到 `reports/_raw/`。

### 和直接把稿子丢给 AI 写，有什么不同

| | 直接让 AI 写 | 这套 skill |
|---|---|---|
| **文献** | 可能编造，出处经不起查 | 每条过 Crossref／arXiv 核验，查不到的再走 AMiner；仍查不到标 [待验证]，查询记录落盘 |
| **引文** | 摘要当原文用，转述容易过头 | 按引用位置分 A/B/C，B/C 不得撑中／强论断 |
| **结构** | 一次生成，改一处牵动全文 | 总纲 → 段落提纲 → 逐段写，可只返工一段 |
| **编号** | 增删文献后编号漂移 | 正文号与台账号双轨，变动走 diff 报告 |
| **记忆** | 换个会话就从零开始 | 台账、进度板、概念台账都在项目里，接着做 |

**适合谁：** 正在写中文综述的研究生、需要把课题组文献整理成库的人、投稿前想做一次系统自检的人。

**不适合谁：** 想跳过读文献、直接生成一篇成稿的人。这套流程会不断要求你确认论断和证据。

---

## 1. 一条综述是怎么产出的

```
① 收敛范围    你的模糊需求
               ↓ 读者 / 篇幅 / 时间窗 / 边界
② 搭骨架      章节总纲 ──你确认──▶ 段落提纲（每段一句论述指向 + 拟引编号）
                                     ↓
③ 建库/出料   检索 · 核验 · 去重 ──▶ bib/verified.md + 本节证据池
                                     ↓
④ 加工        按论断强度配引文
               ↓
⑤ 删引测试    段稿【作者 年份】
               ↓
⑥ 挂引用      占位 → [n] ──▶ 正文 + 引用明细表 + 待补文献清单
               ↓
⑦ 自检        覆盖 / 忠实性 / 结构 / 句法 ──▶ 可交付稿 + 落盘回执
```

它拆成两卷，各管一头：

| 卷 | 管什么 | 典型任务 |
|---|---|---|
| **写作卷 `survey-writing`** | 学术判断 | 这句话说得过不过头、论断配多强的证据、概念怎么定、段落结构成不成立 |
| **体系卷 `survey-ops`** | 机械运转 | 文献核验、全文定位、台账编号、Zotero 写入、批量作业、落盘对账 |

一句话判据：**「读起来站不站得住」→ 写作卷；「对账对不对得上」→ 体系卷。** 两卷怎么交接写在 `skills/_shared/handoff.md`。

你不需要记住这个分工。说人话，规范会自己分流；判不准时它会反问你。

---

## 2. 五分钟上手

### 2.1 先看你要准备什么

这张表就是全部外部依赖，没有隐藏项。

| 依赖 | 必须？ | 用来做什么 | 不装 / 不配会怎样 | 怎么搞定 |
|---|---|---|---|---|
| **Claude Code**（或能读 skill 的 agent） | **必须** | 运行 skill 的宿主 | 用不了 | 你已经在用 Claude Code 的话不用管 |
| **Python 3.8+** | **必须** | 跑核验、引用覆盖、证据校验脚本 | 脚本跑不了；写作条文仍可读 | 安装脚本可自动装，或到 [python.org](https://www.python.org/downloads/) |
| **网络：Crossref + arXiv** | **必须** | 文献存在性核验 | 无法核验文献，只能手工查 | 能正常打开网页即可；公司代理见 §4.7 |
| pandoc | 可选 | docx → markdown 转换 | `tools/convert.cmd` 不可用 | `python .claude/doctor.py --fix` 自动装 |
| curl | 可选 | arXiv 406 时的兜底通道 | 极少数 arXiv 查询失败 | `--fix` 自动装；Win10+ / macOS 通常自带 |
| **Zotero 桌面版** | 推荐 | 本地 PDF 全文；体系卷 §7.4 的「两处查找」 | 只能扫 `pdfs/`，本地全文来源少一处 | `--fix --with-zotero` 自动装，或到 [zotero.org/download](https://www.zotero.org/download/) |
| Zotero Web API key + userID | 可选 | 批量修正 Zotero 条目字段 | Zotero 直写通道不可用 | `python .claude/doctor.py --configure` 交互配置 |
| AMiner token | 可选 | 中文文献、无 DOI 老文献核验 | AMiner 层不可用；Crossref/arXiv 照常 | `--configure` 交互配置 |
| **邮箱 IMAP + 客户端授权码** | 可选 | 每日文献 Alert 自动拉信 | 每日监控不可用；其余功能照常 | 见 [§4.8](#48-邮箱-alert--imap-授权码可选)；QQ/Gmail/Outlook 均可 |
| 大模型 API key | **不需要** | — | — | 模型由你的 Claude Code 账号提供，与本仓库无关 |

**一句话：只有 Python 和网络是硬门槛；Zotero、AMiner、pandoc、curl、邮箱 IMAP 都是可选项，不配也能用核心功能。**

> `doctor.py` 有两个位置：还在仓库里时用 `python tools/doctor.py`；装完以后用 `python .claude/doctor.py`。**下面所有 `.claude/...` 路径，用户级安装时都换成 `~/.claude/...`**（Windows 是 `$HOME\.claude\...`）。

### 2.2 第 1 步：拿到本仓库

```bash
git clone https://github.com/hsm-lnx/survey-writing-skill.git
cd survey-writing-skill
```

没有 git？打开仓库页面 → 绿色 **Code** 按钮 → **Download ZIP** → 解压，然后进入解压后的目录。

### 2.3 第 2 步：运行安装脚本

把 `D:\my_survey`（Windows）或 `~/my_survey`（macOS/Linux）换成你自己的项目目录。目录不存在没关系，脚本会建。

**Windows**（在仓库目录里打开 PowerShell）：

```powershell
powershell -ExecutionPolicy Bypass -File install.ps1 -ProjectRoot D:\my_survey -AutoInstall
```

**macOS / Linux**（在仓库目录里打开终端）：

```bash
bash install.sh ~/my_survey --auto-install
```

脚本会做五件事：

1. 把两卷 skill 与 `_shared` 装到 `<项目>/.claude/skills/`——在该项目里开 Claude Code 就会自动加载；
2. 建好 `manuscript/ pdfs/ bib/ docs/ reports/ reports/_raw/` 骨架，并写入台账与进度板表头；
3. 检查 Python / pandoc / curl；带 `-AutoInstall` / `--auto-install` 时，缺什么就尝试用系统包管理器装；
4. 把体检脚本 `doctor.py` 和密钥说明 `KEY_SETUP.md` 复制到 `<项目>/.claude/`；
5. 自动跑一次环境体检，把缺的东西列出来。

> 每日文献监控是**可选模块**，安装脚本不会自动建 `daily/`。需要时按 [§4.8](#48-邮箱-alert--imap-授权码可选) 单独初始化；它不改动上面的项目骨架。

> **只想让所有项目都能用？** 不带 `-ProjectRoot` / 项目目录即可，装到 `~/.claude/skills/`。此时骨架建在你**当前所在目录**，所以请先 `cd` 到你的项目目录再运行。

| 你的情况 | 怎么装 | 结果 |
|---|---|---|
| 只在一个综述项目里用（推荐） | 带 `-ProjectRoot D:\my_survey` / `~/my_survey` | skill 只在该项目加载；骨架建在该项目 |
| 想让所有项目都能用 | 不带项目目录，先 `cd` 到你想建骨架的目录 | skill 装到 `~/.claude/skills/`；骨架建在当前目录 |

### 2.4 第 3 步：按体检报告补齐

安装脚本最后会打印一份体检报告。看到 `[X]` 就按提示处理；看到 `[!]` 是可选项，不影响核心功能。怎么读见 §3。

### 2.5 第 4 步：配置可选密钥（需要时才做）

只有你要用 **AMiner** 或 **Zotero 直写** 时才需要。运行交互式配置：

```powershell
python .claude\doctor.py --configure
```

```bash
python3 .claude/doctor.py --configure
```

它会一步步问你，输入时不回显，自动验证，然后写进你的用户环境变量。**不会**写进仓库，也**不会**碰你的文献库。详细说明见 [`KEY_SETUP.md`](KEY_SETUP.md)。

### 2.6 第 5 步：打开 Claude Code

```bash
cd D:\my_survey
claude
```

然后直接说人话。第一次用建议从 §5 的对话示例开始。

---

## 3. 体检报告怎么读

`doctor.py` 的输出分七段：必需项、可选命令行工具、Zotero、外部账号与密钥、网络与接口、安装状态、每日监控（可选）。每行前面有一个标记：

| 标记 | 含义 | 你要做什么 |
|---|---|---|
| `[OK]` | 已就绪 | 不用管 |
| `[!]` | 可选项缺失，或有问题但不致命 | 看后面的「解决」；不影响核心功能可以先跳过 |
| `[X]` | 必需项未满足 | 必须处理，否则脚本跑不起来 |
| `[-]` | 跳过（比如 `--offline`，或没配密钥） | 需要该功能时再配 |
| `[i]` | 只是信息 | 不用管 |

随时可以重新体检：

```powershell
cd D:\my_survey
python .claude\doctor.py
```

```bash
cd ~/my_survey
python3 .claude/doctor.py
```

> Windows 上如果 `python` 不可用，试 `py .claude\doctor.py`。macOS/Linux 上如果没有 `python`，用 `python3`。

常见 `[X]` / `[!]` 的处置：

| 报告 | 意思 | 怎么办 |
|---|---|---|
| `[X] Python：当前 2.7，需要 3.8+` | Python 太老 | 装 Python 3.8+，重开终端 |
| `[X] ZOTERO_USER_ID 一致性` | 环境变量里的 userID 和 key 不属于同一个账号 | 跑 `--configure` 重新配；写错库比不写更糟 |
| `[!] AMINER_API_KEY 未设置` | 没配 AMiner | 可选；要用中文/无 DOI 文献核验时再跑 `--configure` |
| `[!] ZOTERO_API_KEY 未设置` | 没配 Zotero 直写 | 可选；只用写作规范和 Crossref 核验的话不用管 |
| `[!] Zotero 本地 API：HTTP 403` | Zotero 在运行，但本地 API 没开 | 可选；要用本地 API 才去 Zotero 设置里允许 |
| `[!] skill：当前在仓库目录里` | 你还没把 skill 装到项目 | 回到仓库目录，按 §2.3 带 `-ProjectRoot` 重跑 |
| `[!] pandoc 未安装` | 不能 docx→md | 可选；`python .claude/doctor.py --fix` 自动装 |
| `[!] arXiv：返回 406` | urllib 被 arXiv 限流 | 装 curl 后 `arxiv_curl.py` 可兜底；`--fix` 自动装 |
| `[!] Crossref：连接超时` | 网络/代理问题 | 检查代理；公司网络见 §4.7 |
| `[!] 每日监控配置：这些字段还没填好` | `daily/config.json` 有缺项或占位符 | 按 §4.8 填，再跑 `python check_config.py`；doctor 不显示授权码 |

退出码：`0` = 必需项齐全；`1` = 有必需项不满足；`2` = 用法或配置过程出错。

---

## 4. 外部工具逐个说明

### 4.1 Python 3.8+（必须）

**用途**：`verify_round1.py`、`aminer_search.py`、`arxiv_curl.py`、`cite_coverage.py`、`faithfulness_check.py`、`zotero_client.py` 全部是 Python 脚本。只用标准库，不需要 `pip install` 任何东西。

**怎么装**：

- Windows：`winget install --id Python.Python.3.12 -e`，或到 [python.org](https://www.python.org/downloads/) 下载安装包。安装时勾选 **Add Python to PATH**。
- macOS：`brew install python`，或到 python.org 下载。
- Linux：`sudo apt install python3`（Debian/Ubuntu）、`sudo dnf install python3`（Fedora）、`sudo pacman -S python`（Arch）。

**验证**：

```bash
python --version        # Windows
python3 --version       # macOS/Linux
```

> 脚本文档里写的是 `python`。如果你的系统只有 `python3`，把命令里的 `python` 换成 `python3` 即可。

### 4.2 pandoc（可选）

**用途**：`tools/convert.cmd` 把 docx 转成 markdown，供后续核对。不装只影响「docx → md」这一步。

**怎么装**：

- Windows：`winget install --id JohnMacFarlane.Pandoc -e`
- macOS：`brew install pandoc`
- Linux：`sudo apt install pandoc` / `sudo dnf install pandoc`

**验证**：`pandoc --version`。

### 4.3 curl（可选）

**用途**：arXiv 对 Python urllib 的 TLS 指纹间歇返回 406，`arxiv_curl.py` 改用 curl 请求同一个 arXiv API。Windows 10+、macOS、大多数 Linux 已自带。

**验证**：`curl --version`。

### 4.4 Zotero 桌面版（推荐，非必须）

**用途**：两件事——（1）从 Zotero storage 里找本地 PDF 全文，配合写作卷 §4.2 的忠实性核对；（2）Zotero 10+ 的本地 API 可以写入。没有桌面版，Web API 写入仍可用，但本地全文会少一处来源。

**怎么装**：到 [zotero.org/download](https://www.zotero.org/download/) 下载，或用 `python .claude/doctor.py --fix --with-zotero`。

**验证**：打开 Zotero，`doctor.py` 会显示「Zotero 程序」和「Zotero 数据目录」，并统计 `storage` 里的 PDF 数量。

> 数据目录默认是 `C:\Users\<你>\Zotero`（Windows）或 `~/Zotero`（macOS/Linux）。如果你在 Zotero 设置里改过位置，doctor 会尝试从 `prefs.js` 读出来。读不到时会提示你手动确认。

### 4.5 Zotero Web API key + userID（可选）

**用途**：`zotero_client.py` 直写你自己的 Zotero 库，批量修正条目字段（类型切换、卷期页修正等），并在写入后回读断言。

**怎么配**：先跑 `python .claude/doctor.py --configure`，按提示粘贴 key；doctor 会用 `/keys/current` 自动查出 userID 并一起保存。也可以按 [`KEY_SETUP.md`](KEY_SETUP.md) 手动配。

**验证**：

```bash
python .claude/skills/survey-ops/scripts/zotero_client.py smoke
```

它建一个临时条目、读回来、再删掉。通了再动真数据。

> **安全提醒**：这个 key 能改写你的整库。建 key 时只给需要的 library，权限勾 **Read/Write**。不要用别人的 key，也不要把 key 提交到 git。

### 4.6 AMiner token（可选）

**用途**：`aminer_search.py` 在 Crossref 查不到时（无 DOI 的中文文献、老会议论文）做存在性核验。

**怎么配**：先跑 `python .claude/doctor.py --configure`，按提示粘贴 token；doctor 会立即验证一次。手动取 token 的步骤见 [`KEY_SETUP.md`](KEY_SETUP.md)。

**注意**：这是你 aminer.cn 账号的**会话凭证**，会过期。过期后 doctor 会报 HTTP 401/403，重新取一次即可。它等同于密码级别，不要外传。

### 4.7 网络与代理（必须）

**用途**：Crossref 和 arXiv 是免费公开接口，不需要 key，但需要能访问。

**验证**：`doctor.py` 的「网络与接口」段会分别探测 Crossref、arXiv；配了 AMiner/Zotero key 时也会探测对应接口。

**公司网络 / 代理**：如果浏览器能打开而脚本不能，通常是代理只配在浏览器里。给终端也配上：

```powershell
$env:HTTPS_PROXY = "http://你的代理地址:端口"
```

```bash
export HTTPS_PROXY="http://你的代理地址:端口"
```

doctor 会显示检测到的代理变量，方便排查。

### 4.8 邮箱 Alert + IMAP 授权码（可选）

**用途**：把数据库的**保存检索 / Alert** 接进项目。每天定时拉 Alert 邮件 → 解析题录 → 题名补 DOI 与摘要 → 和台账、正文、历史简报对重 → 生成中文候选简报。**有新文献才出声，没新增就安静**。

它不是台账：简报只回答「这篇值不值得看、以什么角色看、下一步做什么」。要把候选写进正文，仍走「写作卷定强度 → 体系卷取全文入账 → 写作卷落笔」的固定顺序。

**第 0 步：在数据库里建好 Alert，并确认邮箱能收**

先在 Web of Science / Scopus / PubMed / 期刊网站把检索式保存成 Alert。以 Web of Science 为例：

1. 跑一次检索，确认结果就是你要跟踪的范围；
2. 点 **Save search / 保存检索**，再选 **Create alert / 创建提醒**；
3. 频率选 **Daily / 每天**，邮件格式选 **Full Record / 完整记录**（不要只选题名，否则解析不出题录）；
4. 填收信邮箱，保存后等一封测试邮件。

Scopus、PubMed、期刊网站也有类似入口。本文的解析器目前按 Web of Science 的 `full-record` 邮件模板写；换库前先看一封样本邮件（见本节末尾「已知限制」）。

**第 1 步：开启邮箱 IMAP，拿到客户端授权码**

脚本用的是 **IMAP + 用户名 + 客户端授权码**，不是网页登录密码。常见邮箱：

| 邮箱 | 开启 IMAP | 生成授权码 | 服务器 |
|---|---|---|---|
| QQ | 设置 → 账号 → POP3/IMAP → 开启 IMAP | 同一页生成授权码 | `imap.qq.com:993` |
| Gmail | 设置 → 转发和 POP/IMAP → 启用 IMAP | Google 账号 → 安全性 → 两步验证 → 应用专用密码 | `imap.gmail.com:993` |
| Outlook / Microsoft 365 | 账户安全 → 高级安全选项 | 应用密码（需先开两步验证） | `outlook.office365.com:993` |

注意：

- 授权码通常只显示一次，复制下来填进 `config.json`；丢了就重新生成。
- 组织/学校邮箱可能被管理员关闭 IMAP，或只允许 OAuth 现代认证；这种邮箱本脚本连不上，换 QQ / Gmail 等支持「用户名 + 授权码」的邮箱。
- Gmail 的垃圾箱 IMAP 名通常是 `[Gmail]/Spam`，不是 `Junk`；不确定时先把 `folders` 只留 `["INBOX"]`。

**第 2 步：初始化工作目录**（在综述项目根目录）

```powershell
python .claude/skills/survey-ops/scripts/daily/init_daily.py --workdir ./daily
```

```bash
python3 .claude/skills/survey-ops/scripts/daily/init_daily.py --workdir ./daily
```

装了合并包 `survey-manager` 的，把路径里的 `survey-ops` 换成 `survey-manager`。脚本会建 `daily/` 目录、复制拉信/解析/补全/调度脚本、生成 `config.json` 占位与 `CLAUDE.md` 分诊模板、写 `.gitignore`。重复运行只刷新脚本，不覆盖已有配置与分诊口径。

**第 3 步：填 `daily/config.json`**

| 字段 | 填什么 | 说明 |
|---|---|---|
| `imap_server` / `imap_port` | IMAP 地址与端口 | QQ：`imap.qq.com:993`；Gmail：`imap.gmail.com:993` |
| `use_ssl` | `true` | 目前固定走 SSL |
| `email` | 收信邮箱**完整地址** | 不要只写域名 |
| `auth_code` | 邮箱**客户端授权码** | 不是登录密码；QQ 在「设置 → 账户 → POP3/IMAP」生成 |
| `from_filter` | Alert 发件人完整地址 | 如 `alerts-noreply@clarivate.com` |
| `match_domain` | 发件人域名 | 兜住数据库换发信地址；QQ IMAP 不支持服务端域名检索，脚本在客户端过滤 |
| `folders` | 扫描的文件夹 | 默认 `["INBOX", "Junk"]`，垃圾箱也扫 |
| `ledger_path` | 台账路径 | 留空用项目根目录下的 `bib/verified.md`；相对路径以项目根目录为基准 |
| `manuscript_globs` | 正文 glob 列表 | 留空用 `["manuscript/*.md", "docs/*.md"]` |

**`from_filter` / `match_domain` 怎么填？** 打开一封真实的 Alert 邮件，点开发件人，把完整地址整体填进 `from_filter`，把 `@` 后面的域名填进 `match_domain`。例如发件人是 `alerts-noreply@clarivate.com`，就填：

```json
"from_filter": "alerts-noreply@clarivate.com",
"match_domain": "clarivate.com"
```

两个字段至少填一个；脚本按「完全等于 `from_filter`」或「域名等于 `match_domain`」匹配，不会把所有邮件都拉进来。

一个最小可用的 `config.json` 长这样（**占位值必须换掉**；JSON 不能写注释，最后一项后面不能加逗号）：

```json
{
  "imap_server": "imap.qq.com",
  "imap_port": 993,
  "use_ssl": true,
  "email": "your-email@example.com",
  "auth_code": "【待填】邮箱客户端授权码",
  "from_filter": "alerts-noreply@clarivate.com",
  "match_domain": "clarivate.com",
  "folders": ["INBOX", "Junk"],
  "ledger_path": "",
  "manuscript_globs": ["manuscript/*.md", "docs/*.md"]
}
```

**第 4 步：检查配置（不会显示授权码）**

```powershell
cd daily
python check_config.py
python check_config.py --test-imap   # 可选：实际登录一次，确认授权码可用
```

`check_config.py` 只报字段名与格式问题，并检查 `.gitignore` 是否排除了 `config.json`。退出码 `2`＝还没填好，`3`＝IMAP 登录失败（授权码过期、IMAP 未开、网络不通等）。`--test-imap` 会联网，但不会打印授权码。

**第 5 步：改分诊口径**

`daily/CLAUDE.md` 是从模板生成的，**必须按项目改**：综述范围、纳入/排除判据、三类引用角色、五分钟三问、A/B/C/D 类型定义。模板保留了原工作版的硬纪律，不要删：证据上限（邮件 C、摘要 B、全文 A）、`probable` DOI 必须写「待核」、覆盖缺口必须声明、只分诊不入账。

**第 6 步：手动跑一遍**

```powershell
cd daily
python pull_mail.py           # 拉信
python parse_alerts.py        # 解析
python enrich_crossref.py     # 补 DOI/摘要并对重
```

正常会看到：

- `pull_mail.py`：`[SAVE]` 逐封落盘，最后 `[DONE] 落盘 N 封`；
- `parse_alerts.py`：`[PARSE] ...`，并在 `daily/inbox/` 生成 `_parsed.md`；
- `enrich_crossref.py`：逐条 `[matched]` / `[probable]` / `[unmatched]`，最后 `[ENRICH] ...` 并生成 `_enriched.md`。

**第一次跑可能拉取这个发件人以前的所有 Alert**，不只是今天的。脚本按 `Message-ID` 去重，不会重复处理已拉过的邮件，但首次可能一次落很多封。想先小范围试，可以：

1. 先在邮箱里把旧 Alert 移到别的文件夹，只留最近一两封；
2. 或把 `folders` 临时改成只含 `["INBOX"]`，并确认收件箱里没有积压；
3. 或先只跑 `check_config.py --test-imap` 确认能登录，再决定是否全量跑。

**第 7 步：建定时任务**

Windows（每天 09:00）：

```powershell
schtasks /Create /TN "Survey Daily Brief" /SC DAILY /ST 09:00 `
  /TR "powershell -ExecutionPolicy Bypass -File D:\my_survey\daily\run_daily.ps1" /F
```

macOS / Linux：

```cron
0 9 * * * "/path/to/project/daily/run_daily.sh"
```

调度脚本只给 Claude 四个工具（Read / Write / Glob / Grep），**不给 Bash、不给联网**；邮件正文即使藏了指令也执行不了命令。空提醒（解析 0 条）会归档后安静退出，不生成空简报。

定时任务能跑起来，还要求：

- 运行任务的账户已经安装并登录 **Claude Code**，`claude` 命令在 PATH 里；
- Windows 任务默认「仅当用户登录时运行」，电脑要开着并已登录该账户；可在任务属性里勾选「错过后尽快补跑」；
- 计划任务的 PATH 与终端不同。`run_daily.ps1` 会依次找 `SURVEY_DAILY_PYTHON`、`python`、`py -3`；都不行时在 `daily/logs/YYYY-MM-DD.log` 里报错。
- 第一次建议手动运行一次 `run_daily.ps1`，确认能生成 `daily/brief/YYYY-MM-DD.md`，再交给定时任务。

**安全**：`config.json` 含授权码，等同于邮箱密码。`.gitignore` 已排除它；不要贴进聊天、issue、commit 或报告。授权码在邮箱网页重新生成后旧码立即失效，回来改这里再跑一次 `check_config.py --test-imap`。

**边界与已知限制**：

- 只分诊，不写 `bib/verified.md`、不改正文、不宣称某文「已纳入」；
- Web of Science 的 Alert 邮件常只展示前 5 条，其余题名可一行一条粘到 `daily/manual/extra_titles.txt`，简报会声明覆盖缺口；
- `parse_alerts.py` 目前按 WOS 的 `full-record` 邮件模板解析；换 Scopus / PubMed / 期刊 Alert 前先看一封样本邮件，必要时改解析正则，不要盲跑；
- 核心脚本直接复制自原 `mail_daily` 工作版，逐项来源与改动见 `scripts/daily/SOURCE.md`；真实配置、历史邮件、简报与去重台账未随包分发。

**怎么接回主流程**：定时任务生成的是 `daily/brief/YYYY-MM-DD.md`。第二天在综述项目里打开 Claude Code，直接说：

```
读 daily/brief/2026-11-04.md，把 P0 第 2 条按流程纳入 3.2。
```

skill 会先由写作卷判断这句话要多强的证据，再由体系卷取全文、核著录、入台账，最后回写作卷落笔。**不要**让日报直接改正文或台账；它给的始终是候选。

**出问题先看哪里**：

| 现象 | 先查 | 处理 |
|---|---|---|
| `check_config.py` 报 `NOT READY` | 它列出的字段名 | 补 `config.json`；占位符不算填好 |
| `--test-imap` 退出码 3 | 报错类型 | 授权码过期、IMAP 未开、邮箱地址不完整、网络不通 |
| 登录成功但拉不到信 | `daily/logs/`、`from_filter` | 发件人地址/域名抄错，或 Alert 发到了垃圾箱 |
| 日志出现 `无法打开文件夹 Junk` | `folders` 名称 | Gmail 改 `[Gmail]/Spam`；不确定先只留 `["INBOX"]` |
| 解析 0 条 | 邮件格式 | 确认 Alert 选的是 Full Record；换库时先看样本邮件 |
| 定时任务没跑 | 任务计划程序历史 | 是否登录、`claude` 是否在 PATH |

完整说明见 [`skills/survey-ops/references/daily-lit.md`](skills/survey-ops/references/daily-lit.md)。

---

## 5. 第一次用：从一个模糊题目开始

下面是一条完整的真实使用路径。示例题目是「激光焊接过程监测」，换成你自己的方向即可。

范围收敛和章节总纲由 Claude Code 和你对话完成；提纲一旦确认，后面的检索、核验、记账、写作、核对都有明确规则和脚本兜着。

### 第 1 轮：把模糊题目收敛成范围

```
你：我想写一篇激光焊接过程监测的中文综述，投《机械工程学报》，1.5 万字左右。范围还没想好。
它：先确认三件事——读者是焊接工艺方向还是控制方向？要不要覆盖增材制造？时间窗近十年还是十五年？
你：工艺方向；覆盖增材；近十年。
它：给出章节总纲（6 章），标出每章要回答的问题和大致篇幅，等你确认。
```

这一步的产物是**章节总纲**，不是正文。你可以直接改：删一章、合并两章、调顺序，它会按你的意见重排。

### 第 2 轮：建文献库

```
你：就按这个总纲，先把第 3 章的文献收进来。
它：把第 3 章拆成若干检索方向 → Crossref 查 DOI 和书目、arXiv 查预印本、中文文献和无 DOI 老文献走 AMiner
   → 逐条核验 → 追加进 bib/verified.md，编号从当前最大号顺延
   → 交一份清单：新增多少、存疑多少、查无多少。
```

查不到的条目会标 `[待验证]`，不会编一个 DOI 糊过去。每条查询的原始返回落盘 `reports/_raw/`，以后可以复查。

> 第一次建库时台账是空的，所以这一步就是「从零建库」。之后每次补文献都走同一套核验流程，已有条目只读、不重验。
>
> 检索动作由 Claude Code 调用公开接口完成；skill 规定的是查什么、怎么验、怎么记账。

### 第 3 轮：搭章节骨架

```
你：第 3 章按「信号类型 → 特征提取 → 缺陷识别」这条线搭骨架。
它：给出段落提纲——每段一句论述指向、拟引用的台账编号、哪些位置需要新增文献
   → 你确认后才动笔。
```

段落提纲是这套流程的关键闸门。没有提纲就开写，最后一定会变成「文献罗列段」。

### 第 4 轮：填血肉

```
你：按提纲写 3.2。
它：从本节证据池取文献 → 用【作者 年份】占位写 → 做删引测试 → 把占位替换成 [n]
   → 交本节引用明细表：每条文献的占位、台账编号、支撑哪句话、A/B/C 依据等级。
```

写作过程中，每条引用先写占位、不写编号。编号在整节定稿后统一挂，避免中途增删导致全文编号漂移。

### 第 5 轮：自检

```
你：核一下 3.2，哪几条撑不住「主流」这个说法。
它：把「主流」这类中/强论断逐条对回原文和证据等级；
   撑不住的给出两条路：补证，或把措辞降级。不会直接放行。
```

每一轮的产物都落盘。换会话、换机器、隔一周回来，都能从台账、提纲和进度板接着做。

---

## 6. 日常怎么用：按任务查

| 你想做的事 | 可以直接说 | 它会走哪里 |
|---|---|---|
| 新开一篇综述 | 「我想写一篇 XX 的综述，帮我把范围理出来」 | 写作卷：收敛范围 → 章节总纲 |
| 给已有稿补一章 | 「补第 5 章，主题是 XX」 | 写作卷出提纲 → 体系卷建库 → 写作卷落笔 |
| 查一条文献是否真实 | 「这篇文献是真的吗：<标题/DOI>」 | 体系卷：Crossref → arXiv → AMiner |
| 补一篇文献并写进正文 | 「补一篇关于 XX 的文献，写进 4.2」 | 写作卷定强度 → 体系卷取证 → 写作卷落笔（顺序不可倒） |
| 改一段、润色 | 「把 3.2 第二段改清楚一点」 | 写作卷：先指问题，再给修改稿 |
| 看全文引用有没有漏 | 「核一下全文的引用覆盖」 | 体系卷：`cite_coverage.py` |
| 判断引文撑不撑得住 | 「这条引文原文到底怎么说的」 | 写作卷 §4.2 → 体系卷 §7.4 取全文 |
| 文献库周维护 | 「把这周新增的文献整理入库」 | 体系卷：台账 diff、去重、补字段、编号顺延 |
| 接每日 Alert | 「把每天的 WOS 提醒接进来，自动分诊」 | 体系卷 §16 + `references/daily-lit.md`；先用 `init_daily.py` 初始化 |
| 看今天有什么新文献 | 「读一下今天的简报」 | 读 `daily/brief/YYYY-MM-DD.md`；候选入正文仍走取证流程 |
| 批量修 Zotero | 「Zotero 里会议论文类型错了，批量改」 | 体系卷 §10：写入 + 回读断言 |
| 调整章节结构 | 「把第 4 章并进第 3 章」 | 写作卷 §9：冲击扫描 → 返工清单 |
| 让 skill 自己变强 | 「演进 skill」 | 两卷各自的演进通道：病例 → 新条文 |

### 唯一必须按固定顺序走的混合任务

「补一篇文献并写进来」同时涉及写和查，顺序不能倒：

1. **写作卷先定强度**——把将被支撑的那句话逐字写出来，判断是弱／中／强／最高论断。
2. **体系卷再取证**——先看有没有全文，再验著录、入台账、顺延编号。
3. **写作卷最后落笔**——按拿回的编号、等级和限定词写，不得外推。

跳过第 1 步，体系卷不知道该找什么等级的证据；跳过第 3 步的限定词，文献结论就会被写过头。这是同一批引文反复返工的最常见原因。

---

## 7. 它拦什么：质量闸门

这套 skill 的价值不在「能写」，而在**每个关键位置都有明确的拦截标准**。

| 闸门 | 什么时候拦 | 拦什么 |
|---|---|---|
| **论断强度** | 每次配引文 | 「这方法已成主流」属中／强论断，要 2 至 3 篇支撑；只挂一篇就要求改措辞 |
| **忠实性核对 A/B/C** | 引文要撑中／强论断时 | 只有摘要算 B 级，不得撑强论断；B 级必须先取全文、摘出关键句才能升 A |
| **引用覆盖** | 参考文献表定稿后 | 正文漏引、区间引用被误判成漏引；阴性结论必须回读原句才能写 |
| **概念纪律** | 概念首次出现、改名、精化 | 同义漂移、首现不定义、定义提前透支后文内容 |
| **段落结构** | 每段写完、结构改动后 | 中心句空转、结论超出前文、例子淹没判断、强主张没有边界 |
| **句法可读性** | 随结构体检同步 | 伪主语、名词化堆叠、逻辑算子叠用、冗余复述、该有的主语或动作缺失 |
| **编号双轨** | 引用集有任何变动 | 正文 [n] 与台账编号各自独立，任何一方禁止重编号；变动走 diff 报告 |
| **落盘对账** | 每次查询、每次改正文前 | 原始返回不落盘不算完成；改动前先备份到 `reports/_raw/` |

它不是靠「感觉」判断，能机械检查的都落成了脚本：

```bash
# 正文引用覆盖
python .claude/skills/survey-ops/scripts/cite_coverage.py 正文.md -m "# 参考文献"

# 忠实性证据行校验
python .claude/skills/survey-ops/scripts/faithfulness_check.py 证据表.md -c 正文.md
```

两个脚本都以退出码说话：`0` 才算过。校验器只报违规，不改判——最终判断仍然在你。

### 忠实性核对到底怎么分级

单位是**引用位置**，不是文献。同一篇文献在不同位置的等级可以不同。

| 等级 | 现状 | 下一步动作 | 完成标志 |
|---|---|---|---|
| A | 已对照本地原文核实过这个位置 | 不重核，只做失效检查 | 转述没改就维持；改过就降 B |
| B | 只有摘要或出版方页面 | 先取全文，再核支撑该句的那段原文 | 摘到原文关键句 → 升 A |
| C | 只有题名或书目元数据 | 先补证，还谈不上核对 | 取到摘要 → 转 B；取不到不得独立承担论断 |

核对结论必须落成证据行（正文位置／论断原文／强度／原文关键句／原等级→新等级），否则视为未核对。

---

## 8. 密钥与安全

**本仓库不含任何密钥**，`.env.example` 里只有占位符。关于「要不要大模型 API key」，分三层：

1. **本包自身不需要模型 key。** 包里全是条文和 Python 脚本，没有任何一处调用大模型 API，所以没有 `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` 这类配置项。
2. **模型由你使用的 agent 提供，用你自己的账号与额度。** 认证走 Claude Code（或别的 agent）自己的登录／密钥体系，与本仓库无关，本仓库也无从读取。
3. **脚本只需要两个可选的外部文献服务凭证**，不给也不影响其余功能：

| 变量 | 何时需要 | 不给会怎样 |
|---|---|---|
| `AMINER_API_KEY` | 跑 `aminer_search.py`（中文文献、无 DOI 老文献） | 该脚本报错退出；Crossref / arXiv 两层照常可用 |
| `ZOTERO_USER_ID` + `ZOTERO_API_KEY` | 跑 `zotero_client.py`（Zotero 直写通道） | 该脚本报错退出；skill 其余部分不受影响 |

一律走环境变量：脚本不读 `.env` 文件，也不得硬编码 key。填法见 [`KEY_SETUP.md`](KEY_SETUP.md)，或直接跑 `python .claude/doctor.py --configure`。

**唯一例外：每日监控的邮箱授权码。** 它必须放在本机 `daily/config.json`，不能走环境变量（定时任务与手动运行都要读同一份配置）。因此：

- `init_daily.py` 会写 `daily/.gitignore`，把 `config.json`、`inbox/`、`processed/`、`logs/`、`state/` 排除；
- `check_config.py` 会检查这条排除规则是否存在；
- 任何时候都不要把 `config.json` 的内容贴进聊天、issue、commit 或报告。提交前看一眼 `git status`，确认它没被 `git add`。

**不要把 key 写进** `CLAUDE.md`、脚本注释、报告、聊天记录、issue、PR、commit message。`.gitignore` 已排除 `.env`、`*.env`、`*.key`、`*.token`，但**不要依赖它**——提交前还是看一眼 `git status`。

---

## 9. 包内结构与你该建的项目

### 9.1 包内结构

```
install.ps1 / install.sh                 一键安装（Windows / macOS·Linux）
tools/
├── doctor.py                            环境体检 + 自动安装 + 交互式配置密钥
└── convert.cmd                          docx → markdown（pandoc）
KEY_SETUP.md                             密钥申请与填写明细
skills/
├── survey-writing/                      写作卷（学术判断）
│   ├── SKILL.md                         §0–§6、§9、§11–§14
│   ├── references/
│   │   ├── citation_style_notes.md      著录转换规则
│   │   └── 14_mechanism.md              §14 条文演进工序全文
│   └── templates/section_workflow.md        章节五步循环模板
├── survey-ops/                          体系卷（机械运转）
│   ├── SKILL.md                         §6A、§7、§8、§10、§15、§16（每日 Alert）
│   ├── references/daily-lit.md          每日监控完整说明
│   ├── templates/
│   │   ├── daily_config.example.json    config.json 占位模板
│   │   └── daily_triage.md              分诊口径模板（生成 daily/CLAUDE.md）
│   └── scripts/
│       ├── verify_round1.py             存在性核验：Crossref DOI + 书目 + arXiv
│       ├── aminer_search.py             AMiner 层（需 AMINER_API_KEY）
│       ├── arxiv_curl.py                arXiv API 的 curl 兜底（urllib 被 406 时）
│       ├── cite_coverage.py             正文引用覆盖核对（写作卷 §4.1）
│       ├── faithfulness_check.py        忠实性核对证据行校验（写作卷 §4.2）
│       ├── zotero_client.py             Zotero Web API 直写通道（体系卷 §10）
│       └── daily/                       每日 Alert 监控
│           ├── init_daily.py            初始化 daily/ 工作目录
│           ├── check_config.py          只读配置体检（不显示授权码）
│           ├── pull_mail.py             IMAP 拉 Alert（UID + Message-ID 去重）
│           ├── parse_alerts.py          WOS Alert HTML → _parsed.md
│           ├── enrich_crossref.py       题名→DOI→摘要，并与台账/正文对重
│           ├── run_daily.ps1 / .sh      每日总调度
│           ├── check_alert_links.py     只读诊断：邮件里到底有几条
│           ├── uid_gaps.py              只读诊断：邮箱 UID 空洞
│           └── SOURCE.md                与原 mail_daily 工作版的逐项对照
└── _shared/handoff.md                   两卷交接契约
```

安装后，`doctor.py` 和 `KEY_SETUP.md` 会各复制一份到 `<项目>/.claude/`（用户级安装则是 `~/.claude/`），所以装完不必再回到仓库目录也能体检和配置。

节号沿用分卷前的编号，不重排——历史记录里的 § 引用照原号读即可。

### 9.2 你的综述项目长什么样

脚本默认按这套骨架读写，安装时已自动建好：

```
manuscript/      正文
pdfs/            本地全文，忠实性核对用
bib/verified.md  文献台账：只增不改、编号顺延
docs/            progress.md（安装时建）；claims.md、concepts.md 随写作建立
reports/         回执与报告
reports/_raw/    接口原始返回、改动前备份
daily/           每日 Alert 监控工作目录（可选；config.json 含授权码，禁止提交）
```

这三样是它的「记忆」：

- `bib/verified.md`：文献台账。每条文献一行，编号只增不改。
- `docs/progress.md`：进度板。哪节写完了、哪节有遗留。
- `docs/concepts.md`：概念台账。规范名、定义位置、复用章节。

换会话不会失忆，靠的就是这些落盘文件。

---

## 10. 常见问题（FAQ）

### 安装 / 环境

**Q：`python` 不是内部或外部命令，也不是可运行的程序？**

A：Python 没装或没进 PATH。Windows 可以重跑安装脚本并加 `-AutoInstall`，或到 python.org 安装时勾选 **Add Python to PATH**。macOS/Linux 试 `python3`。装完**重开终端**再试。

**Q：公司电脑不让装软件 / 没有管理员权限？**

A：Skill 条文本身不需要管理员权限，只有安装 Python、pandoc、Zotero 时需要。可以：
- 用便携版 Python（解压即用）；
- 让 IT 装 Python；
- 只用写作卷的条文（不跑脚本），此时不需要 pandoc、Zotero、AMiner。

**Q：公司网络需要代理，脚本连不上 Crossref / arXiv？**

A：给终端也配上代理（见 §4.7）。如果代理需要认证，把用户名密码写进代理 URL。doctor 的「网络与接口」段会告诉你哪个接口不通。

**Q：安装脚本跑完，提示「当前目录是本仓库自身，跳过骨架」？**

A：这是正常的保护：你直接在 clone 里跑了脚本，它不想把干净的仓库弄脏。到你的项目目录里重跑，并带上 `-ProjectRoot` / 项目目录参数。

### 密钥

**Q：我必须配 AMiner 和 Zotero 吗？**

A：不必须。只做「读文献、核论断、写正文」时，Crossref + arXiv 够用。只有要查中文/无 DOI 老文献（AMiner）或批量修正 Zotero 条目（Zotero API）时才配。

**Q：`--configure` 会把密钥写到哪里？**

A：Windows 写当前用户的用户环境变量（`HKCU\Environment`）；macOS/Linux 写 shell 启动文件里的一个受管区块（如 `~/.zshrc`），写前自动备份。不会写进仓库，也不会写进 `.env`。重开终端或重启 Claude Code 后生效。

**Q：AMiner 报 401/403？**

A：token 过期了。重新登录 aminer.cn，按 `KEY_SETUP.md` 取一次新的，再跑 `--configure`。

**Q：Zotero key 显示「写权限：无」？**

A：建 key 时只勾了读。到 [zotero.org/settings/keys](https://www.zotero.org/settings/keys) 重建一个，勾 **Allow library access → Read/Write**。

**Q：Zotero 本地 API 返回 403？**

A：桌面版在运行，但本地 API 没开。这个接口是可选的：Web API 和 `zotero_client.py` 不受影响。要用本地 API 时，在 Zotero 设置里允许本地访问，或升级到支持写入的版本。

**Q：`zotero_client.py smoke` 安全吗？**

A：它只建一个标题为 `SMOKE_TEST` 的临时条目、读回来、再删掉，不碰你的真实文献。但它确实会写库，所以第一次跑之前确认 key 指向的是你自己的库（doctor 会检查 userID 一致性）。

**Q：`--configure` 说保存成功了，但 Claude Code 里脚本还报 `missing env`？**

A：环境变量是**进程启动时**继承的。完全退出 Claude Code（不是只关窗口），再从**新开的终端**里启动。macOS 上从 Dock/Spotlight 启动的 GUI 应用可能不读 `~/.zshrc`，建议在终端里运行 `claude`。Windows 同理：设置用户环境变量后，已开的终端和 Claude Code 都要重开。

### 使用

**Q：它会不会替我编文献？**

A：不会。查不到就标 `[待验证]`，绝不伪造 DOI、卷号、页码。你可以在 `bib/verified.md` 里看到每条文献的核验依据。

**Q：它会不会改我的正文？**

A：体系卷不会自行改正文；正文改动由写作卷做，且改动前会先备份到 `reports/_raw/`。结构改动会先出返工清单交你分诊。

**Q：我该说「帮我写第 3 节」还是「帮我核第 3 节」？**

A：都可以，说人话就行。规范会按「读起来站不站得住 / 对账对不对得上」分流。判不准时它会反问你。

**Q：写了一半换电脑 / 隔一个月回来，还能接上吗？**

A：能。台账、进度板、概念台账、当前提纲都在项目目录里；新机器上重装 skill 并跑一次 `doctor.py` 即可。

**Q：我把仓库删了，装在项目里的 skill 还能用吗？**

A：能。skill 已经复制到 `<项目>/.claude/skills/`；`doctor.py` 和 `KEY_SETUP.md` 也复制到了 `.claude/`。只有想更新 skill 版本时才需要重新 clone。

### 每日 Alert

**Q：每日简报会不会直接把新文献写进台账或正文？**

A：不会。日报只做分诊，输出的是候选清单，证据上限最多 B 级（邮件本身 C 级）。要写进正文，按「写作卷定强度 → 体系卷取全文、核著录、入台账 → 写作卷落笔」走；跳过取证直接写，等于用 C 级证据撑论断。

**Q：WOS 邮件只展示 5 条，其余文献怎么办？**

A：Web of Science 的 Alert 模板固定只带 5 条，「View all」页面匿名取不到其余记录。两条路：① 点开「View all N records」，把其余题名一行一条粘到 `daily/manual/extra_titles.txt`（约 1 分钟），下一轮会合并并按题名补 DOI；② 把 Alert 改成每日提醒，单批新增通常不超过 5 条。无论哪种，简报都会声明覆盖缺口。

**Q：`check_config.py` 说 `NOT READY`，但字段我都填了？**

A：看它列出的字段名。占位符 `【待填】`、`your-email@example.com` 不算填好；`email` 必须写完整地址；`from_filter` 与 `match_domain` 至少填一个。填完重跑；要确认授权码本身可用，加 `--test-imap`。

**Q：授权码会不会被提交到 git？**

A：`init_daily.py` 会在 `daily/` 下写 `.gitignore` 排除 `config.json`、`inbox/`、`processed/`、`logs/`、`state/`，`check_config.py` 也会检查这条规则。但不要只依赖 `.gitignore`——提交前看一眼 `git status`。授权码等同于邮箱密码，不要贴进聊天、issue 或报告。

---

## 11. 病例、演进与依赖

### 11.1 关于病例

写作卷 §0 有条元规则：**新条文只能由已确诊病例逼出**。快照版每条只保留一行匿名摘要作为线索，病例原文不在本包内。用起来之后请在自己的项目里重建病例档案（建议 `reports/cases/`），否则条文会慢慢失去自检能力。

积累到一定数量后说「演进 skill」，两卷会分别把病例转成新条文——用得越久，它越贴合你的项目。

### 11.2 依赖与更新

- Python 3.8+，仅标准库
- pandoc（`tools/convert.cmd` 用）、curl（`arxiv_curl.py` 用），都非必需
- Zotero 桌面版（本地全文，推荐）、Zotero Web API（直写，可选）、AMiner（中文/无 DOI 核验，可选）
- 邮箱 IMAP + 客户端授权码（每日 Alert 监控，可选）；`parse_alerts.py` 目前按 Web of Science 邮件模板解析
- 网络：Crossref、arXiv（必需）；OpenAlex（每日监控补摘要，可选）、AMiner、Zotero API（配了才需要）

本包是**节点快照**，不跟上游自动同步。需要新条文时，按写作卷 §0 在你自己的项目里长出来，再决定是否回灌本仓库。

---

**装完还有问题？** 先跑 `python .claude/doctor.py`，把报告里的 `[X]` / `[!]` 对照 §3 处理一遍；大部分问题在那一页就有答案。
