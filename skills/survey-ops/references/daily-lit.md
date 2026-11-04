# 每日文献 Alert 监控

管什么：把一个数据库的**保存检索 Alert** 接进项目，每天自动拉信、解析、补全著录、
去重、分诊，生成一份中文简报。它是**入口**，不是台账：简报只回答「这篇新文献值不值得看、
以什么角色看、下一步做什么」，纳入综述仍走主项目的全文核实与台账流程。

适合：

- 已在 Web of Science / Scopus / PubMed / 期刊网站建好保存检索或 Alert；
- 邮件能收到 Alert，且邮箱支持 IMAP（QQ、Gmail、Outlook 均可；需客户端授权码）；
- 想让「有新文献才出声，没新增就安静」；
- 不想每天手动刷数据库，也不想让模型直接改正文和台账。

不适合：

- 没有 Alert 邮件、只能网页检索的库；
- 想让脚本自动把新文献写进 `bib/verified.md` 的——本模块明确不做，防止未经全文核实的
  条目污染台账；
- 完全离线、无法访问 Crossref / OpenAlex 的机器（可退回只解析邮件，但著录补全会缺失）。

---

## 1. 工作目录

监控目录放在综述项目里，和正文、台账并列：

```
<综述项目>/
├── bib/verified.md           台账（本模块只读）
├── manuscript/ 或 docs/      正文（本模块只读，用于对重）
└── daily/                    监控工作目录
    ├── config.json           邮箱与路径配置（含授权码，禁止提交）
    ├── CLAUDE.md             分诊规则（由模板生成，必须按项目改口径）
    ├── check_config.py       只读配置体检（不显示授权码；可选实际登录测试）
    ├── pull_mail.py          拉信：IMAP UID SEARCH/FETCH，按 Message-ID 去重
    ├── parse_alerts.py       Alert HTML → _parsed.md
    ├── enrich_crossref.py    题名→DOI→著录/摘要，并与台账、正文、历史简报对重
    ├── run_daily.ps1         Windows 每日总调度
    ├── run_daily.sh          macOS/Linux 每日总调度
    ├── check_alert_links.py  只读诊断：邮件里到底有几条、View all 指向哪
    ├── uid_gaps.py           只读诊断：邮箱 UID 空洞
    ├── manual/extra_titles.txt  手工补充邮件未展示的题名
    ├── inbox/                待处理邮件与解析件
    ├── brief/YYYY-MM-DD.md   生成的中文简报
    ├── processed/YYYY-MM-DD/ 已处理邮件归档
    ├── logs/YYYY-MM-DD.log   每日运行日志
    └── state/                去重台账与 Crossref 原始返回
```

**所有路径以监控目录为基准。** `enrich_crossref.py` 默认到上一级找
`bib/verified.md` 与 `manuscript/*.md`、`docs/*.md`；可用 `config.json` 覆盖。

---

## 2. 初始化

> 第一次配置、不熟悉邮箱设置时，先看 README §4.8：里面有「在数据库建 Alert → 开启 IMAP → 拿授权码 → 找发件人 → 填完整 `config.json`」的逐屏步骤和示例。本节只列字段语义。

在综述项目根目录运行（把 `<skill>` 换成 `survey-ops` 或 `survey-manager` 的实际路径）：

```bash
python <skill>/scripts/daily/init_daily.py --workdir ./daily
```

它会建目录、复制脚本、生成 `config.json` 占位、生成 `CLAUDE.md` 分诊模板、写 `.gitignore`。
重复运行只刷新脚本，**不会覆盖已有的 `config.json` 与 `CLAUDE.md`**。

然后编辑 `daily/config.json`：

