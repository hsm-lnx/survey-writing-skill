# 密钥接入明细

本包**不含任何密钥**；包内脚本也不调用大模型 API，因此**本包不需要配模型 key**——你运行 skill 所用的 agent（如 Claude Code）用你自己的登录／密钥，与本仓库无关。本包需要你自备的只有两个**可选**的外部文献服务凭证。

这里只讲四件事：要哪些、怎么申请、怎么接进来且不泄露、出问题怎么查。

---

## 0. 最快路径：让体检脚本带你配

不用手工敲环境变量。在项目目录里运行（`doctor.py` 在仓库里是 `tools/doctor.py`，装完后是 `.claude/doctor.py`）：

```powershell
python .claude\doctor.py --configure
```

```bash
python3 .claude/doctor.py --configure
```

它会：

1. 逐项问你要不要配置 AMiner / Zotero；
2. 输入时不回显，粘贴即可；
3. 立即用只读接口验证 key 是否有效；
4. 对 Zotero，用 key 自动查出 `ZOTERO_USER_ID`，不用你手填；
5. 写进你的**用户级**环境变量（Windows `HKCU\Environment`；macOS/Linux 的 shell 启动文件受管区块），写前自动备份。

配置完**重开终端**（或重启 Claude Code）让环境变量生效。然后跑一次：

```bash
python .claude/doctor.py
```

看到 `[OK] AMINER_API_KEY` / `[OK] Zotero Web API` 就算接好了。

> 不想用交互脚本，或脚本写不进去（比如受管公司电脑），按下面的手工步骤做。

---

## 1. `AMINER_API_KEY` — 文献核验的 AMiner 层

**用途**：`aminer_search.py`。当 Crossref 查不到（无 DOI 的中文文献、老会议论文）时，用 AMiner 的检索网关做存在性核验。

**免费**：是。

**怎么拿**：

