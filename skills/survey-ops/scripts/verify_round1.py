# -*- coding: utf-8 -*-
"""
Round-1 existence verification -- Crossref (free) + arXiv (free) layers.

Usage:
    python scripts/verify_round1.py <entries.json> <out.json> [start] [end]

Entry JSON item:
    {"n": 11, "doi": "...", "arxiv": "1802.09477" (optional),
     "raw": {"authors": [...], "etal": bool, "title": "...", "journal": str|null,
             "volume": str|null, "issue": str|null, "pages": str|null,
             "year": int|null, "month": str|null},
     "note": "optional corruption note"}

Verification order per entry:
  1. doi given:
     - 10.48550/arXiv.*        -> arXiv API (Crossref does not host DataCite DOIs),
                                  plus a Crossref bibliographic probe for a published version.
     - otherwise               -> GET api.crossref.org/works/{doi};
                                  on 404 -> bibliographic fallback (evidence for wrong-DOI cases).
  2. no doi                    -> Crossref bibliographic query (title + first author family),
                                  scored; unresolved candidates are left for the AMiner layer
                                  (scripts/aminer_search.py, separate step).
"""
import difflib
import html
import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

BASE = "https://api.crossref.org/works/"
ARXIV = "https://export.arxiv.org/api/query?id_list={}&max_results=1"
HDRS = {"User-Agent": "survey-writing-verification/1.0 (bibliography existence check)"}
ATOM = "{http://www.w3.org/2005/Atom}"

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# Standard abbreviation -> full journal title (deaccented lowercase, punctuation stripped).
ABBREV = {
    "j manuf syst": "journal of manufacturing systems",
    "ieee trans autom sci eng": "ieee transactions on automation science and engineering",
    "annu rev control": "annual reviews in control",
    "robot comput integr manuf": "robotics and computer-integrated manufacturing",
    "comput ind": "computers in industry",
    "int j adv manuf technol": "international journal of advanced manufacturing technology",
    "ieee trans syst man cybern": "ieee transactions on systems man and cybernetics",
    "j manuf process": "journal of manufacturing processes",
    "j intell manuf": "journal of intelligent manufacturing",
    "eng appl artif intell": "engineering applications of artificial intelligence",
    "comput chem eng": "computers chemical engineering",
    "int j control": "international journal of control",
    "cirp j manuf sci technol": "cirp journal of manufacturing science and technology",
    "j mech des": "journal of mechanical design",
    "opt lasers eng": "optics and lasers in engineering",
    "j mech sci technol": "journal of mechanical science and technology",
    "neural netw": "neural networks",
    "appl soft comput": "applied soft computing",
    "proc ieee": "proceedings of the ieee",
    "light adv manuf": "light advanced manufacturing",
    "manuf lett": "manufacturing letters",
    "mater today commun": "materials today communications",
    "addit manuf": "additive manufacturing",
    "metall trans b": "metallurgical transactions b",
    "appl sci": "applied sciences",
    "j heat transf": "journal of heat transfer",
    "int j inf technol syst approach": "international journal of information technologies and systems approach",
}
# 按需扩充：查 ISO 4 名录后在此追加 "缩写": "全称"（全小写、去标点）。

PARTICLES = {"van", "von", "de", "del", "der", "den", "la", "le", "di", "da", "du", "bin", "el"}