| 字段 | 填什么 | 说明 |
|---|---|---|
| `imap_server` / `imap_port` | 邮箱 IMAP 地址与端口 | QQ：`imap.qq.com:993`；Gmail：`imap.gmail.com:993` |
| `use_ssl` | `true` | 目前固定走 SSL |
| `email` | 收信邮箱完整地址 | 必须写完整地址，不要写域名 |
| `auth_code` | 邮箱**客户端授权码** | 不是登录密码；QQ 在「设置 → 账户 → POP3/IMAP」生成 |
| `from_filter` | Alert 发件人完整地址 | 例如 `alerts-noreply@clarivate.com` |
| `match_domain` | 发件人域名 | 用于兜住数据库换发信地址；QQ IMAP 不支持按域名服务端检索，脚本在客户端过滤 |
| `folders` | 扫描的文件夹 | 默认 `["INBOX", "Junk"]`，垃圾箱也扫；Gmail 垃圾箱通常叫 `[Gmail]/Spam`，不确定先只留 `INBOX` |
| `ledger_path` | 台账路径 | 留空用项目根目录下的 `bib/verified.md`；相对路径以项目根目录为基准 |
| `manuscript_globs` | 正文 glob 列表 | 留空用 `["manuscript/*.md", "docs/*.md"]`；只收 `.md` / `.txt` |

填完先跑只读体检（不会显示授权码）：

```bash
cd daily
python check_config.py
python check_config.py --test-imap   # 可选：实际登录一次，确认授权码可用
```

`check_config.py` 检查必填字段、占位符、端口/邮箱格式、`folders`/路径配置，以及
`.gitignore` 是否排除了 `config.json`。退出码 2 表示还没填好，3 表示 IMAP 登录失败。
`--test-imap` 会联网，无需等定时任务才发现授权码过期。

**安全**：`config.json` 含授权码，等同于邮箱密码。`.gitignore` 已把它排除；
不要把内容贴进聊天、issue、commit。授权码在邮箱网页重新生成后旧码立即失效，回来改这里。

---

## 3. 配置分诊口径

`daily/CLAUDE.md` 是从模板复制的，**必须改**。模板按原始工作版 `mail_daily/CLAUDE.md` 的结构脱敏，保留了完整的判据骨架；至少填五处：

1. **§2.1 主题交叉**：研究对象关键词、方法/应用关键词、时间窗。
2. **§2.2 三类引用角色**：核心实证、环境/感知组件、邻域参照各多少项（可写“现 N 项”）。
3. **§2.3 核心实证硬门槛**：什么算目标层级的实质决策，哪些轨迹级/检测级/综述类要排除。
4. **§2A 五分钟三问**：协议截止日、规则侧排除层级、发现侧判据。
5. **§3 类型与决策对象**：A/B/C/D 四类的项目定义。

模板保留了原始工作版的硬纪律，不要删：

- **证据上限**：邮件 C 级、补全摘要 B 级、全文才是 A 级；
- **`probable` DOI 必须写「待核」**，不得当作确定著录；
- **覆盖缺口必须声明**（Alert 邮件经常只展示前 5 条）；
- **三问前问成立即终止**，裁决只有三种落点，不得悬置；
- **只分诊、不入账、不改正文**。

脚本与原始工作版的逐项对照见 `scripts/daily/SOURCE.md`：`parse_alerts.py` 逐字节相同，其余核心脚本只改了配置路径与解释器定位；`config.json`、历史邮件、简报与去重台账未复制。

---

## 4. 手动跑一遍

```bash
cd daily
python check_config.py        # 配置体检；[OK] 后再往下
python pull_mail.py           # 拉信，看 [SAVE] / [DONE]
python parse_alerts.py        # 解析，看 [PARSE] 与 inbox/_parsed.md
python enrich_crossref.py     # 补全，看 [matched]/[unmatched] 与 inbox/_enriched.md
```

退出码约定：

| 退出码 | 来自 | 含义 | 调度脚本怎么处理 |
|---|---|---|---|
| 0 | 任一 | 正常 | 继续 |
| 2 | `pull_mail.py` | 配置缺失或授权码还是占位 | 报错退出，邮件不动 |
| 3 | `pull_mail.py` | 匹配邮件取正文失败 | 报错退出，邮件留在邮箱下次重试 |
| 4 | `parse_alerts.py` | 本轮 0 条（空提醒） | 归档邮件，安静退出，不调 Claude |
| 2 | `enrich_crossref.py` | 全部查询失败（断网） | 记警告，退回 `_parsed.md` 继续 |

拉信要点：

