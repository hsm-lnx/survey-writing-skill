# 每日监控脚本来源对照

本目录的核心脚本来自 `mail_daily/`（2026-10-24 工作版），不是另起炉灶重写。下表逐项列出复制关系与唯一改动，便于核对。

| 本目录文件 | 来源 | 改动 |
|---|---|---|
| `pull_mail.py` | `mail_daily/pull_mail.py` | 仅增加 `config.json` 缺失/JSON 非法的友好报错；`inbox_dir` 留空时默认 `./inbox`；占位检查增加“待填”。IMAP 流程、UID SEARCH/FETCH、`BODY.PEEK`、Message-ID 去重、退出码 2/3 全部保留。 |
| `parse_alerts.py` | `mail_daily/parse_alerts.py` | **逐字节相同**。 |
| `enrich_crossref.py` | `mail_daily/enrich_crossref.py` | 仅把硬编码的 `../bib/verified.md`、`../docs/正文草稿_v6.3-coherent.md` 改成默认值＋`config.json` 覆盖（`ledger_path`、`manuscript_globs`）；题名→DOI、相似度阈值、OpenAlex 摘要兜底、四路对重、退出码全保留。 |
| `run_daily.ps1` | `mail_daily/run_daily.ps1` | 仅把硬编码的 `mail_daily/` 改为 `$PSScriptRoot`（可用 `-WorkDir` 覆盖）；Python 定位增加 `SURVEY_DAILY_PYTHON`、`python`、`py -3`；其余步骤顺序、空提醒退出码 4、Claude 受限工具集、归档逻辑不变。 |
| `check_alert_links.py` | `mail_daily/state/check_alert_links.py` | 去掉硬编码 `.eml` 路径，改为命令行参数或自动取 `inbox/`、`processed/` 最新邮件。 |
| `uid_gaps.py` | `mail_daily/state/uid_gaps.py` | 去掉硬编码 `mail_daily/`，改为脚本所在目录；增加 `--folder`。 |
| `run_daily.sh` | 新增 | macOS/Linux 端口，流程与 `run_daily.ps1` 一致。 |
| `init_daily.py` | 新增 | 产品化初始化：建目录、复制脚本、生成占位配置与分诊模板、写 `.gitignore`。 |

## 没有复制的内容

- `config.json`：含真实邮箱地址与 IMAP 授权码，**未复制、未打印、未提交**。包内只有 `templates/daily_config.example.json` 占位。
- `inbox/`、`processed/`、`brief/`、`logs/`、`state/`：历史邮件、简报与去重台账，属于本地运行数据，未复制。
- `probe*.py`、`state/probe_wos_*.py`：一次性探测脚本，不属于日常流程，未复制。
- `README.md`：其中的配置说明已并入 `references/daily-lit.md`，并去掉真实邮箱地址。

## 分诊规则

`templates/daily_triage.md` 按 `mail_daily/CLAUDE.md` 的结构脱敏：保留输入优先级、三类引用角色、硬门槛、五分钟三问、证据上限、四处去重、简报格式与空简报纪律；只把焊接项目专属的表号、计数、具体文件名和截止日换成【待填】。原始工作版仍在 `mail_daily/CLAUDE.md`，未随包分发。