def deacc(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def norm_words(s):
    if s is None:
        return ""
    s = deacc(html.unescape(str(s))).casefold()
    s = re.sub(r"[^a-z0-9一-鿿]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def norm_page(s):
    if s is None:
        return None
    s = deacc(str(s))
    s = s.replace("–", "-").replace("—", "-").replace("−", "-")
    return re.sub(r"\s+", "", s)


def initials(given):
    parts = [p for p in re.split(r"[\s.\-]+", deacc(given)) if p]
    parts = [p for p in parts if p.casefold() not in PARTICLES]
    return "".join(p[0] for p in parts).casefold()


def http_get(url, tries=4):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=HDRS)
            with urllib.request.urlopen(req, timeout=40) as r:
                return r.read().decode("utf-8", errors="replace"), 200
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return "", 404
            if e.code in (429, 500, 502, 503, 504):
                time.sleep(2 * (i + 1))
                continue
            return "", e.code
        except Exception:
            time.sleep(2 * (i + 1))
    return "", "error"


def get_json(url, tries=4):
    text, status = http_get(url, tries)
    if status != 200:
        return {"__status__": status}
    try:
        return json.loads(text)
    except Exception:
        return {"__status__": "parse_error"}


def crossref_years(msg):
    out = {"years": set(), "print": None, "online": None}
    for k in ("issued", "published-print", "published-online", "published", "created"):
        v = msg.get(k) or {}
        for dp in v.get("date-parts", []):
            if dp and dp[0]:
                out["years"].add(int(dp[0]))
    pp = msg.get("published-print", {}).get("date-parts", [[None]])
    po = msg.get("published-online", {}).get("date-parts", [[None]])
    out["print"] = pp[0][0] if pp and pp[0] else None
    out["online"] = po[0][0] if po and po[0] else None
    out["years"] = sorted(out["years"])
    return out


def extract_record(msg):
    authors = []
    for a in msg.get("author", []) or []:
        nm = " ".join(x for x in (a.get("given"), a.get("family")) if x) or a.get("name", "")
        authors.append({"given": a.get("given", ""), "family": a.get("family", ""), "name": nm})
    yd = crossref_years(msg)
    return {
        "doi": msg.get("DOI"),
        "title": (msg.get("title") or [""])[0],
        "container": (msg.get("container-title") or [""])[0] if msg.get("container-title") else None,
        "short_container": (msg.get("short-container-title") or [""])[0] if msg.get("short-container-title") else None,
        "authors": authors,
        "years": yd["years"],
        "print_year": yd["print"],
        "online_year": yd["online"],
        "volume": msg.get("volume"),
        "issue": msg.get("issue"),
        "page": msg.get("page"),
        "article_number": msg.get("article-number"),
        "type": msg.get("type"),
        "publisher": msg.get("publisher"),
        "cited_by_crossref": msg.get("is-referenced-by-count"),
        "url": msg.get("URL"),
    }


def author_check(raw_authors, etal, cr_authors):
    detail = []
    for i, a in enumerate(raw_authors):
        if i >= len(cr_authors):
            detail.append({"stated": a, "crossref": None, "ok": False})
            continue
        toks = a.split()
        fam_raw = toks[-1]
        given_raw = " ".join(toks[:-1])
        fam_ok = norm_words(fam_raw) == norm_words(cr_authors[i]["family"].split()[-1])
        in_r, in_c = initials(given_raw), initials(cr_authors[i]["given"] or "")
        if in_r and in_c:
            init_ok = in_c.startswith(in_r) or in_r.startswith(in_c)
        else:
            init_ok = True
        # Fallback: publisher may split multi-part given names differently (e.g. Vietnamese
        # names). If the entry's family token IS in the record's family and all entry initials
        # appear among the record full name's word-initials, treat as compatible.
        note = None
        if fam_ok and not init_ok:
            cr_name = cr_authors[i].get("name") or ""
            cr_word_inits = {w[0].casefold() for w in cr_name.split() if w and w[0].isalpha()}
            if in_r and set(in_r) <= cr_word_inits:
                init_ok = True
                note = "记录对复名（given）切分方式不同，但姓氏与名字首字母均可对应"
        detail.append({
            "stated": a,
            "crossref": cr_authors[i]["name"],
            "family_ok": fam_ok,
            "initials": {"stated": in_r, "crossref": in_c, "ok": init_ok},
            "ok": fam_ok and init_ok,
            "note": note,
        })
    all_ok = all(d["ok"] for d in detail)
    count_note = None
    if raw_authors and len(cr_authors) < len(raw_authors):
        all_ok = False
    elif raw_authors and not etal and len(cr_authors) > len(raw_authors):
        count_note = f"条目列 {len(raw_authors)} 位作者，权威记录有 {len(cr_authors)} 位（条目少列）"
    return detail, all_ok, count_note


def field_cmp(raw_val, cr_val, dash=False):
    """raw missing -> ok=None (entry incomplete, not a conflict)."""
    if raw_val is None or raw_val == "":
        return {"stated": raw_val, "crossref": cr_val, "ok": None}
    if dash:
        ok = norm_page(raw_val) == norm_page(cr_val)
    else:
        ok = str(raw_val) == (str(cr_val) if cr_val is not None else None)
    return {"stated": raw_val, "crossref": cr_val, "ok": ok}


def compare(entry, rec):
    raw = entry["raw"]
    fields = {}

    t_ok = norm_words(raw["title"]) == norm_words(rec["title"])
    fields["title"] = {"stated": raw["title"], "crossref": rec["title"], "ok": t_ok}

    if raw.get("authors"):
        adetail, a_ok, a_note = author_check(raw["authors"], raw.get("etal", False), rec["authors"])
        fields["authors"] = {"detail": adetail, "etal": raw.get("etal", False),
                             "crossref_count": len(rec["authors"]), "note": a_note, "ok": a_ok}
    else:
        fields["authors"] = {"detail": [], "etal": False, "crossref_count": len(rec["authors"]),
                             "note": "条目无作者字段", "ok": None}

    if raw.get("year") is None:
        fields["year"] = {"stated": None, "crossref": rec["years"], "ok": None}
    else:
        fields["year"] = {"stated": raw["year"], "crossref": rec["years"],
                          "print": rec["print_year"], "online": rec["online_year"],
                          "ok": raw["year"] in rec["years"]}

    ab = norm_words(raw.get("journal") or "")
    c_norm = norm_words(rec["container"])
    if not ab:
        fields["journal"] = {"stated": raw.get("journal"), "crossref": rec["container"],
                             "ok": None, "basis": "条目未标出处"}
    elif ab == c_norm:
        fields["journal"] = {"stated": raw.get("journal"), "crossref": rec["container"],
                             "ok": True, "basis": "direct match"}
    else:
        expected_full = ABBREV.get(ab)
        if expected_full:
            en = norm_words(expected_full)
            j_ok = c_norm in (en, "the " + en)
            j_basis = "abbreviation mapped to full title"
        elif rec["short_container"] and norm_words(rec["short_container"]) == ab:
            j_ok = True
            j_basis = "matches Crossref short-container-title"
        else:
            j_ok = None
            j_basis = "no abbreviation mapping; manual check"
        fields["journal"] = {"stated": raw.get("journal"), "crossref": rec["container"],
                             "short_container": rec["short_container"], "ok": j_ok, "basis": j_basis}

    fields["volume"] = field_cmp(raw.get("volume"), rec["volume"])
    fields["issue"] = field_cmp(raw.get("issue"), rec["issue"], dash=True)
    p_raw = raw.get("pages")
    p_cr = rec["page"] or rec["article_number"]
    fields["pages"] = field_cmp(p_raw, p_cr, dash=True)
    if p_raw is not None and p_cr is None:
        fields["pages"]["ok"] = False

    hard = [f for f, v in fields.items() if v["ok"] is False]
    return fields, hard


def crossref_query(params):
    url = BASE + "?" + urllib.parse.urlencode(params)
    resp = get_json(url)
    items = []
    if "message" in resp:
        for it in resp["message"].get("items", []):
            items.append(extract_record(it))
    return url, items


def score_hit(entry, hit):
    t_norm = norm_words(entry["raw"]["title"])
    h_norm = norm_words(hit["title"])
    ratio = difflib.SequenceMatcher(None, t_norm, h_norm).ratio()
    if entry["raw"].get("authors"):
        fam = norm_words(entry["raw"]["authors"][0].split()[-1])
        author_ok = bool(hit["authors"]) and bool(hit["authors"][0].get("family")) \
            and norm_words(hit["authors"][0]["family"].split()[-1]) == fam
    else:
        author_ok = None
    y = entry["raw"].get("year")
    year_ok = None if y is None else any(abs(hy - y) <= 1 for hy in hit["years"])
    return {"ratio": round(ratio, 3), "author_ok": author_ok, "year_ok": year_ok}


def query_title_layer(entry, rows=4):
    """Crossref bibliographic query for entries without DOI (or with unresolvable DOI)."""
    title = entry["raw"]["title"]
    first_fam = entry["raw"]["authors"][0].split()[-1] if entry["raw"].get("authors") else None
    queries = []
    params = {"query.bibliographic": title, "rows": rows,
              "select": "DOI,title,container-title,issued,author,volume,issue,page,type,publisher,is-referenced-by-count"}
    url, hits = crossref_query(params)
    queries.append({"strategy": "query.bibliographic=<full title>", "url": url})
    if first_fam:
        params2 = {**params, "query.bibliographic": title + " " + first_fam}
        url2, hits2 = crossref_query(params2)
        queries.append({"strategy": "query.bibliographic=<title + first-author family>", "url": url2})
        seen, merged = set(), []
        for h in hits + hits2:
            if h["doi"] not in seen:
                seen.add(h["doi"])
                merged.append(h)
        hits = merged
    scored = [{**h, "score": score_hit(entry, h)} for h in hits]
    scored.sort(key=lambda x: -x["score"]["ratio"])
    return queries, scored


def verify_arxiv(arxiv_id):
    # arXiv's API rejects the generic Python-urllib UA (HTTP 406): send a descriptive one.
    text, status = None, None
    url = ARXIV.format(arxiv_id)
    for i in range(4):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "survey-writing-verification/1.0 (bibliography existence check)",
                "Accept": "application/atom+xml",
            })
            with urllib.request.urlopen(req, timeout=40) as r:
                text = r.read().decode("utf-8", errors="replace")
            status = 200
            break
        except urllib.error.HTTPError as e2:
            status = e2.code
            if status == 404:
                break
            # arXiv throttles aggressively (HTTP 406): back off hard before retrying.
            time.sleep(15 if status == 406 else 2 * (i + 1))
        except Exception:
            status = "error"
            time.sleep(2 * (i + 1))
    if status != 200:
        return {"status": f"API_ERROR_{status}"}
    try:
        root = ET.fromstring(text)
    except Exception:
        return {"status": "parse_error"}
    entry = root.find(ATOM + "entry")
    if entry is None:
        return {"status": "NOT_FOUND"}
    t_el = entry.find(ATOM + "title")
    title = (t_el.text or "").strip() if t_el is not None else ""
    if "error" in title.casefold() or not title:
        return {"status": "NOT_FOUND"}
    authors = []
    for a in entry.findall(ATOM + "author"):
        n_el = a.find(ATOM + "name")
        if n_el is not None and n_el.text:
            parts = n_el.text.strip().split()
            authors.append({"given": parts[0] if parts else "",
                            "family": " ".join(parts[1:]) if len(parts) > 1 else (parts[0] if parts else ""),
                            "name": n_el.text.strip()})
    pub = (entry.find(ATOM + "published").text or "")[:10] if entry.find(ATOM + "published") is not None else None
    upd = (entry.find(ATOM + "updated").text or "")[:10] if entry.find(ATOM + "updated") is not None else None
    return {"status": "OK", "title": re.sub(r"\s+", " ", title), "authors": authors,
            "v1_date": pub, "updated_date": upd,
            "years": sorted({int(pub[:4]) if pub else None, int(upd[:4]) if upd else None} - {None})}