- **首次运行会拉取该发件人在扫描文件夹里的历史 Alert**，不只是当天。`Message-ID` 去重只防重复处理，不限制首次批量；想先小范围试，先把旧邮件移走，或临时把 `folders` 只留 `["INBOX"]`。
- 全流程用 `UID SEARCH` + `UID FETCH`，不用序列号。手机端删信会造成 UID 空洞，
  旧式「序列号当 UID」会永久漏信。
- 只读：用 `BODY.PEEK`，不标已读、不移动邮件。
- 按 `Message-ID` 持久去重（`state/seen_message_ids.json`），已归档邮件不会重复落盘。
- 取正文失败不写入 state，并以退出码 3 上报，不会静默当成「没有新邮件」。

---

## 5. 自动化

### Windows

```powershell
schtasks /Create /TN "Survey Daily Brief" /SC DAILY /ST 09:00 `
  /TR "powershell -ExecutionPolicy Bypass -File D:\my_survey\daily\run_daily.ps1" /F
```

- 任务默认「仅交互式登录」运行：电脑要开着并已登录该账户；可在任务属性里勾选
  「错过后尽快补跑」「电池供电也运行」。
- 计划任务的 PATH 与终端不同。`run_daily.ps1` 依次尝试 `SURVEY_DAILY_PYTHON` 环境变量、
  `python`、`py -3`、常见安装路径；都不行时在日志里报错。
- `run_daily.ps1` 存成 **UTF-8 带 BOM**。Windows PowerShell 5.1 读无 BOM 的 UTF-8
  会按 ANSI 解码，中文注释会让脚本解析失败。

### macOS / Linux

```bash
chmod +x /path/to/project/daily/run_daily.sh
```

```cron
0 9 * * * "/path/to/project/daily/run_daily.sh"
```

`run_daily.sh` 与 PowerShell 版流程一致；`claude` 必须在 PATH 里。

### 调度流程

```
pull_mail.py
  └─ 无新邮件 / 0 条空提醒 → 归档，安静退出
parse_alerts.py
  └─ 0 条（退出码 4） → 归档，安静退出
enrich_crossref.py
  └─ 断网（退出码 2） → 退回 _parsed.md 继续
claude -p（只给 Read/Write/Glob/Grep）
  └─ 生成 brief/YYYY-MM-DD.md；无新增则不生成
归档 inbox/、解析件、手工补充题名
```

**Claude 步骤只给四个工具，不给 Bash、不给联网。** 邮件正文即使藏了指令也执行不了命令。
改调度脚本时务必保留这个受限工具集。

---

## 6. 输出：简报与分诊结论

简报固定写到 `daily/brief/YYYY-MM-DD.md`，分 P0 / P1 / P2 三节，外加「已引/历史已报」
与「覆盖缺口」。每条记录至少给出：

- 题名、DOI（`probable` 写「候选 DOI，待核」）、作者、期刊/年份/卷期页；
- 类型（核心实证候选 / 组件支撑 / 邻域参照 / 不相关）；
- 三问结论（日期 / 规则 / 发现）与落点；
- 证据等级上限（C / B）；
- 与本综述的具体关系（章节、表、论点）；
- 建议动作与待核项。

**简报是候选清单，不是台账。** 要把某篇写进正文，按 `skills/_shared/handoff.md` 走：

1. 写作卷先定这句话要多强的证据；
2. 体系卷取全文、核著录、入台账、给编号与 A/B/C 等级；
3. 写作卷按回传的等级和限定词落笔。

跳过第 2 步直接把简报里的文献写进正文，等于用 C 级证据撑论断。

---

## 7. 去重与对重

`enrich_crossref.py` 会做四路对重，结果写进 `_enriched.md`：

| 对重对象 | 怎么判 | 命中后 |
|---|---|---|
| `processed/` 历史邮件 | 同一论文在历史批次出现过 | 不计新增 |
| `brief/` 历史简报 | DOI 或题名子串命中 | 标「历史简报：日期已出现（非新增）」 |
| 台账 `bib/verified.md` | DOI 精确优先，其次题名子串（≥25 字符） | 标「已引〔n〕」 |
| 正文 `manuscript_globs` | 题名归一化后子串命中 | 标「正文：题名已出现」 |

阈值纪律：

- 题名相似度 ≥0.97 记 `matched`；0.90–0.97 记 `probable`，只能写「待核」；
  <0.90 不采用。**宁可不匹配，也不能把 A 论文的 DOI 安到 B 论文上。**
- `probable` DOI 不得用于断定「已引」，按题名核。
- 题名只有部分词相同、不能确定同一篇时，标「疑似重复，待核」，不要强行合并。

---

## 8. Alert 只展示前 5 条怎么办

Web of Science 的结果邮件模板固定只带 5 条；「View all N records」指向登录后才能取数的
单页应用，匿名访问拿不到其余记录。两条路：

1. **手工补题名（推荐，约 1 分钟）**：点开「View all N records」，把其余题名一行一条
   粘到 `manual/extra_titles.txt`（`#` 开头为注释）。下一轮会与邮件记录合并，
   `enrich_crossref.py` 按题名补 DOI/摘要，简报覆盖行写「展示 B 条 + 手工补充 C 条」。
   运行成功后该文件归档到 `processed/<日期>/manual_extra_titles.txt`。
