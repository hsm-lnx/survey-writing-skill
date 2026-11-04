#!/usr/bin/env python3
"""Zotero Web API client for survey-writing.

Establishes a direct-write channel to the user's own Zotero library.
Subcommands:
  smoke        create/get/delete a dummy item to verify write access
  find         list library top-level items, locate candidate entries
  patch        apply approved PATCH payloads (stage 2 only, explicit file)

All raw responses are saved verbatim under $ZOTERO_RAW_DIR; every call is
appended to the same directory's zotero_channel.log.md.

Env:
  ZOTERO_API_KEY   required. Create at https://www.zotero.org/settings/keys
                   (needs read/write on the target library).
  ZOTERO_USER_ID   required. Your numeric userID, shown on the same keys page.
  ZOTERO_RAW_DIR   optional. Default: ./reports/_raw

This client writes to the library that ZOTERO_API_KEY belongs to. Never
commit real keys; see KEY_SETUP.md.
Stdout is ASCII-only (Windows console); file logs are UTF-8.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime

USER_ID = os.environ.get("ZOTERO_USER_ID", "").strip()
API_KEY = os.environ.get("ZOTERO_API_KEY", "").strip()
RAW = os.environ.get("ZOTERO_RAW_DIR", os.path.join("reports", "_raw"))
LOG = os.path.join(RAW, "zotero_channel.log.md")

SMOKE_TITLE = "SMOKE_TEST"
SMOKE_TAG = "smoke-test"


def require_env():
    missing = [k for k, v in (("ZOTERO_USER_ID", USER_ID), ("ZOTERO_API_KEY", API_KEY)) if not v]
    if missing:
        raise SystemExit(
            "missing env: %s -- see KEY_SETUP.md (no default user id on purpose: "
            "a wrong default would write into someone else's library)" % ", ".join(missing)
        )


def _base():
    require_env()
    return "https://api.zotero.org/users/" + USER_ID


def log(line):
    os.makedirs(RAW, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def save_raw(name, data):
    os.makedirs(RAW, exist_ok=True)
    with open(RAW + "/" + name, "wb") as f:
        f.write(data)
    return RAW + "/" + name


def req(method, path, body=None, version_header=None):
    """One API call. Returns (status, headers, body_bytes)."""
    headers = {"Zotero-API-Version": "3", "Authorization": "Bearer " + API_KEY}
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if version_header is not None:
        headers["If-Unmodified-Since-Version"] = str(version_header)
    r = urllib.request.Request(_base() + path, data=data, method=method,
                               headers=headers)
    try:
        with urllib.request.urlopen(r, timeout=45) as resp:
            return resp.status, dict(resp.headers), resp.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def call(method, path, tag, body=None, version_header=None):
    """req + verbatim raw save + log line. Returns (status, obj|None)."""
    status, hdrs, raw = req(method, path, body=body,
                            version_header=version_header)
    safe_tag = tag.replace("/", "_").replace("?", "_")
    fname = "zotero_%s_%s.json" % (safe_tag, datetime.now().strftime("%Y%m%d"))
    save_raw(fname, raw)
    lmver = hdrs.get("Last-Modified-Version") or hdrs.get("last-modified-version")
    log("| %s | `%s %s` | %s | lmver=%s | raw=%s |" % (
        datetime.now().strftime("%H:%M:%S"), method, path, status, lmver, fname))
    obj = None
    if raw:
        try:
            obj = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            obj = None
    return status, obj


def fail(code, msg):
    print("SMOKE_FAIL: " + msg)
    sys.exit(code)


# ---------------------------------------------------------------- smoke
def delete_permanently(key, version, tag):
    """DELETE, then purge from trash if it only landed there."""
    status, _ = call("DELETE", "/items/" + key, tag + "_delete",
                     version_header=version)
    if not (200 <= status < 300):
        fail(4, "%s: DELETE rejected (HTTP %s)" % (tag, status))
    status, obj = call("GET", "/items/" + key + "?format=json",
                       tag + "_get_after_delete")
    if status == 404:
        return True  # permanently gone
    if status != 200:
        fail(5, "%s: post-delete GET unexpected HTTP %s" % (tag, status))
    if not (obj or {}).get("data", {}).get("deleted"):
        fail(6, "%s: item still exists and is not in trash" % tag)
    # item is in trash: purge it (second DELETE with fresh version)
    ver2 = obj["version"]
    status, _ = call("DELETE", "/items/" + key, tag + "_purge",
                     version_header=ver2)
    if not (200 <= status < 300):
        fail(7, "%s: trash purge DELETE rejected (HTTP %s)" % (tag, status))
    status, _ = call("GET", "/items/" + key + "?format=json",
                     tag + "_get_after_purge")
    if status == 404:
        return True
    fail(8, "%s: item still retrievable after purge (HTTP %s)" % (tag, status))


def cmd_smoke():
    if not API_KEY:
        fail(1, "ZOTERO_API_KEY not set")
    log("\n## smoke run %s" % datetime.now().isoformat(timespec="seconds"))
    log("- user id: %s (main library, no collection)" % USER_ID)

    # leftover sweep from any earlier failed run
    status, obj = call("GET", "/items?q=" + SMOKE_TITLE + "&format=json&limit=10",
                       "smoke_leftover_scan")
    if status != 200:
        fail(2, "leftover scan GET failed (HTTP %s)" % status)
    leftovers = [it for it in (obj or [])
                 if it.get("data", {}).get("title") == SMOKE_TITLE]
    if leftovers:
        log("- leftover sweep: %d prior smoke item(s) found, deleting"
            % len(leftovers))
        for it in leftovers:
            delete_permanently(it["key"], it["version"], "smoke_leftover_" + it["key"])
        print("LEFTOVER_CLEANUP: %d item(s) removed" % len(leftovers))

    # create
    payload = [{"itemType": "journalArticle", "title": SMOKE_TITLE,
                "tags": [{"tag": SMOKE_TAG}]}]
    status, obj = call("POST", "/items", "smoke_01_create", body=payload)
    if status != 200:
        fail(10, "create POST HTTP %s" % status)
    ok = (obj or {}).get("successful") or (obj or {}).get("success")
    if not ok:
        fail(11, "create POST returned no success object; failed=%s"
             % json.dumps((obj or {}).get("failed")))
    item = ok["0"]
    key, ver = item["key"], item["version"]
    print("SMOKE_CREATED: key=%s version=%s" % (key, ver))

    # read back
    status, obj = call("GET", "/items/" + key + "?format=json", "smoke_02_get")
    if status != 200:
        fail(12, "read-back GET HTTP %s" % status)
    got_title = (obj or {}).get("data", {}).get("title")
    if got_title != SMOKE_TITLE:
        fail(13, "read-back title mismatch: %r" % got_title)
    print("SMOKE_READBACK_OK: version=%s" % (obj or {}).get("version"))

    # delete (+ purge if trashed)
    delete_permanently(key, ver, "smoke")

    # belt-and-suspenders: confirm not lingering in trash
    status, obj = call("GET", "/trash?format=json&limit=25", "smoke_trash_scan")
    if status == 200:
        lingering = [it for it in (obj or [])
                     if it.get("data", {}).get("title") == SMOKE_TITLE
                     or it.get("key") == key]
        if lingering:
            fail(14, "smoke item still in trash: %s" % [it["key"] for it in lingering])
    print("SMOKE_OK: create -> readback -> delete -> verified gone "
          "(trash purged if needed)")


# ---------------------------------------------------------------- find
def norm_doi(s):
    return (s or "").strip().lower().replace("https://doi.org/", "")


SURNAME_STEMS = ["rajeswaran", "thananjeyan"]
DOI_TARGETS = {"10.48550/arxiv.1709.10087", "10.15607/rss.2018.xiv.049",
               "10.48550/arxiv.1905.13402", "10.1109/lra.2020.2976272"}
TITLE_STEMS = ["dexterous manipulation", "safety augmented value estimation"]


def match_reason(data):
    reasons = []
    for c in data.get("creators", []):
        fam = (c.get("family") or "").lower()
        if any(s in fam for s in SURNAME_STEMS):
            reasons.append("creator:" + fam)
    if norm_doi(data.get("DOI")) in DOI_TARGETS:
        reasons.append("doi")
    t = (data.get("title") or "").lower()
    for stem in TITLE_STEMS:
        if stem in t:
            reasons.append("title:" + stem)
    return reasons


def cmd_find():
    if not API_KEY:
        print("FIND_FAIL: ZOTERO_API_KEY not set")
        sys.exit(1)
    log("\n## find run %s" % datetime.now().isoformat(timespec="seconds"))
    items, start, page = [], 0, 0
    total = None
    while True:
        status, obj = call("GET", "/items/top?format=json&limit=100&start=%d"
                           % start, "lib_top_p%03d" % (page + 1))
        if status != 200:
            print("FIND_FAIL: library listing HTTP %s" % status)
            sys.exit(2)
        items.extend(obj)
        if total is None:
            total = int(status)
        page += 1
        if len(obj) < 100:
            break
        start += 100
        if page >= 40:
            print("FIND_WARN: stopped at 4000 items")
            break
    print("LIBRARY_ITEMS(top-level): %d (pages=%d)" % (len(items), page))
    n = 0
    for it in items:
        data = it.get("data", {})
        reasons = match_reason(data)
        if not reasons:
            continue
        n += 1
        key = it["key"]
        fname = "zotero_match_%s.json" % key
        save_raw(fname, json.dumps(it, ensure_ascii=False, indent=2).encode("utf-8"))
        log("- match #%d key=%s ver=%s type=%s reasons=%s -> %s"
            % (n, key, it.get("version"), data.get("itemType"),
               ";".join(reasons), fname))
        print(json.dumps({
            "match": n, "key": key, "version": it.get("version"),
            "itemType": data.get("itemType"), "title": data.get("title"),
            "DOI": data.get("DOI"), "date": data.get("date"),
            "publicationTitle": data.get("publicationTitle"),
            "volume": data.get("volume"), "issue": data.get("issue"),
            "pages": data.get("pages"), "url": data.get("url"),
            "extra": data.get("extra"), "proceedingsTitle": data.get("proceedingsTitle"),
            "conferenceName": data.get("conferenceName"),
            "creators": [(c.get("family"), c.get("given"), c.get("creatorType"))
                         for c in data.get("creators", [])],
            "tags": [t.get("tag") for t in data.get("tags", [])],
            "matchedBy": reasons,
        }, ensure_ascii=True))
    if n == 0:
        print("FIND_RESULT: no matching items")


# ---------------------------------------------------------------- patch
def cmd_patch(payload_file):
    """payload: {"patches": [{"key","version","body":{...}}, ...]}"""
    if not API_KEY:
        print("PATCH_FAIL: ZOTERO_API_KEY not set")
        sys.exit(1)
    with open(payload_file, encoding="utf-8") as f:
        plan = json.load(f)
    log("\n## patch run %s (%s)" % (datetime.now().isoformat(timespec="seconds"),
                                    payload_file))
    for i, p in enumerate(plan["patches"]):
        key, ver, body = p["key"], p["version"], p["body"]
        # preflight: re-read current item, confirm approved fields still hold
        status, cur = call("GET", "/items/" + key + "?format=json",
                           "patch%02d_%s_preflight" % (i + 1, key))
        if status != 200:
            print("PATCH_ABORT: %s preflight GET HTTP %s" % (key, status))
            sys.exit(3)
        ver_now = cur.get("version")
        if ver_now != ver:
            print("PATCH_ABORT: %s version drifted (plan=%s live=%s) - stopping"
                  % (key, ver, ver_now))
            sys.exit(8)
        cur_data = cur.get("data", {})
        drift = []
        for k, v in p.get("expect_current", {}).items():
            if cur_data.get(k) != v:
                drift.append("%s: approved=%r live=%r" % (k, v, cur_data.get(k)))
        if drift:
            print("PATCH_ABORT: %s fields changed since approval: %s - stopping"
                  % (key, "; ".join(drift)))
            sys.exit(9)
        status, obj = call("PATCH", "/items/" + key, "patch%02d_%s" % (i + 1, key),
                           body=body, version_header=ver)
        if status == 412:
            print("PATCH_ABORT: %s rejected 412 (version conflict) - stopping"
                  % key)
            sys.exit(4)
        if status not in (200, 204):  # Zotero answers 204 No Content on success
            print("PATCH_ABORT: %s HTTP %s - stopping" % (key, status))
            sys.exit(5)
        # read back and verify every patched field + preserved/removed fields
        status, back = call("GET", "/items/" + key + "?format=json",
                            "patch%02d_%s_verify" % (i + 1, key))
        if status != 200:
            print("PATCH_ABORT: %s verify GET HTTP %s" % (key, status))
            sys.exit(6)
        d = back.get("data", {})
        diffs = []
        for k, v in body.items():
            if d.get(k) != v:
                diffs.append("%s: sent=%r got=%r" % (k, v, d.get(k)))
        for k, v in p.get("expect_keep", {}).items():
            if d.get(k) != v:
                diffs.append("keep %s: expected=%r got=%r" % (k, v, d.get(k)))
        for k in p.get("expect_absent", []):
            if d.get(k):
                diffs.append("absent %s: still present %r" % (k, d.get(k)))
        if diffs:
            print("PATCH_MISMATCH %s: %s" % (key, "; ".join(diffs)))
            sys.exit(7)
        print("PATCH_OK %s -> new version %s, %d field(s) set, %d kept, %d absent"
              % (key, back.get("version"), len(body),
                 len(p.get("expect_keep", {})), len(p.get("expect_absent", []))))
    print("PATCH_ALL_OK")


def cmd_verify(payload_file):
    """Read-only: check every patch body/expect_keep/expect_absent against live items."""
    with open(payload_file, encoding="utf-8") as f:
        plan = json.load(f)
    log("\n## verify run %s (%s)"
        % (datetime.now().isoformat(timespec="seconds"), payload_file))
    all_ok = True
    for i, p in enumerate(plan["patches"]):
        key = p["key"]
        status, cur = call("GET", "/items/" + key + "?format=json",
                           "verify%02d_%s" % (i + 1, key))
        if status != 200:
            print("VERIFY_FAIL %s: GET HTTP %s" % (key, status))
            all_ok = False
            continue
        d = cur.get("data", {})
        diffs = []
        for k, v in p["body"].items():
            if d.get(k) != v:
                diffs.append("%s: want=%r got=%r" % (k, v, d.get(k)))
        for k, v in p.get("expect_keep", {}).items():
            if d.get(k) != v:
                diffs.append("keep %s: want=%r got=%r" % (k, v, d.get(k)))
        for k in p.get("expect_absent", []):
            if d.get(k):
                diffs.append("absent %s: still present %r" % (k, d.get(k)))
        if diffs:
            all_ok = False
            print("VERIFY_FAIL %s (version %s): %s"
                  % (key, cur.get("version"), "; ".join(diffs)))
        else:
            print("VERIFY_OK %s (version %s)" % (key, cur.get("version")))
    print("VERIFY_ALL_OK" if all_ok else "VERIFY_INCOMPLETE")
    sys.exit(0 if all_ok else 1)


def cmd_dump(keys):
    """Read-only: GET each item, save raw, print full data (sorted keys)."""
    for i, key in enumerate(keys):
        status, obj = call("GET", "/items/" + key + "?format=json",
                           "dump%02d_%s" % (i + 1, key))
        if status != 200:
            print("DUMP_FAIL %s: HTTP %s" % (key, status))
            sys.exit(2)
        print("=== %s (version %s) ===" % (key, obj.get("version")))
        print(json.dumps(obj.get("data", {}), ensure_ascii=True, indent=1,
                         sort_keys=True))


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "smoke":
        cmd_smoke()
    elif cmd == "find":
        cmd_find()
    elif cmd == "dump":
        if len(sys.argv) < 3:
            print("usage: zotero_client.py dump <key> [<key>...]")
            sys.exit(64)
        cmd_dump(sys.argv[2:])
    elif cmd == "patch":
        if len(sys.argv) < 3:
            print("usage: zotero_client.py patch <payload.json>")
            sys.exit(64)
        cmd_patch(sys.argv[2])
    elif cmd == "verify":
        if len(sys.argv) < 3:
            print("usage: zotero_client.py verify <payload.json>")
            sys.exit(64)
        cmd_verify(sys.argv[2])
    else:
        print("usage: zotero_client.py smoke|find|patch|verify <payload.json>")
        sys.exit(64)


if __name__ == "__main__":
    try:
        main()
    except urllib.error.URLError as e:
        print("NETWORK_FAIL: %s" % e)
        sys.exit(3)
