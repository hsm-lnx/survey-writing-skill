# -*- coding: utf-8 -*-
"""检索补漏脚本的共享工具。仅用标准库。

约定：
- 所有对外请求都带可识别的 User-Agent；Crossref 可选 mailto（环境变量
  CROSSREF_MAILTO），OpenAlex 可选 api_key（环境变量 OPENALEX_API_KEY）。
- 不写任何密钥、邮箱或本机绝对路径。
- 原始返回由各脚本落到 --out 指定的 JSON；本模块只负责请求与归一。
"""
import io
import json
import os
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import date

OPENALEX_BASE = "https://api.openalex.org"
CROSSREF_BASE = "https://api.crossref.org"

DOI_RE = re.compile(r"10\.\d{4,9}/[^\s\]\),;]+")
TAG_RE = re.compile(r"<[^>]+>")
REF_RE = re.compile(r"^\\?\[(\d+)\\?\]\s*(.+)$")

# 默认信号词：强化学习策略闭环。换主题时用 --signal 换成自己的正则。
DEFAULT_SIGNAL_RE = re.compile(
    r"reinforcement learning|q-learning|\bDQN\b|\bPPO\b|\bSAC\b|\bTD3\b|\bDDPG\b|"
    r"actor[- ]critic|policy gradient|deep rl|approximate dynamic programming|"
    r"\bDQL\b|\bA3C\b|\bA2C\b|\bTRPO\b|\bHER\b|temporal[- ]difference|"
    r"马尔可夫决策|强化学习|深度强化", re.I)

# 默认主题词（题名粗筛）。换主题时用 --topic-words 换成自己的词表。
DEFAULT_TOPIC_WORDS = ("weld", "gmaw", "gtaw", "fsw", "braz", "solder", "clad")


def today_stamp():
    return date.today().strftime("%Y%m%d")


def norm_doi(value):
    """统一 DOI：去协议前缀、小写、去尾部标点。"""
    if not value:
        return ""
    s = str(value).strip().lower()
    s = re.sub(r"^(https?://(dx\.)?doi\.org/|doi\s*:\s*)", "", s)
    return s.rstrip(".,;])")


def norm_title(value):
    """题名归一：NFKC、小写、只留字母数字与汉字。"""
    s = unicodedata.normalize("NFKC", str(value or "")).lower()
    return re.sub(r"[^a-z0-9一-鿿]+", "", s)


def match_text(value):
    """把题名/摘要变成带空格的小写文本，便于整词或词干包含判断。"""
    s = unicodedata.normalize("NFKC", str(value or "")).lower()
    return " " + re.sub(r"[^a-z0-9一-鿿]+", " ", s) + " "


def contains_any(text, words):
    t = match_text(text)
    for w in words:
        w = str(w or "").strip().lower()
        if w and w in t:
            return True
    return False


def first_doi(text):
    m = DOI_RE.search(str(text or ""))
    return m.group(0).rstrip(".") if m else ""


def strip_tags(value):
    return " ".join(TAG_RE.sub(" ", str(value or "")).split())


def load_json(path):
    with io.open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path, obj):
    parent = os.path.dirname(os.path.abspath(path))
    if parent and not os.path.isdir(parent):
        os.makedirs(parent)
    with io.open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


def parse_refs(path, heading=None):
    """从 md 正文解析参考文献表，返回 {编号: 条目正文}。

    默认在第一个「参考文献」/「References」标题之后开始解析；找不到标题时
    全文解析，并在 stderr 提示。正文里的行内 [n] 不会匹配，因为 REF_RE
    要求编号出现在行首。
    """
    with io.open(path, encoding="utf-8", errors="replace") as f:
        lines = f.read().splitlines()
    start = 0
    found = False
    for i, line in enumerate(lines):
        low = line.strip().lower()
        if heading:
            if heading.lower() in low:
                start, found = i + 1, True
                break
        elif (line.lstrip().startswith("#") and
              ("参考文献" in line or "references" in low)):
            start, found = i + 1, True
            break
    if not found:
        start = 0
        import sys
        sys.stderr.write("[warn] 未找到参考文献标题，按全文行首 [n] 解析：%s\n" % path)
    refs = {}
    for line in lines[start:]:
        m = REF_RE.match(line.strip())
        if m:
            refs.setdefault(int(m.group(1)), m.group(2).strip())
    return refs


def known_dois(paths):
    """从台账/正文中收集已出现过的 DOI。"""
    out = set()
    for path in paths:
        if not path or not os.path.isfile(path):
            continue
        with io.open(path, encoding="utf-8", errors="replace") as f:
            text = f.read().lower()
        out |= {norm_doi(d) for d in DOI_RE.findall(text)}
    return {d for d in out if d}


def _user_agent():
    mailto = (os.environ.get("CROSSREF_MAILTO") or
              os.environ.get("OPENALEX_MAILTO") or "").strip()
    ua = "survey-writing-skill/1.0"
    if mailto:
        ua += " (mailto:%s)" % mailto
    return ua


def _http_json(url, timeout=60, retries=3):
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": _user_agent()})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (429, 500, 502, 503, 504) and attempt + 1 < retries:
                time.sleep(1.5 * (attempt + 1))
                continue
            raise
        except Exception as e:
            last = e
            if attempt + 1 < retries:
                time.sleep(1.0 * (attempt + 1))
                continue
            raise
    raise last


def openalex_get(path, params):
    """GET OpenAlex；自动附加 OPENALEX_API_KEY / mailto（若已设置）。"""
    p = dict(params or {})
    key = os.environ.get("OPENALEX_API_KEY", "").strip()
    if key:
        p["api_key"] = key
    mailto = (os.environ.get("OPENALEX_MAILTO") or
              os.environ.get("CROSSREF_MAILTO") or "").strip()
    if mailto and "mailto" not in p:
        p["mailto"] = mailto
    url = OPENALEX_BASE + path + "?" + urllib.parse.urlencode(p)
    return url, _http_json(url, timeout=60)


def crossref_get(path, params, timeout=90):
    """GET Crossref；路径与参数分开，DOI 路径由调用方 quote。"""
    p = dict(params or {})
    mailto = os.environ.get("CROSSREF_MAILTO", "").strip()
    if mailto and "mailto" not in p:
        p["mailto"] = mailto
    url = CROSSREF_BASE + path
    if p:
        url += "?" + urllib.parse.urlencode(p)
    return _http_json(url, timeout=timeout)


def abstract_of(inverted_index):
    """OpenAlex 摘要倒排索引还原为文本。"""
    if not inverted_index:
        return ""
    pos = []
    for word, places in inverted_index.items():
        for place in places:
            pos.append((place, word))
    pos.sort()
    return " ".join(word for _, word in pos)


def crossref_record(item):
    """Crossref item -> 精简记录。"""
    title = strip_tags((item.get("title") or [""])[0] or "")
    return {
        "doi": norm_doi(item.get("DOI")),
        "title": title,
        "type": item.get("type"),
        "year": ((item.get("issued", {}).get("date-parts") or [[None]])[0] or [None])[0],
        "venue": (item.get("container-title") or [""])[0] or "",
        "abstract": strip_tags(item.get("abstract") or ""),
    }