1. 注册/登录 [aminer.cn](https://www.aminer.cn)。
2. 在站内做任意一次文献搜索，打开浏览器开发者工具 → Network。
3. 找发往 `searchtest.aminer.cn/aminer-search/search/publicationV2` 的请求。
4. 复制请求头 `Authorization` 里 `Bearer ` 后面的那串。这就是 `AMINER_API_KEY` 的值。

**注意**：

- 这是**你自己账号的会话凭证**，会过期。过期后现象是 401/403，重新取一次即可。
- 它代表你的账号身份，等同于密码级别的东西。**不要外传、不要写进任何会被提交的文件。**
- 开放平台旧域名的公开申请通道已不可用，不要去找「申请 API key」的页面。
- 不需要安装任何 AMiner 客户端；它只是一个网页账号 + 请求头里的 token。

**不给的后果**：`aminer_search.py` 直接报错退出。`verify_round1.py`（Crossref + arXiv）不依赖它，照常可用。

**怎么验证**：

```bash
python .claude/doctor.py
```

看 `[OK] AMiner：token 可用，接口返回正常`。也可以直接跑一次 `aminer_search.py`（需要 entries.json）。

---

## 2. `ZOTERO_USER_ID` + `ZOTERO_API_KEY` — Zotero 直写通道（可选）

**用途**：`zotero_client.py`，对应 SKILL.md §10。用来批量修正自己的 Zotero 条目字段（类型切换、卷期页修正等），并做写入后回读断言。

**需要装 Zotero 桌面版吗？**

- 只做 **Web API 直写**：不需要桌面版，有 Zotero 网页账号和 API key 即可。
- 还要用 **本地 PDF 全文**（§7.4 的两处查找）：需要 Zotero 桌面版，并且本机有数据目录。
- 还要用 **Zotero 10+ 本地 API**：需要桌面版并开启本地访问。

**免费**：是（Zotero 账号自带）。

**怎么拿**：

1. 登录 [zotero.org](https://www.zotero.org)，进 [Settings → Keys](https://www.zotero.org/settings/keys)。
2. 页面上方有一行 **"Your userID for use in API calls is 1234567"** —— 这就是 `ZOTERO_USER_ID`。
3. 点 **Create new private key**：
   - Key permissions：勾选 **Allow library access** → **Read/Write**
   - 按需限定到具体 library / collection
4. 生成后立即复制 key（只显示一次），这就是 `ZOTERO_API_KEY`。

**注意**：

- 这个 key **能改写你的整库**。用最小权限建，只给需要的 library。
- 建完先跑一次 `python .claude/skills/survey-ops/scripts/zotero_client.py smoke`：它建一个临时条目、读回来、再删掉。通了再动真数据。
- 本脚本**故意不设默认 userID**：旧版本曾把某个 ID 写成默认值，别的账号不配环境变量就会往那个人的库里写。现在缺变量直接报错退出。
- 如果 key 和 `ZOTERO_USER_ID` 不属于同一个账号，doctor 会报 `[X] ZOTERO_USER_ID 一致性`。别忽略——写错库比不写更糟。

**不给的后果**：`zotero_client.py` 报错退出。skill 其余部分（写作规范、Crossref/arXiv 核验、引用覆盖核对）完全不受影响。

**怎么验证**：

```bash
python .claude/doctor.py
python .claude/skills/survey-ops/scripts/zotero_client.py smoke
```

---

## 3. 大模型 API Key —— 本包不需要

这些脚本全走免费文献接口，**不调用任何 LLM API**。skill 本身是给 Claude Code 读的规则文件，模型由你的 Claude Code 客户端负责（登录态或客户端侧的 `ANTHROPIC_API_KEY`），与这个仓库无关。

如果你以后自己写脚本想调用大模型做辅助判断，按下面的通用做法接，**不要照抄成硬编码**：

```python
import os
key = os.environ["MY_LLM_API_KEY"]     # 缺失即报错，不给默认值
```

然后把变量名登记进 `KEY_SETUP.md`，值只写在你本机的环境里。

---

## 4. 手工设置环境变量

### Windows（PowerShell）

当前会话临时生效：

```powershell
$env:AMINER_API_KEY = "你的值"
$env:ZOTERO_USER_ID = "1234567"
$env:ZOTERO_API_KEY = "你的值"
```

永久生效（写用户级环境变量，**新开终端**后可用）：

```powershell
[Environment]::SetEnvironmentVariable("AMINER_API_KEY", "你的值", "User")
[Environment]::SetEnvironmentVariable("ZOTERO_USER_ID", "1234567", "User")
[Environment]::SetEnvironmentVariable("ZOTERO_API_KEY", "你的值", "User")
```

设置完验证（不要用 `echo` 把值打出来）：

```powershell
python .claude\doctor.py
```

### macOS / Linux

当前会话临时生效：

```bash
export AMINER_API_KEY="你的值"
export ZOTERO_USER_ID="1234567"
export ZOTERO_API_KEY="你的值"
```

永久生效：把上面三行写进你的 shell 启动文件：

- zsh（macOS 默认）：`~/.zshrc`
- bash：`~/.bashrc`（macOS 登录 shell 也可用 `~/.bash_profile`）
- fish：`~/.config/fish/config.fish`，语法是 `set -gx AMINER_API_KEY "你的值"`

改完执行 `source ~/.zshrc`（或重开终端）。

### 为什么不用 `.env`？

`.env.example` 只是**字段清单**，本包脚本不自动读取 `.env`。原因是：`.env` 太容易被误提交、被复制进项目、被截图。统一走系统环境变量，泄露面更小。如果你确实想用 `.env`，自己加加载逻辑，或直接用上面的系统环境变量。

---

## 5. 出问题怎么查

先跑：

```bash
python .claude/doctor.py
```

| 现象 | 多半原因 | 处理 |
|---|---|---|
| `[!] AMINER_API_KEY 未设置` | 没配，或配在了别的终端 | 重开终端；或跑 `--configure` |
| `AMiner：HTTP 401/403` | token 过期 | 重新从 aminer.cn 取一次 |
| `AMiner：连接超时` | 网络/代理 | 给终端配代理，见 README §4.7 |
| `[!] ZOTERO_API_KEY 未设置` | 没配 | 可选；要用时跑 `--configure` |
| `Zotero Web API：HTTP 401/403` | key 无效或被吊销 | 到 zotero.org/settings/keys 重建 |
| `Zotero Web API：写权限：无` | key 只给了读 | 重建 key，勾 Read/Write |
| `[X] ZOTERO_USER_ID 一致性` | userID 和 key 不属于同一账号 | 跑 `--configure`，让脚本自动推导 |
| `Zotero 本地 API：HTTP 403` | 桌面版本地 API 没开 | 可选；在 Zotero 设置里允许，或忽略 |
| `zotero_client.py` 报 `missing env` | 环境变量没进当前进程 | 重开终端/Claude Code；Windows 用 `[Environment]::GetEnvironmentVariable(...,"User")` 确认已持久化 |
| `--configure` 成功但 Claude Code 仍读不到 | 进程启动时没继承新变量 | 完全退出 Claude Code，从新终端启动；macOS 别从 Dock 启动 GUI 版 |

> 注意：`doctor.py` **不会**打印密钥的值，只报长度和来源。排查时也不要用 `echo $env:ZOTERO_API_KEY` 把值打到屏幕上。

---

## 6. 防泄露纪律

1. `.gitignore` 已排除 `.env`、`*.env`、`*.key`、`*.token`，但**不要依赖它**——先确认再加文件。
2. **提交前必做**：

   ```bash
   git status                 # 看清待提交清单
   git diff --cached | grep -iE "api[_-]?key|bearer|token|secret|password"
   ```

   有命中就 `git reset` 掉那个文件，先弄清它为什么进来了。
3. **不要**把 key 写进 `CLAUDE.md`、脚本注释、报告、聊天记录。
4. **不要**把 key 贴进 issue、PR、commit message。
5. 一旦误提交：**先吊销重签**（Zotero 删 key 重建 / AMiner 重新登录换 token），再处理 git 历史。只删文件不吊销是没用的——历史里还在。
6. 首次推送前如果已经有过误提交，用 `git log -p | grep -iE "api[_-]?key|bearer"` 全历史扫一遍。
