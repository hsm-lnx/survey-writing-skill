#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
survey-writing / survey-ops 环境体检与配置助手（只用 Python 标准库）

它回答三个问题：
  1. 这台机器上，跑这个 skill 需要的东西齐不齐？
  2. 缺的东西里，哪些能自动装、哪些必须你手动登录后粘贴密钥？
  3. 已经配好的东西，真的能用吗？（会做只读探测，不会改你的文献库）

常用命令
--------
  python tools/doctor.py                 # 体检（含联网探测）
  python tools/doctor.py --offline       # 只查本机，不联网
  python tools/doctor.py --fix           # 自动安装缺失的可选工具（pandoc/curl）
  python tools/doctor.py --fix --with-zotero   # 连 Zotero 桌面版也一起装
  python tools/doctor.py --configure     # 交互式配置 AMiner / Zotero 密钥
  python tools/doctor.py --json          # 给脚本/CI 读的 JSON 结果

退出码：0 = 必需项齐全；1 = 有必需项不满足；2 = 用法或配置过程出错。

设计原则
--------
- 只读：体检阶段不发写请求。Zotero 只调 /keys/current 和一次 items 读取。
- 不打印密钥：只报「已设置 / 未设置 / 长度」，绝不回显值。
- 不静默改环境：--configure 会先问，再写；Windows 写 HKCU\\Environment，
  macOS/Linux 写 shell 启动文件里的受管区块，写前自动备份。
