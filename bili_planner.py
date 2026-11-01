#!/usr/bin/env python3
"""bili_planner — 抓取 B 站视频 / 系列 / 合集的分P标题与时长，网页或终端呈现。

用法:
    python3 bili_planner.py                 # 启动网页 http://127.0.0.1:8770
    python3 bili_planner.py <链接或BV号>    # 终端模式，导出 CSV + Markdown

只依赖标准库。接口免登录，仅带 UA + Referer；内置限速与重试以规避 -352/-412 风控。
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
API = "https://api.bilibili.com"
DEFAULT_REFERER = "https://www.bilibili.com"
ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "static"
CACHE_TTL = 600
__version__ = "1.1.1"

BV_RE = re.compile(r"BV([0-9A-Za-z]{10})", re.IGNORECASE)
AV_RE = re.compile(r"\bav(\d+)", re.IGNORECASE)
PAGE_RE = re.compile(r"[?&]p=(\d+)")
COLLECTION_RE = re.compile(r"space\.bilibili\.com/(\d+)/channel/collectiondetail\?(?:[^#]*&)?sid=(\d+)")
LISTS_RE = re.compile(r"space\.bilibili\.com/(\d+)/lists/(\d+)(?:\?[^#\s]*type=(\w+))?")
SHORT_RE = re.compile(r"b23\.tv/([0-9A-Za-z]{4,16})")
LINK_LIMIT = 60


class UnsupportedInput(ValueError):
    """输入既不是 BV/av，也不是受支持的系列/合集链接。"""


class BiliError(RuntimeError):
    """B站接口返回非 0 code。"""

    def __init__(self, code, message):
        super().__init__("B站接口返回 code=%s: %s" % (code, message))
        self.code = code
        self.message = message


# --------------------------------------------------------------------------- #
# 纯函数：输入解析 / 时长格式化 / 汇总
# --------------------------------------------------------------------------- #
def _int(value, default=0):
    """宽松转 int：非数字回落到默认值，避免坏数据打崩汇总。"""
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return default


def parse_target(raw):
    """把用户输入解析成 {kind: video|series|season, ...}。"""
    if not isinstance(raw, str) or not raw.strip():
        raise UnsupportedInput("请输入 BV 号或分享链接")
    s = raw.strip()
    s = re.sub(r"\\s+", "", s)

    m = COLLECTION_RE.search(s)
    if m:
        return {"kind": "season", "mid": _int(m.group(1)), "oid": _int(m.group(2))}

    m = LISTS_RE.search(s)
    if m:
        kind = "season" if (m.group(3) or "series").lower() == "season" else "series"
        return {"kind": kind, "mid": _int(m.group(1)), "oid": _int(m.group(2))}

    if "space.bilibili.com" in s:
        raise UnsupportedInput(
            "只支持 UP 主的「系列 / 合集」链接，例如 "
            "https://space.bilibili.com/431073645/lists/4495895?type=series"
        )

    m = BV_RE.search(s)
    if m:
        page = PAGE_RE.search(s)
        return {"kind": "video", "bvid": "BV" + m.group(1),
                "page": _int(page.group(1)) if page else None}

    m = AV_RE.search(s)
    if m:
        page = PAGE_RE.search(s)
        return {"kind": "video", "aid": _int(m.group(1)),
                "page": _int(page.group(1)) if page else None}

    raise UnsupportedInput("认不出来：请贴 BV 号（BV1xxxxxxxxx）或系列/合集链接")


LINK_SCAN_RE = re.compile(
    r"(?P<lists>space\.bilibili\.com/(?P<mid>\d+)/lists/(?P<oid>\d+)"
    r"(?:\?[^#\s]*type=(?P<type>\w+))?)"
    r"|(?P<collect>space\.bilibili\.com/(?P<cmid>\d+)/channel/collectiondetail\?(?:[^#\s]*&)?sid=(?P<coid>\d+))"
    r"|(?P<bv>BV(?P<bvid>[0-9A-Za-z]{10}))"
    r"|(?P<av>\bav(?P<aid>\d+))"
    r"|(?P<short>b23\.tv/(?P<slug>[0-9A-Za-z]{4,16}))",
    re.IGNORECASE)


def extract_bili_links(*texts, exclude=None):
    """从简介 / 分P标题里挑出 B 站链接，按出现顺序返回并去重。

    返回 [{kind, label, url, bvid|aid|mid+oid}]；exclude 用于剔除自引用（本稿 BV 号）。
    """
    links = []
    seen = set()

    def push(key, item):
        if key in seen or len(links) >= LINK_LIMIT:
            return
        seen.add(key)
        links.append(item)

    skip = str(exclude).lower() if exclude else None
    for text in texts:
        if not isinstance(text, str) or not text:
            continue
        for m in LINK_SCAN_RE.finditer(text):
            if m.group("lists"):
                oid = _int(m.group("oid"))
                kind = "season" if (m.group("type") or "series").lower() == "season" else "series"
                push(("list", m.group("mid"), oid, kind),
                     {"kind": kind, "mid": _int(m.group("mid")), "oid": oid,
                      "label": ("合集 %d" if kind == "season" else "系列 %d") % oid,
                      "url": "https://space.bilibili.com/%s/lists/%d?type=%s"
                             % (m.group("mid"), oid, kind)})
            elif m.group("collect"):
                oid = _int(m.group("coid"))
                push(("list", m.group("cmid"), oid, "season"),
                     {"kind": "season", "mid": _int(m.group("cmid")), "oid": oid,
                      "label": "合集 %d" % oid,
                      "url": "https://space.bilibili.com/%s/lists/%d?type=season"
                             % (m.group("cmid"), oid)})
            elif m.group("bv"):
                bvid = "BV" + m.group("bvid")
                if skip and bvid.lower() == skip:
                    continue
                push(("bv", bvid.lower()),
                     {"kind": "video", "bvid": bvid, "label": bvid,
                      "url": "https://www.bilibili.com/video/" + bvid})
            elif m.group("av"):
                aid = _int(m.group("aid"))
                push(("av", aid), {"kind": "video", "aid": aid, "label": "av%d" % aid,
                                   "url": "https://www.bilibili.com/video/av%d" % aid})
            elif m.group("short"):
                slug = m.group("slug")
                push(("short", slug.lower()), {"kind": "short", "label": "b23.tv/" + slug,
                                               "url": "https://b23.tv/" + slug})
    return links


def hms(seconds):
    """秒 → H:MM:SS。"""
    try:
        total = int(round(float(seconds or 0)))
    except (TypeError, ValueError):
        total = 0
    return "%d:%02d:%02d" % (total // 3600, total % 3600 // 60, total % 60)


def aggregate(videos):
    """汇总分P数量与总时长；parts 为 None/空 视为未加载。"""
    parts_total = 0
    duration_total = 0
    with_parts = 0
    pending = 0
    for v in videos:
        parts = v.get("parts")
        if not parts:
            pending += 1
            continue
        with_parts += 1
        parts_total += len(parts)
        duration_total += sum(_int(p.get("duration")) for p in parts)
    return {"videos": len(videos), "parts_total": parts_total,
            "duration_total": duration_total, "videos_with_parts": with_parts,
            "videos_pending": pending}


def source_label(data):
    """给一个来源起稳定短标签：CSV 的 source 列、前端的来源条都用它。"""
    videos = data.get("videos") or []
    if data.get("kind") == "video" and videos:
        return "video-" + str(videos[0].get("bvid") or "?")
    if data.get("kind") in ("series", "season") and data.get("oid") is not None:
        return "%s-%s" % (data["kind"], data["oid"])
    return str(data.get("kind") or "list")


def merge_groups(groups):
    """把多个解析结果合并成一份统一记录：按 bvid 去重，先到先得、缺的分P可回填。

    单个来源保持原结构（kind/oid 不变）；多个来源 kind='merged'。
    每个稿件带 from（首次出现的来源标签）与 referer（该来源的 Referer）。
    """
    groups = [g for g in groups if isinstance(g, dict)]
    videos = []
    index = {}
    sources = []
    seen_src = set()
    for data in groups:
        label = source_label(data)
        batch = data.get("videos") or []
        referer = data.get("source") or data.get("url")
        if label not in seen_src:  # 同一个链接解析两次：来源只记一条
            seen_src.add(label)
            sources.append({"label": label, "kind": data.get("kind"),
                            "title": data.get("title"), "count": len(batch),
                            "url": data.get("url") or referer})
        for video in batch:
            key = str(video.get("bvid") or "").upper()
            if not key:
                continue
            if key in index:
                held = index[key]
                if not held.get("parts") and video.get("parts"):
                    held["parts"] = video["parts"]
                for field in ("links", "desc", "owner", "error"):
                    if not held.get(field) and video.get(field):
                        held[field] = video[field]
                if held.get("from") != label:
                    held.setdefault("also_in", []).append(label)
                continue
            item = dict(video)
            item["from"] = label
            if not item.get("parts"):
                item["parts"] = None
            if referer:
                item["referer"] = referer
            index[key] = item
            videos.append(item)
    if not groups:
        return {"kind": "merged", "title": "没有来源", "videos": [], "sources": []}
    if len(sources) == 1:  # 只有一个实际来源（含同链接重复解析）：保持原结构
        merged = dict(groups[0])
        merged["videos"] = videos
        merged["sources"] = sources
        return merged
    return {"kind": "merged", "title": "合并 %d 个来源" % len(sources),
            "videos": videos, "sources": sources,
            "source": groups[0].get("source") or groups[0].get("url")}


# --------------------------------------------------------------------------- #
# 网络层
# --------------------------------------------------------------------------- #
class NetworkError(RuntimeError):
    """底层网络失败或返回非 JSON，可重试。"""


class OutputError(RuntimeError):
    """写文件失败（目录不可写、磁盘满等）。"""


def _http_json(url, referer=DEFAULT_REFERER, timeout=20):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Referer": referer,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise NetworkError("请求失败: %s" % (exc,)) from exc
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise NetworkError("返回不是合法 JSON: %s" % (exc,)) from exc


def api_get(path, params=None, referer=DEFAULT_REFERER, retries=3, delay=0.3):
    url = API + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    last = None
    for attempt in range(retries):
        try:
            data = _http_json(url, referer=referer)
        except NetworkError as exc:
            last = exc
            time.sleep(delay * (attempt + 2))
            continue
        code = data.get("code")
        if code == 0:
            return data
        if code in (-352, -412, -509, -799):
            last = BiliError(code, data.get("message", "风控/限速"))
            time.sleep(delay * (attempt + 2) * 3)
            continue
        raise BiliError(code, data.get("message", ""))
    if isinstance(last, BiliError):
        raise last
    raise BiliError(-1, "网络请求失败: %s" % (last,))


def expand_short_link(raw):
    """把 b23.tv 短链展成真实 URL（不跟随则原样返回）。"""
    if "b23.tv" not in raw:
        return raw
    url = raw if raw.startswith("http") else "https://" + raw
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.geturl()
    except (urllib.error.URLError, TimeoutError):
        return raw


def _to_parts(pages):
    return [{"page": p.get("page"), "part": p.get("part"),
             "duration": _int(p.get("duration")), "cid": p.get("cid")}
            for p in pages or []]


def fetch_parts(bvid, referer=DEFAULT_REFERER):
    data = api_get("/x/player/pagelist", {"bvid": bvid}, referer=referer)
    return _to_parts(data.get("data"))


def fetch_video(target):
    params = {"bvid": target["bvid"]} if target.get("bvid") else {"aid": target["aid"]}
    data = api_get("/x/web-interface/view", params)["data"]
    bvid = data["bvid"]
    desc = data.get("desc") or ""
    return {"bvid": bvid, "title": data.get("title"), "owner": (data.get("owner") or {}).get("name"),
            "duration": data.get("duration"), "videos": data.get("videos"),
            "parts": _to_parts(data.get("pages")),
            "desc": desc,
            "links": extract_bili_links(desc, target.get("bvid") or bvid, exclude=bvid),
            "url": "https://www.bilibili.com/video/" + bvid,
            "focus_page": target.get("page")}


def fetch_meta(bvid, referer=DEFAULT_REFERER):
    """稿件元信息：标题 / UP / 简介 / 简介与分P标题里提到的 B 站链接。"""
    data = api_get("/x/web-interface/view", {"bvid": bvid}, referer=referer)["data"]
    real = data.get("bvid") or bvid
    desc = data.get("desc") or ""
    part_titles = [p.get("part") for p in data.get("pages") or []]
    return {"bvid": real, "title": data.get("title"), "owner": (data.get("owner") or {}).get("name"),
            "duration": data.get("duration"), "videos": data.get("videos"),
            "desc": desc, "links": extract_bili_links(desc, *part_titles, exclude=real)}


def _series_meta(mid, oid, referer):
    try:
        data = api_get("/x/series/series", {"mid": mid, "series_id": oid}, referer=referer)
        meta = data["data"]["meta"]
        return meta.get("name"), meta.get("total")
    except (BiliError, KeyError, TypeError):
        return None, None


def _season_meta(mid, oid, referer):
    # page_size 只接受 10/20（50 会 -400），故按 20 翻页找目标 season。
    page = 1
    while page <= 5:
        try:
            data = api_get("/x/polymer/web-space/home/seasons_series",
                           {"mid": mid, "page_num": page, "page_size": 20}, referer=referer)
        except BiliError:
            return None, None
        lists = ((data.get("data") or {}).get("items_lists") or {})
        for item in lists.get("seasons_list") or []:
            meta = item.get("meta") or {}
            if meta.get("season_id") == oid:
                return meta.get("name"), meta.get("total")
        pages = (lists.get("page") or {}).get("total") or 0
        if page >= pages:
            return None, None
        page += 1
    return None, None


def fetch_videos_list(target, delay=0.0):
    mid, oid, kind = target["mid"], target["oid"], target["kind"]
    referer = "https://space.bilibili.com/%d/lists/%d?type=%s" % (mid, oid, kind)
    path = ("/x/series/archives" if kind == "series"
            else "/x/polymer/web-space/seasons_archives_list")
    videos = []
    page = 1
    total = None
    while True:
        if kind == "series":
            params = {"mid": mid, "series_id": oid, "only_normal": "true",
                      "sort": "desc", "pn": page, "ps": 100}
        else:
            params = {"mid": mid, "season_id": oid, "page_num": page, "page_size": 100}
        data = api_get(path, params, referer=referer)
        payload = data.get("data") or {}
        batch = payload.get("archives") or []
        page_info = payload.get("page") or {}
        total = page_info.get("total", total)
        for item in batch:
            bvid = item.get("bvid")
            videos.append({"bvid": bvid, "title": item.get("title"),
                           "duration": item.get("duration"), "parts": None,
                           "url": "https://www.bilibili.com/video/" + (bvid or "")})
        if not batch or (total is not None and len(videos) >= total):
            break
        page += 1
        if delay:
            time.sleep(delay)
    name, _ = (_series_meta(mid, oid, referer) if kind == "series"
               else _season_meta(mid, oid, referer))
    label = "系列" if kind == "series" else "合集"
    return {"kind": kind, "title": name or ("%s %d" % (label, oid)), "mid": mid, "oid": oid,
            "owner": None, "videos": videos, "declared_total": total,
            "url": referer, "source": referer}


def resolve(raw):
    """入口：任意受支持的输入 → 统一结构。"""
    expanded = expand_short_link(raw)
    target = parse_target(expanded)
    if target["kind"] == "video":
        video = fetch_video(target)
        return {"kind": "video", "title": video["title"], "owner": video.get("owner"),
                "videos": [video], "source": expanded, "url": video["url"],
                "focus_page": video.get("focus_page")}
    result = fetch_videos_list(target)
    result["source"] = expanded
    return result


# --------------------------------------------------------------------------- #
# 缓存
# --------------------------------------------------------------------------- #
_cache = {}
_cache_lock = threading.Lock()


def _cached(key, producer, ttl=CACHE_TTL):
    now = time.time()
    with _cache_lock:
        hit = _cache.get(key)
        if hit and now - hit[0] < ttl:
            return hit[1]
    value = producer()
    with _cache_lock:
        _cache[key] = (now, value)
    return value


def cached_resolve(raw):
    return _cached("resolve:" + raw.strip(), lambda: resolve(raw))


def cached_parts(bvid):
    return _cached("parts:" + bvid, lambda: fetch_parts(bvid))


def cached_meta(bvid):
    return _cached("meta:" + bvid, lambda: fetch_meta(bvid))


# --------------------------------------------------------------------------- #
# HTTP 服务
# --------------------------------------------------------------------------- #
CONTENT_TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
                 ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml", ".ico": "image/x-icon"}


class Handler(BaseHTTPRequestHandler):
    server_version = "bili-planner/" + __version__

    def log_message(self, format, *args):
        sys.stderr.write("[http] " + (format % args) + "\n")

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, payload, code=200):
        self._send(code, json.dumps(payload, ensure_ascii=False).encode("utf-8"))

    def _serve_file(self, path):
        root = STATIC_DIR.resolve()
        target = path.resolve()
        if root != target.parent or not target.is_file():
            return self._json({"ok": False, "error": "缺少文件 " + path.name}, 404)
        ctype = CONTENT_TYPES.get(target.suffix, "application/octet-stream")
        try:
            body = target.read_bytes()
        except OSError as exc:
            return self._json({"ok": False, "error": "读取失败: %s" % (exc,)}, 500)
        self._send(200, body, ctype)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)
        try:
            if parsed.path in ("/", "/index.html"):
                return self._serve_file(STATIC_DIR / "index.html")
            if parsed.path == "/api/resolve":
                targets = [u.strip() for u in (query.get("url") or []) if u.strip()]
                if not targets:
                    return self._json({"ok": False, "error": "缺少 url 参数"}, 400)
                data = merge_groups([cached_resolve(u) for u in targets])
                return self._json({"ok": True, "data": data})
            if parsed.path == "/api/parts":
                bvid = (query.get("bvid") or [""])[0]
                if not re.fullmatch(r"BV[0-9A-Za-z]{10}", bvid):
                    return self._json({"ok": False, "error": "bvid 非法"}, 400)
                parts = cached_parts(bvid)
                meta = None
                try:
                    meta = cached_meta(bvid)
                except (BiliError, NetworkError) as exc:
                    meta = {"error": str(exc)}
                return self._json({"ok": True, "bvid": bvid, "parts": parts, "meta": meta,
                                   "sum": sum(p["duration"] for p in parts)})
            if parsed.path == "/healthz":
                return self._json({"ok": True})
            return self._json({"ok": False, "error": "not found"}, 404)
        except UnsupportedInput as exc:
            self._json({"ok": False, "error": str(exc)}, 400)
        except BiliError as exc:
            self._json({"ok": False, "error": str(exc), "code": exc.code}, 502)
        except Exception as exc:  # 顶层兜底：单个请求异常不应打崩整个服务
            self._json({"ok": False, "error": "%s: %s" % (type(exc).__name__, exc)}, 500)


def serve(host="127.0.0.1", port=8770):
    httpd = ThreadingHTTPServer((host, port), Handler)
    print("网页已启动: http://%s:%d   （Ctrl-C 退出）" % (host, port), file=sys.stderr)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n已退出", file=sys.stderr)
    finally:
        httpd.server_close()


# --------------------------------------------------------------------------- #
# 终端模式
# --------------------------------------------------------------------------- #
def _load_one(bvid, referer, with_meta):
    """一次抓一个稿件：分P 必取，元信息（含简介链接）尽力而为。"""
    parts = fetch_parts(bvid, referer)
    meta = None
    if with_meta:
        try:
            meta = fetch_meta(bvid, referer)
        except (BiliError, NetworkError):
            meta = None
    return parts, meta


def load_all_parts(data, workers=4, delay=0.0, with_meta=True):
    fallback = data.get("source") or DEFAULT_REFERER
    pending = [v for v in data["videos"] if not v.get("parts")]
    if not pending:
        return data
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {}
        for video in pending:
            if delay:
                time.sleep(delay)
            referer = video.get("referer") or fallback
            futures[pool.submit(_load_one, video["bvid"], referer, with_meta)] = video
        for future in as_completed(futures):
            video = futures[future]
            try:
                parts, meta = future.result()
                video["parts"] = parts
                if meta:
                    video["desc"] = meta.get("desc")
                    video["links"] = meta.get("links") or []
                    if not video.get("owner"):
                        video["owner"] = meta.get("owner")
            except (BiliError, NetworkError) as exc:
                video["parts"] = []
                video["error"] = str(exc)
    return data


def write_outputs(data, out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    if data.get("kind") == "video" and data["videos"]:
        stamp = data["videos"][0]["bvid"]
    elif data.get("kind") == "merged":
        stamp = "merged-%dsrc" % len(data.get("sources") or [])
    else:
        stamp = "%s-%s" % (data.get("kind", "list"), data.get("oid") or "list")
    rows = []
    for video in data["videos"]:
        for part in video.get("parts") or []:
            rows.append({"bvid": video["bvid"], "video_title": video.get("title"),
                         "page": part["page"], "part_title": part["part"],
                         "duration_s": part["duration"], "duration_hms": hms(part["duration"]),
                         "cid": part["cid"],
                         "source": video.get("from") or data.get("kind")})
    csv_path = out / (stamp + "-parts.csv")
    try:
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=["bvid", "video_title", "page", "part_title",
                                                        "duration_s", "duration_hms", "cid", "source"])
            writer.writeheader()
            writer.writerows(rows)
    except OSError as exc:
        raise OutputError("写 CSV 失败: %s" % (exc,)) from exc

    link_rows = []
    for video in data["videos"]:
        for item in video.get("links") or []:
            link_rows.append({"source_bvid": video["bvid"], "source_title": video.get("title"),
                              "kind": item.get("kind"), "target": item.get("label"),
                              "url": item.get("url")})
    links_path = None
    if link_rows:
        links_path = out / (stamp + "-links.csv")
        try:
            with open(links_path, "w", newline="", encoding="utf-8-sig") as handle:
                writer = csv.DictWriter(handle, fieldnames=["source_bvid", "source_title",
                                                            "kind", "target", "url"])
                writer.writeheader()
                writer.writerows(link_rows)
        except OSError as exc:
            raise OutputError("写简介链接 CSV 失败: %s" % (exc,)) from exc

    agg = aggregate(data["videos"])
    lines = ["# " + str(data.get("title")), "",
             "- 视频 %d，分P %d，总时长 %s（%.2f h）" % (
                 agg["videos"], agg["parts_total"], hms(agg["duration_total"]),
                 agg["duration_total"] / 3600),
             "- 1.25x %s ｜ 1.5x %s ｜ 2x %s" % (
                 hms(agg["duration_total"] / 1.25), hms(agg["duration_total"] / 1.5),
                 hms(agg["duration_total"] / 2)), "",
             "| # | BV | 分P | 时长 | 来源 | 标题 |", "|---|---|---|---|---|---|"]
    for idx, video in enumerate(data["videos"], 1):
        dur = sum(p["duration"] for p in video.get("parts") or [])
        lines.append("| %d | %s | %d | %s | %s | %s |" % (
            idx, video["bvid"], len(video.get("parts") or []), hms(dur),
            video.get("from") or "", video.get("title")))
    if data.get("sources") and len(data["sources"]) > 1:
        lines += ["", "## 来源", "", "| 标签 | 类型 | 数量 | 标题 |", "|---|---|---|---|"]
        for src in data["sources"]:
            lines.append("| %s | %s | %d | %s |" % (src.get("label"), src.get("kind"),
                                                    src.get("count") or 0, src.get("title")))
    if link_rows:
        lines += ["", "## 简介 / 分P标题里提到的其他 B 站链接", "",
                  "| 来源视频 | 类型 | 链接 |", "|---|---|---|"]
        for row in link_rows:
            lines.append("| %s | %s | %s |" % (row["source_bvid"], row["kind"], row["url"]))
    md_path = out / (stamp + "-summary.md")
    try:
        md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError as exc:
        raise OutputError("写 Markdown 失败: %s" % (exc,)) from exc
    return csv_path, md_path, links_path


def run_cli(sources, out_dir, workers, delay, as_json, with_meta=True, with_parts=True):
    if isinstance(sources, str):
        sources = [sources]
    groups = [cached_resolve(raw) for raw in sources]
    data = merge_groups(groups)
    if with_parts:
        data = load_all_parts(data, workers=workers, delay=delay, with_meta=with_meta)
    else:
        for video in data["videos"]:
            video["parts"] = []
    if not with_meta:
        for video in data["videos"]:
            video.setdefault("links", [])
    if as_json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    agg = aggregate(data["videos"])
    print("%s  [%s]" % (data.get("title"), data.get("kind")))
    if len(sources) > 1:
        for src in data.get("sources") or []:
            print("  来源 %-22s %4d 稿  %s" % (src.get("label"), src.get("count") or 0,
                                              src.get("title")))
    print("%-13s %3s %11s  %s" % ("BV", "P", "时长", "标题"))
    for video in data["videos"]:
        dur = sum(p["duration"] for p in video.get("parts") or [])
        print("%-13s %3d %11s  %s" % (video["bvid"], len(video.get("parts") or []),
                                      hms(dur), (video.get("title") or "")[:48]))
    print("-" * 78)
    print("视频 %d ｜ 分P %d ｜ 总计 %s (%.2f h) ｜ 1.25x %s ｜ 1.5x %s ｜ 2x %s" % (
        agg["videos"], agg["parts_total"], hms(agg["duration_total"]),
        agg["duration_total"] / 3600, hms(agg["duration_total"] / 1.25),
        hms(agg["duration_total"] / 1.5), hms(agg["duration_total"] / 2)))
    failures = [v for v in data["videos"] if v.get("error")]
    if failures:
        print("失败 %d 个:" % len(failures), ", ".join(v["bvid"] for v in failures))
    link_total = sum(len(v.get("links") or []) for v in data["videos"])
    if with_meta:
        print("简介链接 %d 条" % link_total)
    csv_path, md_path, links_path = write_outputs(data, out_dir)
    print("CSV:", csv_path)
    print("MD :", md_path)
    if links_path:
        print("LINK:", links_path)


def main(argv=None):
    parser = argparse.ArgumentParser(description="B站分P观看时长规划")
    parser.add_argument("sources", nargs="*", metavar="URL",
                        help="BV 号 / 视频链接 / 系列或合集链接，可给多个并合并；不填则启动网页")
    parser.add_argument("--version", action="version", version="bili-planner " + __version__)
    parser.add_argument("--port", type=int, default=8770)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--out", default="out", help="终端模式的输出目录")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--delay", type=float, default=0.0, help="每个请求之间的间隔秒数")
    parser.add_argument("--json", action="store_true", help="终端模式额外打印原始 JSON")
    parser.add_argument("--no-desc", action="store_true",
                        help="不抓稿件简介（省一半请求，跳过简介链接提取）")
    parser.add_argument("--no-parts", action="store_true",
                        help="只出稿件级汇总，不逐稿抓分P（大合集秒回）")
    args = parser.parse_args(argv)
    if not args.sources:
        return serve(args.host, args.port)
    try:
        run_cli(args.sources, args.out, args.workers, args.delay, args.json,
                with_meta=not args.no_desc, with_parts=not args.no_parts)
    except UnsupportedInput as exc:
        print("输入有误: " + str(exc), file=sys.stderr)
        return 2
    except BiliError as exc:
        print("接口失败: " + str(exc), file=sys.stderr)
        return 3
    except OutputError as exc:
        print("写文件失败: " + str(exc), file=sys.stderr)
        return 4
    return 0


if __name__ == "__main__":
    sys.exit(main())
