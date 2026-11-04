# 密钥接入明细

本包**不含任何密钥**；包内脚本也不调用大模型 API，因此**本包不需要配模型 key**——你运行 skill 所用的 agent（如 Claude Code）用你自己的登录／密钥，与本仓库无关。本包需要你自备的只有两个可选的外部文献服务凭证。

这里只讲三件事：要哪些、怎么申请、怎么接进来且不泄露。

---

## 1. `AMINER_API_KEY` — 文献核验的 AMiner 层

**用途**：`aminer_search.py`。当 Crossref 查不到（无 DOI 的中文文献、老会议论文）时，用 AMiner 的检索网关做存在性核验。

**免费**：是。

**怎么拿**：

1. 注册/登录 [aminer.cn](https://www.aminer.cn)。
2. 在站内做任意一次文献搜索，打开浏览器开发者工具 → Network。
3. 找发往 `searchtest.aminer.cn/aminer-search/search/publicationV2` 的请求，复制请求头 `Authorization` 里 `Bearer ` 后面的那串。

**注意**：

- 这是**你自己账号的会话凭证**，会过期。过期后现象是 401/403，重新取一次即可。
- 它代表你的账号身份，等同于密码级别的东西。**不要外传、不要写进任何会被提交的文件。**
- 开放平台旧域名的公开申请通道已不可用，不要去找「申请 API key」的页面。

**不给的后果**：`aminer_search.py` 直接报错退出。`verify_round1.py`（Crossref + arXiv）不依赖它，照常可用。

---

## 2. `ZOTERO_USER_ID` + `ZOTERO_API_KEY` — Zotero 直写通道（可选）

**用途**：`zotero_client.py`，对应 SKILL.md §10。用来批量修正自己的 Zotero 条目字段（类型切换、卷期页修正等），并做写入后回读断言。

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
- 建完先跑一次 `python zotero_client.py smoke`：它建一个临时条目、读回来、再删掉。通了再动真数据。
- 本脚本**故意不设默认 userID**：旧版本曾把某个 ID 写成默认值，别的账号不配环境变量就会往那个人的库里写。现在缺变量直接报错退出。

**不给的后果**：`zotero_client.py` 报错退出。skill 其余部分（写作规范、Crossref/arXiv 核验、引用覆盖核对）完全不受影响。

---

## 3. 大模型 API Key —— 本包不需要

这五个脚本全走免费文献接口，**不调用任何 LLM API**。skill 本身是给 Claude Code 读的规则文件，模型由你的 Claude Code 客户端负责（登录态或客户端侧的 `ANTHROPIC_API_KEY`），与这个仓库无关。

如果你以后自己写脚本想调用大模型做辅助判断，按下面的通用做法接，**不要照抄成硬编码**：

```python
import os
key = os.environ["MY_LLM_API_KEY"]     # 缺失即报错，不给默认值
```

然后把变量名登记进 `KEY_SETUP.md`，值只写在你本机的环境里。

---

## 4. 环境变量怎么设

### Windows（PowerShell）

当前会话临时生效：

```powershell
$env:AMINER_API_KEY = "你的值"
$env:ZOTERO_USER_ID = "1234567"
$env:ZOTERO_API_KEY = "你的值"
```

永久生效（写用户级环境变量，重启终端后可用）：

```powershell
[Environment]::SetEnvironmentVariable("AMINER_API_KEY", "你的值", "User")
```

### macOS / Linux

```bash
export AMINER_API_KEY="你的值"        # 写进 ~/.bashrc 或 ~/.zshrc 则永久生效
```

`.env.example` 只是**字段清单**，本包脚本不自动读取 `.env`。要读就自己加加载逻辑，或直接用上面的系统环境变量。

---

## 5. 防泄露纪律

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