- 自动安装必须显式触发：只有带 --fix 才会运行包管理器。
"""

import argparse
import ctypes
import getpass
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

VERSION = "1.0.1"
MIN_PY = (3, 8)
UA = "survey-writing-doctor/1.0 (environment check)"
AMINER_URL = "https://searchtest.aminer.cn/aminer-search/search/publicationV2"
ZOTERO_KEYS_URL = "https://api.zotero.org/keys/current"
LOCAL_API = "http://127.0.0.1:23119/api/users/0/items?limit=1"
CROSSREF_URL = "https://api.crossref.org/works?rows=0"
ARXIV_URL = "https://export.arxiv.org/api/query?id_list=1706.03762&max_results=1"

BLOCK_START = "# >>> survey-writing env (managed by tools/doctor.py) >>>"
BLOCK_END = "# <<< survey-writing env <<<"


# --------------------------------------------------------------------------
# 输出
# --------------------------------------------------------------------------

class Reporter(object):
    def __init__(self, json_mode=False):
        self.json_mode = json_mode
        self.results = []
        self.required_failures = []

    def self_cmd(self, suffix=""):
        """给用户看的、指向本脚本的可复制命令。"""
        p = Path(__file__).resolve()
        try:
            rel = os.path.relpath(str(p), str(Path.cwd()))
            shown = rel if not rel.startswith("..") else str(p)
        except Exception:
            shown = str(p)
        exe = "python" if which("python") else ("python3" if which("python3") else "python")
        return '%s "%s"%s' % (exe, shown, (" " + suffix) if suffix else "")

    def section(self, title):
        if not self.json_mode:
            print("")
            print("== %s ==" % title)

    def add(self, level, name, detail, required=False, fix=None, install_key=None):
        """level: ok / warn / fail / skip / info"""
        item = {
            "level": level,
            "name": name,
            "detail": detail,
            "required": bool(required),
        }
        if fix:
            item["fix"] = fix
        if install_key:
            item["install_key"] = install_key
        self.results.append(item)
        if required and level == "fail":
            self.required_failures.append(name)
        if not self.json_mode:
            symbol = {"ok": "[OK]", "warn": "[!]", "fail": "[X]",
                      "skip": "[-]", "info": "[i]"}.get(level, "[i]")
            print("%s %s：%s" % (symbol, name, detail))
            if fix:
                print("      解决：%s" % fix)
        return item

    def summary(self):
        fails = [r for r in self.results if r["level"] == "fail"]
        warns = [r for r in self.results if r["level"] == "warn"]
        if self.json_mode:
            return
        print("")
        print("== 结论 ==")
        if not fails and not warns:
            print("[OK] 必需项和可选项都已就绪。")
        elif not fails:
            print("[OK] 必需项已就绪；有 %d 项提醒（[!]），按上面的「解决」处理即可。" % len(warns))
        else:
            print("[X] 有 %d 项必需项未满足，见上面的 [X]。" % len(fails))
        print("")
        print("随时可以再跑：%s" % self.self_cmd())
        if any(r.get("install_key") for r in self.results):
            print("自动安装缺失的可选工具：%s" % self.self_cmd("--fix"))
        need_key = any(
            r["name"] in ("AMINER_API_KEY", "ZOTERO_API_KEY") and r["level"] == "skip"
            for r in self.results)
        if need_key:
            print("配置 AMiner / Zotero 密钥：%s" % self.self_cmd("--configure"))


# --------------------------------------------------------------------------
# 基础工具
# --------------------------------------------------------------------------

def which(name):
    return shutil.which(name)


def run_version(cmd, args):
    """返回 (ok, 第一行版本信息)。"""
    try:
        p = subprocess.run([cmd] + args, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, timeout=20)
        text = p.stdout.decode("utf-8", "replace").strip()
        first = text.splitlines()[0] if text else ""
        return p.returncode == 0, first
    except Exception as e:
        return False, str(e)


def http_get(url, headers=None, timeout=8):
    h = {"User-Agent": UA, "Accept": "*/*"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.getcode(), r.read(200000)
    except urllib.error.HTTPError as e:
        try:
            body = e.read(20000)
        except Exception:
            body = b""
        return e.code, body
    except Exception:
        raise


def http_post_json(url, payload, headers=None, timeout=15):
    h = {"User-Agent": UA, "Content-Type": "application/json; charset=utf-8"}
    if headers:
        h.update(headers)
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=h, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.getcode(), r.read(200000)
    except urllib.error.HTTPError as e:
        try:
            body = e.read(20000)
        except Exception:
            body = b""
        return e.code, body
    except Exception:
        raise


def short_err(e):
    """把网络异常压成一句人话。"""
    text = str(e)
    low = text.lower()
    if "timed out" in low or "timeout" in low:
        return "连接超时（网络慢或接口被墙）"
    if "certificate" in low or "ssl" in low:
        return "TLS/证书错误（公司代理或杀毒软件可能拦截了 HTTPS）"
    if "connection refused" in low:
        return "连接被拒绝（服务未运行或端口不通）"
    if "name or service not known" in low or "getaddrinfo" in low:
        return "域名解析失败（检查 DNS 或代理）"
    return text.splitlines()[0][:160] if text else e.__class__.__name__


# --------------------------------------------------------------------------
# 1. Python
# --------------------------------------------------------------------------

def check_agent(rep):
    """Claude Code 是运行 skill 的宿主；没有命令行也可能是 IDE/桌面版。"""
    claude = which("claude")
    home_claude = Path.home() / ".claude"
    if claude:
        rep.add("ok", "Claude Code", claude)
    elif home_claude.is_dir():
        rep.add("ok", "Claude Code", "检测到 %s（命令行不在 PATH；IDE/桌面版可忽略）" % home_claude)
    else:
        rep.add("warn", "Claude Code",
                "未检测到 claude 命令或 ~/.claude；本 skill 需要一个能读 skill 的 agent",
                fix="安装 Claude Code：https://claude.com/claude-code")


def check_python(rep):
    rep.section("1. 必需项")
    check_agent(rep)
    v = sys.version_info
    version = "%d.%d.%d" % (v.major, v.minor, v.micro)
    if v >= MIN_PY:
        rep.add("ok", "Python", "%s（需要 3.8+）" % version, required=True)
    else:
        rep.add("fail", "Python", "当前 %s，需要 3.8+" % version, required=True,
                fix="升级 Python 后重新运行本脚本：https://www.python.org/downloads/")

    exe = sys.executable or which("python") or ""
    if exe:
        rep.add("info", "Python 路径", exe)

    py = which("python")
    py3 = which("python3")
    py_launcher = which("py")
    if py:
        rep.add("ok", "python 命令", py)
    elif py3:
        rep.add("warn", "python 命令", "只有 python3，没有 python；文档里的 python 请改成 python3",
                fix="macOS/Linux 可建别名：alias python=python3（写进 ~/.zshrc 或 ~/.bashrc）")
    elif py_launcher:
        rep.add("ok", "python 命令", "只有 py 启动器：%s；把命令里的 python 改成 py" % py_launcher)
    else:
        rep.add("warn", "python 命令", "PATH 里找不到 python/python3；从 Claude Code 调用脚本时可能失败",
                fix="把 Python 加入 PATH，或重启终端后再试")


# --------------------------------------------------------------------------
# 2. 可选命令行工具
# --------------------------------------------------------------------------

def check_tool(rep, name, version_args, purpose, required=False, install_key=None):
    path = which(name)
    if path:
        ok, ver = run_version(path, version_args)
        detail = ver if ok and ver else path
        rep.add("ok", name, detail + "  —— " + purpose)
        return True
    rep.add("warn", name, "未安装 —— " + purpose, required=required,
            install_key=install_key,
            fix=rep.self_cmd("--fix") if install_key else None)
    return False


def check_optional_tools(rep):
    rep.section("2. 可选命令行工具")
    check_tool(rep, "pandoc", ["--version"],
               "把 docx 转成 markdown（tools/convert.cmd 用）；不装只影响转换",
               install_key="pandoc")
    check_tool(rep, "curl", ["--version"],
               "arXiv 接口的兜底通道；不装只影响极少数 406 情况",
               install_key="curl")


# --------------------------------------------------------------------------
# 3. Zotero 桌面版 / 本地数据
# --------------------------------------------------------------------------

def _zotero_profile_roots():
    home = Path.home()
    roots = []
    system = platform.system()
    if system == "Windows":
        appdata = os.environ.get("APPDATA")
        if appdata:
            roots.append(Path(appdata) / "Zotero" / "Zotero" / "Profiles")
    elif system == "Darwin":
        roots.append(home / "Library" / "Application Support" / "Zotero" / "Profiles")
        roots.append(home / "Library" / "Application Support" / "Zotero" / "Profiles")
    else:
        roots.append(home / ".zotero" / "zotero" / "Profiles")
        roots.append(home / ".zotero" / "zotero")
        roots.append(home / ".config" / "zotero")
    return roots


def _read_zotero_datadir_from_prefs():
    for root in _zotero_profile_roots():
        if not root.is_dir():
            continue
        # Profiles/<xxx>/prefs.js 或直接在根下
        candidates = list(root.glob("*/prefs.js"))[:20] + list(root.glob("prefs.js"))[:1]
        for prefs in candidates:
            try:
                text = prefs.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            m = re.search(
                r'user_pref\("extensions\.zotero\.dataDir",\s*"((?:[^"\\]|\\.)*)"\)',
                text)
            if not m:
                continue
            raw = m.group(1)
            raw = raw.replace("\\\\", "\\").replace('\\"', '"')
            raw = os.path.expandvars(raw)
            p = Path(raw).expanduser()
            if p.exists():
                return p
    return None


def find_zotero_desktop():
    """返回 (可执行文件路径或 None, 数据目录或 None)。"""
    home = Path.home()
    system = platform.system()
    exe = which("zotero")
    exe_candidates = []
    if system == "Windows":
        for env_name in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
            base = os.environ.get(env_name)
            if base:
                exe_candidates.append(Path(base) / "Zotero" / "zotero.exe")
    elif system == "Darwin":
        exe_candidates += [Path("/Applications/Zotero.app"),
                           home / "Applications" / "Zotero.app"]
    else:
        exe_candidates += [Path("/usr/bin/zotero"), Path("/opt/zotero/zotero"),
                           Path("/usr/lib/zotero/zotero")]
    if not exe:
        for p in exe_candidates:
            if p.exists():
                exe = str(p)
                break

    data = _read_zotero_datadir_from_prefs()
    if data is None:
        defaults = [home / "Zotero"]
        if system != "Windows":
            defaults.append(home / ".var" / "app" / "org.zotero.Zotero" / "data" / "Zotero")
        for p in defaults:
            if (p / "zotero.sqlite").exists() or (p / "storage").is_dir():
                data = p
                break
    return exe, data


def count_pdfs(storage, cap=3000):
    n = 0
    if not storage or not storage.is_dir():
        return 0, False
    for root, dirs, files in os.walk(str(storage)):
        for f in files:
            if f.lower().endswith(".pdf"):
                n += 1
                if n >= cap:
                    return n, True
    return n, False


def check_zotero_desktop(rep):
    rep.section("3. Zotero 桌面版（可选，但推荐）")
    exe, data = find_zotero_desktop()

    if exe:
        rep.add("ok", "Zotero 程序", exe)
    else:
        rep.add("warn", "Zotero 程序", "未检测到桌面版。没有它也能用 Web API 写入，但本地 PDF 全文核对会少一处来源",
                install_key="zotero",
                fix=rep.self_cmd("--fix --with-zotero"))

    if data:
        storage = data / "storage"
        pdf_n, capped = count_pdfs(storage)
        sqlite_ok = (data / "zotero.sqlite").exists()
        msg = "%s" % data
        if sqlite_ok:
            msg += "；zotero.sqlite 存在"
        if storage.is_dir():
            msg += "；storage 内 PDF %s%d 篇" % (">=" if capped else "", pdf_n)
        else:
            msg += "；没有 storage 目录（可能还没存附件）"
        rep.add("ok", "Zotero 数据目录", msg)
    else:
        rep.add("warn", "Zotero 数据目录",
                "没找到 ~/Zotero 或 Zotero 设置里指定的数据目录；§7.4 的本地全文核对将只能扫 pdfs/",
                fix="打开 Zotero → 编辑 → 设置 → 高级 → 文件和文件夹，确认数据目录位置")

    # 本地 API：只有桌面版正在运行才可用
    try:
        status, body = http_get(LOCAL_API, headers={"Zotero-API-Version": "3"}, timeout=3)
        if status == 200:
            rep.add("ok", "Zotero 本地 API",
                    "127.0.0.1:23119 可访问（桌面版正在运行）")
        elif status in (400, 403, 404, 405):
            rep.add("warn", "Zotero 本地 API",
                    "端口有响应但返回 HTTP %s；若要用本地 API，请在 Zotero 设置中允许本地访问" % status)
        else:
            rep.add("warn", "Zotero 本地 API", "返回 HTTP %s" % status)
    except Exception:
        rep.add("skip", "Zotero 本地 API",
                "未连接（Zotero 没运行，或本地 API 未开启）；这是可选项，不影响 Web API")


# --------------------------------------------------------------------------
# 4. 环境变量
# --------------------------------------------------------------------------

def read_windows_user_env(name):
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_READ) as k:
            value, _ = winreg.QueryValueEx(k, name)
            return str(value or "").strip()
    except Exception:
        return ""


def get_env(name):
    """返回 (值, 来源说明)。不打印值。"""
    value = os.environ.get(name, "").strip()
    if value:
        return value, "当前会话"
    if platform.system() == "Windows":
        value = read_windows_user_env(name)
        if value:
            return value, "Windows 用户环境变量（已持久化，重启终端后当前会话才可见）"
    return "", ""


def check_env_vars(rep):
    rep.section("4. 外部账号与密钥")
    aminer, aminer_src = get_env("AMINER_API_KEY")
    zuser, zuser_src = get_env("ZOTERO_USER_ID")
    zkey, zkey_src = get_env("ZOTERO_API_KEY")

    if aminer:
        rep.add("ok", "AMINER_API_KEY", "已设置（长度 %d，来源：%s）" % (len(aminer), aminer_src))
    else:
        rep.add("skip", "AMINER_API_KEY",
                "未设置 —— 中文文献、无 DOI 老文献的 AMiner 核验不可用；Crossref/arXiv 照常",
                fix=rep.self_cmd("--configure"))

    if zkey:
        rep.add("ok", "ZOTERO_API_KEY", "已设置（长度 %d，来源：%s）" % (len(zkey), zkey_src))
    else:
        rep.add("skip", "ZOTERO_API_KEY",
                "未设置 —— Zotero 直写通道不可用；其余功能不受影响",
                fix=rep.self_cmd("--configure"))

    if zuser:
        rep.add("ok", "ZOTERO_USER_ID", "已设置（%s，来源：%s）" % (zuser, zuser_src))
    else:
        if zkey:
            rep.add("warn", "ZOTERO_USER_ID",
                    "未设置，但可以用 ZOTERO_API_KEY 自动推导",
                    fix=rep.self_cmd("--fix"))
        else:
            rep.add("skip", "ZOTERO_USER_ID",
                    "未设置 —— 配置 Zotero API key 后可自动推导",
                    fix=rep.self_cmd("--configure"))
    return aminer, zuser, zkey


# --------------------------------------------------------------------------
# 5. 网络与接口探测
# --------------------------------------------------------------------------

def check_network(rep, aminer, zkey, offline=False):
    rep.section("5. 网络与接口")
    if offline:
        rep.add("skip", "联网探测", "已按 --offline 跳过")
        return
    for p in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY"):
        if os.environ.get(p):
            rep.add("info", "代理变量", "%s 已设置（若接口连不上，先检查代理）" % p)

    # Crossref
    try:
        status, body = http_get(CROSSREF_URL, timeout=8)
        if status == 200:
            rep.add("ok", "Crossref", "可达（文献存在性核验的主通道）")
        else:
            rep.add("warn", "Crossref", "返回 HTTP %s；文献核验可能失败" % status)
    except Exception as e:
        rep.add("warn", "Crossref", short_err(e),
                fix="检查网络/代理后重试；离线时不能做文献核验")

    # arXiv
    try:
        status, body = http_get(ARXIV_URL, timeout=10)
        if status == 200 and b"<entry" in body:
            rep.add("ok", "arXiv", "可达")
        elif status == 406:
            rep.add("warn", "arXiv", "返回 406（urllib 被限流）—— 装 curl 后 arxiv_curl.py 可兜底",
                    install_key="curl",
                    fix=rep.self_cmd("--fix"))
        else:
            rep.add("warn", "arXiv", "返回 HTTP %s" % status)
    except Exception as e:
        rep.add("warn", "arXiv", short_err(e))

    # AMiner（只有配了 token 才探测）
    if aminer:
        try:
            payload = {"query": "survey", "needDetails": False, "page": 0, "size": 1}
            status, body = http_post_json(
                AMINER_URL, payload,
                headers={"Authorization": "Bearer " + aminer}, timeout=15)
            if status == 200:
                try:
                    data = json.loads(body.decode("utf-8"))
                    if isinstance(data, dict) and ("data" in data or "hitList" in json.dumps(data)):
                        rep.add("ok", "AMiner", "token 可用，接口返回正常")
                    else:
                        rep.add("warn", "AMiner", "返回 200 但内容不像检索结果，token 可能不是搜索接口的凭证")
                except Exception:
                    rep.add("warn", "AMiner", "返回 200 但无法解析 JSON")
            elif status in (401, 403):
                rep.add("warn", "AMiner", "HTTP %s —— token 无效或已过期，重新从 aminer.cn 复制" % status,
                        fix=rep.self_cmd("--configure"))
            else:
                rep.add("warn", "AMiner", "HTTP %s" % status)
        except Exception as e:
            rep.add("warn", "AMiner", short_err(e))
    else:
        rep.add("skip", "AMiner", "未配置 token，跳过")

    # Zotero Web API（只有配了 key 才探测）
    if zkey:
        try:
            status, body = http_get(
                ZOTERO_KEYS_URL,
                headers={"Authorization": "Bearer " + zkey, "Zotero-API-Version": "3"},
                timeout=10)
            if status == 200:
                try:
                    info = json.loads(body.decode("utf-8"))
                except Exception:
                    info = {}
                uid = info.get("userID")
                username = info.get("username")
                access = info.get("access") or {}
                user_access = access.get("user") or {}
                can_write = bool(user_access.get("write"))
                detail = "key 有效"
                if uid:
                    detail += "，属于 userID %s" % uid
                if username:
                    detail += "（%s）" % username
                detail += "；写权限：%s" % ("有" if can_write else "无")
                if can_write:
                    rep.add("ok", "Zotero Web API", detail)
                else:
                    rep.add("warn", "Zotero Web API", detail + "；只能读，不能批量修正",
                            fix="到 https://www.zotero.org/settings/keys 重建 key，勾选 Read/Write")
            elif status in (401, 403):
                rep.add("warn", "Zotero Web API", "HTTP %s —— key 无效或被吊销" % status,
                        fix=rep.self_cmd("--configure"))
            else:
                rep.add("warn", "Zotero Web API", "HTTP %s" % status)
        except Exception as e:
            rep.add("warn", "Zotero Web API", short_err(e))


def check_zotero_identity(rep, zuser, zkey):
    """若 userID 与 key 所属账号不一致，写入会落到错误库。"""
    if not (zuser and zkey):
        return
    try:
        status, body = http_get(
            ZOTERO_KEYS_URL,
            headers={"Authorization": "Bearer " + zkey, "Zotero-API-Version": "3"},
            timeout=10)
        if status != 200:
            return
        info = json.loads(body.decode("utf-8"))
        real = str(info.get("userID") or "")
        if real and real != str(zuser).strip():
            rep.add("fail", "ZOTERO_USER_ID 一致性",
                    "环境变量是 %s，但 key 属于 %s；写入会失败或写错库" % (zuser, real),
                    required=True,
                    fix="运行 %s 重新配置，或手动改成 %s" % (rep.self_cmd("--configure"), real))
        elif real:
            rep.add("ok", "ZOTERO_USER_ID 一致性", "与 key 所属账号一致（%s）" % real)
    except Exception:
        pass


# --------------------------------------------------------------------------
# 6. 安装状态
# --------------------------------------------------------------------------

def _candidate_install_roots(project_root):
    cwd = Path.cwd()
    roots = []
    if project_root:
        roots.append((Path(project_root) / ".claude" / "skills", "项目级（--project-root）", Path(project_root)))
    roots.append((cwd / ".claude" / "skills", "项目级（当前目录）", cwd))
    roots.append((Path.home() / ".claude" / "skills", "用户级", None))
    return roots


def find_install(project_root):
    for base, scope, root in _candidate_install_roots(project_root):
        if (base / "survey-ops" / "SKILL.md").exists() or (base / "survey-writing" / "SKILL.md").exists():
            return base, scope, root
    return None, None, None


def check_install_state(rep, project_root):
    rep.section("6. skill 安装状态")
    base, scope, root = find_install(project_root)

    if base:
        missing = []
        for rel in ("survey-writing/SKILL.md", "survey-ops/SKILL.md",
                    "_shared/handoff.md", "survey-ops/scripts/verify_round1.py",
                    "survey-ops/scripts/faithfulness_check.py"):
            if not (base / rel).exists():
                missing.append(rel)
        if missing:
            rep.add("warn", "skill 文件", "已找到 %s（%s），但缺少：%s" % (base, scope, "、".join(missing)),
                    fix="重新运行 install.ps1 / install.sh 覆盖安装")
        else:
            rep.add("ok", "skill", "已安装到 %s（%s）" % (base, scope))
    else:
        repo_clone = Path.cwd() / "skills" / "survey-ops" / "SKILL.md"
        if repo_clone.exists():
            rep.add("warn", "skill", "当前在仓库目录里，但还没装到项目/用户级",
                    fix="Windows: powershell -ExecutionPolicy Bypass -File install.ps1 -ProjectRoot <你的项目目录>；macOS/Linux: bash install.sh <你的项目目录>")
        else:
            rep.add("warn", "skill", "没找到已安装的 skill",
                    fix="先运行本仓库的 install.ps1 / install.sh")

    # 项目骨架
    skeleton_root = root if root else (Path.cwd() if (Path.cwd() / "manuscript").exists() else None)
    if skeleton_root:
        expected = ["manuscript", "pdfs", "bib", "docs", "reports", "reports/_raw"]
        missing = [d for d in expected if not (skeleton_root / d).is_dir()]
        ledger = skeleton_root / "bib" / "verified.md"
        progress = skeleton_root / "docs" / "progress.md"
        if not missing and ledger.exists() and progress.exists():
            rep.add("ok", "项目骨架", "%s 下的目录与台账齐全" % skeleton_root)
        else:
            bits = []
            if missing:
                bits.append("缺目录：" + "、".join(missing))
            if not ledger.exists():
                bits.append("缺 bib/verified.md")
            if not progress.exists():
                bits.append("缺 docs/progress.md")
            rep.add("warn", "项目骨架", "；".join(bits),
                    fix="重新运行 install.ps1 / install.sh -ProjectRoot <项目目录>")
    else:
        rep.add("skip", "项目骨架", "当前目录不是已初始化的项目；如果你只想全局用 skill，可忽略")


def check_daily_config(rep, project_root):
    """每日 Alert 监控是可选模块；只检查 config.json 字段，不显示授权码。"""
    rep.section("7. 每日监控（可选）")

    candidates = []
    if project_root:
        candidates.append(Path(project_root) / "daily")
    candidates.append(Path.cwd() / "daily")
    daily = next((p for p in candidates if (p / "config.json").is_file()), None)

    if daily is None:
        rep.add("skip", "每日监控", "未初始化（可选）；需要时按 README §4.8 运行 init_daily.py")
        return

    cfg_path = daily / "config.json"
    try:
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    except Exception as exc:
        rep.add("warn", "每日监控配置", "config.json 不是合法 JSON：%s" % exc,
                fix="按 daily/config.example.json 重填；授权码不要外传")
        return
    if not isinstance(cfg, dict):
        rep.add("warn", "每日监控配置", "config.json 顶层必须是对象 {...}")
        return

    def blank(value):
        return not isinstance(value, str) or not value.strip()

    def placeholder(value):
        text = value.strip().lower()
        return any(bit in text for bit in ("待填", "your-email", "example.com"))

    problems = []
    server = cfg.get("imap_server")
    if blank(server) or "imap" not in server.lower() or placeholder(server):
        problems.append("imap_server")
    port = cfg.get("imap_port")
    if not isinstance(port, int) or not (1 <= port <= 65535):
        problems.append("imap_port")
    email = cfg.get("email")
    if blank(email) or placeholder(email) or not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email.strip()):
        problems.append("email")
    code = cfg.get("auth_code")
    if blank(code) or placeholder(code) or len(code.strip()) < 6:
        problems.append("auth_code")
    sender = cfg.get("from_filter")
    domain = cfg.get("match_domain")
    if (blank(sender) or placeholder(sender)) and (blank(domain) or placeholder(domain)):
        problems.append("from_filter/match_domain")

    if problems:
        rep.add("warn", "每日监控配置", "这些字段还没填好：%s" % "、".join(problems),
                fix="填好后在 daily/ 里运行 python check_config.py --test-imap")
        return

    rep.add("ok", "每日监控配置", "必填字段齐全（授权码未显示，未做登录测试）")

    gi = daily / ".gitignore"
    if not gi.is_file() or "config.json" not in gi.read_text(encoding="utf-8", errors="replace"):
        rep.add("warn", "每日监控排除", "daily/.gitignore 没有排除 config.json",
                fix="重新运行 init_daily.py，或在 daily/.gitignore 加一行 config.json")
    else:
        rep.add("ok", "每日监控排除", "config.json 已在 .gitignore 中")


# --------------------------------------------------------------------------
# 自动安装
# --------------------------------------------------------------------------

def _winget_id(tool):
    return {
        "pandoc": ["JohnMacFarlane.Pandoc"],
        "curl": ["cURL.cURL"],
        "zotero": ["Zotero.Zotero"],
        "python": ["Python.Python.3.13", "Python.Python.3.12", "Python.Python.3.11"],
    }.get(tool, [])


def install_commands(tool):
    """返回候选安装命令列表（按优先级）。只返回命令，不执行。"""
    system = platform.system()
    cmds = []
    if system == "Windows":
        winget = which("winget")
        if winget:
            for pid in _winget_id(tool):
                cmds.append([winget, "install", "--id", pid, "-e",
                             "--accept-source-agreements",
                             "--accept-package-agreements", "--silent"])
        choco = which("choco")
        if choco and tool in ("pandoc", "curl", "python", "zotero"):
            cmds.append([choco, "install", "-y", {"python": "python"}.get(tool, tool)])
        scoop = which("scoop")
        if scoop and tool in ("pandoc", "curl", "python", "zotero"):
            cmds.append([scoop, "install", tool])
        return cmds

    if system == "Darwin":
        brew = which("brew")
        if brew:
            if tool == "zotero":
                cmds.append([brew, "install", "--cask", "zotero"])
            else:
                cmds.append([brew, "install", tool])
        return cmds

    # Linux
    if tool == "zotero":
        flatpak = which("flatpak")
        if flatpak:
            cmds.append([flatpak, "install", "-y", "flathub", "org.zotero.Zotero"])
        return cmds

    apt = which("apt-get")
    dnf = which("dnf")
    pacman = which("pacman")
    zypper = which("zypper")
    apk = which("apk")
    pkgs = {"pandoc": "pandoc", "curl": "curl", "python": "python3"}
    pkg = pkgs.get(tool)
    if not pkg:
        return cmds
    if apt:
        cmds.append(["sudo", "-n", apt, "install", "-y", pkg])
    if dnf:
        cmds.append(["sudo", "-n", dnf, "install", "-y", pkg])
    if pacman:
        cmds.append(["sudo", "-n", pacman, "-S", "--noconfirm",
                     "pandoc-cli" if tool == "pandoc" else pkg])
    if zypper:
        cmds.append(["sudo", "-n", zypper, "--non-interactive", "install", pkg])
    if apk:
        cmds.append(["sudo", "-n", apk, "add", pkg])
    return cmds


def display_cmd(cmd):
    return " ".join('"%s"' % c if " " in c else c for c in cmd)


def run_install(tool, yes, with_zotero):
    if tool == "zotero" and not with_zotero:
        print("  [跳过] Zotero 桌面版体积较大，确认要装请加 --with-zotero")
        return False
    cmds = install_commands(tool)
    if not cmds:
        print("  [!] 没找到可用的包管理器。请手动安装 %s。" % tool)
        if tool == "zotero":
            print("      Zotero 下载：https://www.zotero.org/download/")
        if platform.system() == "Darwin":
            print("      macOS 可先安装 Homebrew：https://brew.sh")
        elif platform.system() == "Windows":
            print("      Windows 可在 Microsoft Store 安装 App Installer（提供 winget）")
        return False
    for cmd in cmds:
        print("  执行：%s" % display_cmd(cmd))
        if not yes:
            if not ask_yes("  现在执行吗？", default=False):
                print("  已跳过。")
                continue
        try:
            p = subprocess.run(cmd)
            if p.returncode == 0:
                print("  [OK] %s 安装命令完成；重新开一个终端后生效。" % tool)
                return True
            print("  [!] 命令退出码 %d，可能缺少管理员权限或包名不适用。" % p.returncode)
        except FileNotFoundError:
            print("  [!] 命令不存在：%s" % cmd[0])
        except Exception as e:
            print("  [!] 执行失败：%s" % e)
    if platform.system() == "Linux":
        print("  提示：sudo -n 需要免密 sudo；若提示密码，请在终端手动执行上面的命令。")
    return False


def run_fix(args):
    print("")
    print("== 自动修复 ==")
    if args.offline:
        print("[跳过] --offline 模式不联网、也不调用包管理器。去掉 --offline 再试。")
        return
    # 先从 key 推导 userID
    zuser, _ = get_env("ZOTERO_USER_ID")
    zkey, _ = get_env("ZOTERO_API_KEY")
    if zkey and not zuser:
        print("检测到 ZOTERO_API_KEY 但缺少 ZOTERO_USER_ID，尝试自动推导……")
        try:
            status, body = http_get(
                ZOTERO_KEYS_URL,
                headers={"Authorization": "Bearer " + zkey, "Zotero-API-Version": "3"},
                timeout=10)
            if status == 200:
                info = json.loads(body.decode("utf-8"))
                uid = info.get("userID")
                if uid:
                    if args.yes or ask_yes("把 ZOTERO_USER_ID 设为 %s？" % uid, default=True):
                        persist_env({"ZOTERO_USER_ID": str(uid)})
                        print("  [OK] 已写入 ZOTERO_USER_ID=%s" % uid)
                else:
                    print("  [!] key 有效但返回里没有 userID。")
            else:
                print("  [!] key 校验返回 HTTP %s，先运行 --configure 换 key。" % status)
        except Exception as e:
            print("  [!] 自动推导失败：%s" % short_err(e))

    # 安装缺失的工具
    wanted = []
    for r in list_results_from_last_check():
        key = r.get("install_key")
        if key and key not in wanted:
            wanted.append(key)
    if not wanted:
        print("没有需要自动安装的缺失工具。")
        return
    print("检测到缺失：%s" % "、".join(wanted))
    for tool in wanted:
        run_install(tool, args.yes, args.with_zotero)


_LAST_RESULTS = []


def list_results_from_last_check():
    return _LAST_RESULTS


# --------------------------------------------------------------------------
# 交互式配置
# --------------------------------------------------------------------------

def ask_yes(prompt, default=False):
    suffix = " [Y/n] " if default else " [y/N] "
    try:
        ans = input(prompt + suffix).strip().lower()
    except EOFError:
        return default
    if not ans:
        return default
    return ans in ("y", "yes", "是", "好", "1")


def _escape_sh(value):
    return "'" + value.replace("\\", "\\\\").replace("'", "'\\''") + "'"


def _escape_fish(value):
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def _pick_rc():
    home = Path.home()
    shell = os.environ.get("SHELL", "")
    if "fish" in shell:
        return home / ".config" / "fish" / "config.fish"
    if "zsh" in shell:
        return home / ".zshrc"
    if "bash" in shell:
        if platform.system() == "Darwin":
            p = home / ".bash_profile"
            return p if p.exists() else home / ".bashrc"
        return home / ".bashrc"
    return home / ".profile"


def _read_managed_block(text):
    pattern = re.compile(
        r"(?ms)^" + re.escape(BLOCK_START) + r".*?^" + re.escape(BLOCK_END) + r"\n?")
    m = pattern.search(text)
    if not m:
        return {}, text
    block = m.group(0)
    entries = {}
    for line in block.splitlines():
        line = line.strip()
        if line.startswith("export "):
            rest = line[len("export "):]
            if "=" in rest:
                name, val = rest.split("=", 1)
                entries[name.strip()] = val.strip()
        elif line.startswith("set -gx "):
            rest = line[len("set -gx "):]
            parts = rest.split(None, 1)
            if len(parts) == 2:
                entries[parts[0].strip()] = parts[1].strip()
    return entries, pattern.sub("", text)


def persist_env(mapping):
    """把变量写进用户级环境；返回一段人话说明。"""
    for k, v in mapping.items():
        os.environ[k] = v

    if platform.system() == "Windows":
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0,
                            winreg.KEY_SET_VALUE) as key:
            for name, value in mapping.items():
                winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)
        # 通知资源管理器环境变量变了，新开的进程能拿到
        try:
            HWND_BROADCAST = 0xFFFF
            WM_SETTINGCHANGE = 0x001A
            SMTO_ABORTIFHUNG = 0x0002
            ctypes.windll.user32.SendMessageTimeoutW(
                HWND_BROADCAST, WM_SETTINGCHANGE, 0,
                ctypes.c_wchar_p("Environment"), SMTO_ABORTIFHUNG, 5000, None)
        except Exception:
            pass
        return "已写入 Windows 用户环境变量（新开的终端生效）"

    rc = _pick_rc()
    fish = rc.suffix == ".fish" or "fish" in os.environ.get("SHELL", "")
    try:
        old = rc.read_text(encoding="utf-8", errors="ignore") if rc.exists() else ""
        entries, cleaned = _read_managed_block(old)
        # 反解旧值：旧块里存的是 shell 字面量，这里只在同名变量被覆盖时忽略旧值
        rendered = []
        for name, value in mapping.items():
            entries[name] = _escape_fish(value) if fish else _escape_sh(value)
        for name in sorted(entries):
            rendered.append(("set -gx %s %s" if fish else "export %s=%s") % (name, entries[name]))
        block = BLOCK_START + "\n" + "\n".join(rendered) + "\n" + BLOCK_END + "\n"
        if rc.exists():
            backup = rc.with_name(rc.name + ".survey-backup-" + time.strftime("%Y%m%d%H%M%S"))
            try:
                shutil.copy2(str(rc), str(backup))
                os.chmod(str(backup), 0o600)
            except Exception:
                pass
        rc.parent.mkdir(parents=True, exist_ok=True)
        rc.write_text(cleaned.rstrip() + "\n\n" + block, encoding="utf-8")
        return "已写入 %s（重开终端或 source 后生效）" % rc
    except Exception as e:
        return "写入 %s 失败：%s；请手动 export" % (rc, e)


def configure(online=True):
    if not sys.stdin.isatty():
        print("--configure 需要在交互式终端里运行（不要在管道或 CI 里跑）。")
        print("你也可以按 KEY_SETUP.md 手动设置环境变量。")
        return 2

    print("")
    print("== 交互式配置 ==")
    print("说明：密钥只保存在你本机的用户环境里，不会写进这个仓库。")
    print("输入时不会回显；直接回车表示跳过该项。")
    print("")

    aminer, _ = get_env("AMINER_API_KEY")
    if ask_yes("配置 AMiner？(中文文献 / 无 DOI 老文献核验用；免费)", default=not bool(aminer)):
        token = getpass.getpass("  粘贴 AMiner Bearer token（直接回车跳过）：").strip()
        if token:
            if online:
                print("  正在验证 token……")
                try:
                    status, _ = http_post_json(
                        AMINER_URL,
                        {"query": "survey", "needDetails": False, "page": 0, "size": 1},
                        headers={"Authorization": "Bearer " + token}, timeout=15)
                    if status == 200:
                        print("  [OK] token 可用。")
                    elif status in (401, 403):
                        print("  [!] HTTP %s：token 无效或已过期。" % status)
                        if not ask_yes("  仍然保存吗？", default=False):
                            token = ""
                    else:
                        print("  [!] 接口返回 HTTP %s；先保存，之后可再验。" % status)
                except Exception as e:
                    print("  [!] 验证失败：%s；先保存。" % short_err(e))
            if token:
                print("  " + persist_env({"AMINER_API_KEY": token}))
                print("  已保存 AMINER_API_KEY（长度 %d）" % len(token))

    zkey, _ = get_env("ZOTERO_API_KEY")
    if ask_yes("配置 Zotero？(批量修正 Zotero 条目用；免费)", default=not bool(zkey)):
        key = getpass.getpass("  粘贴 Zotero API key（直接回车跳过）：").strip()
        if key:
            uid = None
            if online:
                print("  正在用 key 查询账号信息……")
                try:
                    status, body = http_get(
                        ZOTERO_KEYS_URL,
                        headers={"Authorization": "Bearer " + key,
                                 "Zotero-API-Version": "3"}, timeout=10)
                    if status == 200:
                        info = json.loads(body.decode("utf-8"))
                        uid = info.get("userID")
                        name = info.get("username") or ""
                        access = (info.get("access") or {}).get("user") or {}
                        print("  [OK] key 有效：userID=%s %s，写权限=%s"
                              % (uid, name, "有" if access.get("write") else "无"))
                        if not access.get("write"):
                            print("  [!] 这个 key 只有读权限；要批量修正请在 Zotero 设置里重建 Read/Write key。")
                    elif status in (401, 403):
                        print("  [!] HTTP %s：key 无效。" % status)
                        if not ask_yes("  仍然保存吗？", default=False):
                            key = ""
                    else:
                        print("  [!] 校验返回 HTTP %s；先保存，之后可再验。" % status)
                except Exception as e:
                    print("  [!] 校验失败：%s；先保存。" % short_err(e))
            if key:
                if not uid:
                    entered = input("  你的 Zotero userID（数字；可留空稍后自动推导）：").strip()
                    uid = entered or None
                mapping = {"ZOTERO_API_KEY": key}
                if uid:
                    mapping["ZOTERO_USER_ID"] = str(uid)
                print("  " + persist_env(mapping))
                print("  已保存 ZOTERO_API_KEY（长度 %d）%s"
                      % (len(key), "，userID=%s" % uid if uid else ""))

    print("")
    print("配置完成。请重开终端（或重新启动 Claude Code）让环境变量生效。")
    zkey_now, _ = get_env("ZOTERO_API_KEY")
    if zkey_now:
        base, scope, root = find_install("")
        if base and (base / "survey-ops" / "scripts" / "zotero_client.py").exists():
            smoke = base / "survey-ops" / "scripts" / "zotero_client.py"
        else:
            smoke = Path(".claude") / "skills" / "survey-ops" / "scripts" / "zotero_client.py"
        exe = "python" if which("python") else ("python3" if which("python3") else "python")
        print("然后跑一次 smoke 验证 Zotero 写权限：")
        print('  %s "%s" smoke' % (exe, smoke))
        print("（它建一个临时条目、读回、再删掉；不会碰你的真实文献）")
    return 0


# --------------------------------------------------------------------------
# 主流程
# --------------------------------------------------------------------------

def print_header():
    print("survey-writing / survey-ops 环境体检 v%s" % VERSION)
    print("平台：%s %s / Python %s" % (
        platform.system(), platform.release(), platform.python_version()))
    print("时间：%s" % time.strftime("%Y-%m-%d %H:%M:%S"))
    print("说明：本脚本只读探测，不会修改文献库；密钥只报有无，不显示值。")


def main(argv=None):
    global _LAST_RESULTS
    parser = argparse.ArgumentParser(
        description="survey-writing / survey-ops 环境体检与配置助手",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""例子：
  python tools/doctor.py
  python tools/doctor.py --offline
  python tools/doctor.py --fix
  python tools/doctor.py --fix --with-zotero
  python tools/doctor.py --configure
""")
    parser.add_argument("--offline", action="store_true", help="不联网，只查本机")
    parser.add_argument("--fix", action="store_true", help="自动安装缺失的可选工具")
    parser.add_argument("--configure", action="store_true", help="交互式配置 AMiner / Zotero 密钥")
    parser.add_argument("--with-zotero", action="store_true", help="--fix 时连 Zotero 桌面版一起装")
    parser.add_argument("--yes", "-y", action="store_true", help="自动确认安装命令")
    parser.add_argument("--json", action="store_true", help="输出 JSON（不打印人话）")
    parser.add_argument("--project-root", default="", help="项目目录，用于检查骨架与安装位置")
    parser.add_argument("--strict", action="store_true", help="把警告也当作失败（CI 用）")
    parser.add_argument("--version", action="version", version="doctor " + VERSION)
    args = parser.parse_args(argv)

    if args.json and (args.fix or args.configure):
        print("--json 不能和 --fix / --configure 一起用（那两个会交互、会改环境）。", file=sys.stderr)
        return 2

    if not args.json:
        print_header()

    rep = Reporter(json_mode=args.json)
    check_python(rep)
    check_optional_tools(rep)
    check_zotero_desktop(rep)
    aminer, zuser, zkey = check_env_vars(rep)
    check_network(rep, aminer, zkey, offline=args.offline)
    if not args.offline:
        check_zotero_identity(rep, zuser, zkey)
    check_install_state(rep, args.project_root)
    check_daily_config(rep, args.project_root)

    _LAST_RESULTS = rep.results

    if args.fix:
        run_fix(args)
    if args.configure:
        code = configure(online=not args.offline)
        if code:
            return code

    rep.summary()

    if args.json:
        payload = {
            "version": VERSION,
            "platform": platform.platform(),
            "python": platform.python_version(),
            "ok": not rep.required_failures,
            "required_failures": rep.required_failures,
            "results": rep.results,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))

    if rep.required_failures:
        return 1
    if args.strict and any(r["level"] == "warn" for r in rep.results):
        return 1
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n已取消。")
        sys.exit(130)