2. **提高 Alert 频率**：改为每日提醒，单批新增通常 ≤5 条；突发日仍需路径 1 兜底。

其他数据库（Scopus、PubMed、期刊 Alert）的邮件模板不同。`parse_alerts.py` 目前按
Web of Science 的 `full-record` 链接结构解析；换库时需要先看一封样本邮件，
必要时改 `RECORD_LINK_RE` 与字段抽取。**不要在不认识模板的情况下直接跑**，
否则可能把题名读错或漏条。

---

## 9. 故障排查

| 现象 | 先看 | 处理 |
|---|---|---|
| `check_config.py` 报 `NOT READY` | 它列出的字段名 | 按提示补 `config.json`；占位符 `【待填】` / `example.com` 不算填好 |
| `check_config.py --test-imap` 退出码 3 | 报错类型 | 授权码过期、IMAP 未开启、邮箱地址不完整或网络不通；不显示授权码 |
| 拉不到信 | `logs/<日期>.log`、`state/seen_message_ids.json` | 确认授权码未过期、IMAP 已开启、发件人域名匹配 |
| `[FAIL] UID n 取正文失败` | 退出码 3 | 邮件留在邮箱，下一轮重试；连续失败跑 `uid_gaps.py` |
| 解析出 0 条 | `python check_alert_links.py` | 看邮件里 `full-record` 数量、是否为空提醒、模板是否变了 |
| DOI 大量 `unmatched` | `_enriched.md` 的相似度 | Crossref 没有该文时正常；手工补题名时别把作者/期刊一起粘进去 |
| 摘要大量「未取到」 | 是否断网、OpenAlex 是否 429 | Crossref 常缺摘要；OpenAlex 限流时该条退化为无摘要，不编造 |
| 简报没生成 | 是否所有记录都已引/历史已报 | 符合空简报规则；不是失败 |
| 定时任务没跑 | 任务计划程序历史、是否登录 | 任务默认仅交互式登录；勾选「错过后尽快补跑」 |
| PowerShell 中文乱码/解析失败 | 文件是否 UTF-8 BOM | 用 `init_daily.py` 重新复制 `run_daily.ps1` |

诊断脚本都是只读的：

```bash
python check_alert_links.py [某封 .eml]
python uid_gaps.py --folder INBOX
```

---

## 10. 与主流程的边界

| 本模块做 | 本模块不做 |
|---|---|
| 拉 Alert 邮件、解析、补 DOI/摘要 | 把新文献写进 `bib/verified.md` |
| 与台账/正文/历史简报对重 | 修改正文、提纲、概念台账 |
| 给相关性、优先级、证据上限 | 宣称某文「已纳入」 |
| 生成候选简报 | 替代全文核实与 A/B/C 定级 |
| 提示「应落哪一处」 | 直接执行台账变更 |

这条边界是有意的：Alert 邮件最多给到 C 级证据，补全摘要最多 B 级。让日报直接入账，
等于把未经全文核实的条目混进台账，后面每一次引用都要返工。

需要把候选推进为正式引用时，按 `skills/_shared/handoff.md` 的「补文献请求 → 验证回执」
接口走，由写作卷先定论断强度，体系卷再取证入账。