def main():
    entries_path, out_path = sys.argv[1], sys.argv[2]
    start = int(sys.argv[3]) if len(sys.argv) > 3 else None
    end = int(sys.argv[4]) if len(sys.argv) > 4 else None
    with open(entries_path, encoding="utf-8") as f:
        entries = json.load(f)
    if start is not None:
        entries = [e for e in entries if start <= e["n"] <= (end if end is not None else start)]

    results = []
    for e in entries:
        n = e["n"]
        out = {"n": n, "stated_doi": e.get("doi"), "note": e.get("note")}
        doi = e.get("doi") or ""
        rec = None

        if doi.lower().startswith("10.48550/arxiv.") or (not doi and e.get("arxiv")):
            aid = e.get("arxiv") or re.split(r"arxiv\.", doi, flags=re.I)[1].split("v")[0]
            out["mode"] = "arxiv"
            out["arxiv_id"] = aid
            ax = verify_arxiv(aid)
            out["arxiv"] = ax
            time.sleep(3)  # arXiv API politeness (1 req / 3 s)
            if ax["status"] != "OK":
                out["proposed"] = ax["status"]
                results.append(out)
                print(f"[{n}] arxiv={ax['status']}")
                continue
            rec = {"doi": None, "title": ax["title"], "container": "arXiv (preprint)",
                   "short_container": None, "authors": ax["authors"], "years": ax["years"],
                   "print_year": None, "online_year": None, "volume": None, "issue": None,
                   "page": None, "article_number": None, "type": "preprint",
                   "publisher": "arXiv", "cited_by_crossref": None, "url": f"https://arxiv.org/abs/{aid}"}
            # probe Crossref for a formally published version (bonus note only)
            _, pubhits = crossref_query({"query.bibliographic": e["raw"]["title"], "rows": 3,
                                         "select": "DOI,title,container-title,issued"})
            for ph in pubhits:
                if norm_words(ph["title"]) == norm_words(e["raw"]["title"]):
                    out["published_version"] = {"doi": ph["doi"], "container": ph["container"],
                                                "year": ph["years"][0] if ph["years"] else None}
                    break
            time.sleep(1)

        elif doi:
            out["mode"] = "crossref-doi"
            text, status = http_get(BASE + urllib.parse.quote(doi, safe=""))
            if status == 404:
                out["doi_status"] = "NOT_FOUND"
            elif status == 200:
                out["doi_status"] = "RESOLVED"
                rec = extract_record(json.loads(text)["message"])
            else:
                out["doi_status"] = f"API_ERROR_{status}"
            time.sleep(1)

        if rec is None:
            out["mode"] = out.get("mode", "crossref-query") if not doi else out["mode"]
            out["mode"] = "crossref-query" if not doi else out["mode"] + "+query-fallback"
            queries, scored = query_title_layer(e)
            out["fallback_queries"] = queries
            out["fallback_hits"] = scored[:4]
            best = scored[0] if scored else None
            if best and best["score"]["ratio"] >= 0.92 and best["score"]["author_ok"] is not False:
                out["resolved_hit"] = best
                out["proposed"] = "RESOLVED_BY_QUERY"
            elif best and best["score"]["ratio"] >= 0.75:
                out["proposed"] = "REVIEW_CANDIDATES"
            else:
                out["proposed"] = "PENDING_AMINER"
            results.append(out)
            print(f"[{n}] mode={out['mode']} proposed={out['proposed']}"
                  + (f" best_ratio={best['score']['ratio']}" if scored else ""))
            continue

        out["record"] = rec
        fields, hard = compare(e, rec)
        out["fields"] = fields
        out["mismatch_fields"] = hard
        out["proposed"] = "OK" if not hard else "MISMATCH"
        results.append(out)
        print(f"[{n}] mode={out['mode']} proposed={out['proposed']}"
              + (f" mismatch={hard}" if hard else ""))
        time.sleep(1)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"saved -> {out_path} ({len(results)} entries)")


if __name__ == "__main__":
    main()
