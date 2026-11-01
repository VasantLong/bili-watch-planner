# 架构

一次解析就是一条单向管线：把一个链接读成「稿件表」，再把每个稿件的分P补齐。没有数据库、没有队列、没有后台任务。

## 管线

```text
raw url
  → expand_short_link()     b23.tv 短链跳一次，失败原样返回
  → parse_target()          分类：video / series / season
  → resolve()               video → fetch_video()；列表 → fetch_videos_list()
  → merge_groups()          多来源按 bvid 去重合并（单来源也走这一步）
  → load_all_parts()        ThreadPoolExecutor 逐稿拉分P + 简介（workers=4）
  → write_outputs() / JSON  写 CSV+MD / 交给 HTTP
```

合并发生在补分P之前，所以重复来源里的同一个稿件只会被抓一次。

## 数据形状

`parse_target()` 的产物（分类结果）：

```python
{"kind": "video",  "bvid": "BV…", "page": 3 | None}
{"kind": "video",  "aid": 123456, "page": None}
{"kind": "series", "mid": 431073645, "oid": 4495895}
{"kind": "season", "mid": 431073645, "oid": 261059}
```

`resolve()` 的产物（来源）：

```python
{"kind": "series", "title": "…", "mid": …, "oid": …, "owner": None,
 "videos": [ {"bvid": …, "title": …, "duration": 秒, "parts": None | [part],
              "url": …, "from": "series-4495895", "referer": …} ],
 "declared_total": 21, "url": …, "source": 原始 url}
```

`merge_groups()` 的产物在单来源时保持原 kind / title，只补 `sources` 数组；多来源时 `kind = "merged"`、
`title = "合并 N 个来源"`，重复稿件带 `also_in`。

分P 项固定四个键：`{"page": int, "part": str, "duration": 秒, "cid": int}`。

## 缓存

`_cache` + `_cache_lock`（进程内 dict，TTL `CACHE_TTL = 600` 秒），三把逻辑 key：

| key | 谁填 | 内容 |
| --- | --- | --- |
| `("resolve", raw)` | `cached_resolve()` | 整份来源（含 videos，不含 parts） |
| `("parts", bvid)` | `cached_parts()` | 该稿件的分P表 |
| `("meta", bvid)` | `cached_meta()` | 标题 / UP / 简介 / 简介链接 |

缓存对象会被并发请求共享，所以任何写回（例如把 parts 填进 video）都必须落在**副本**上：
`/api/resolve` 每次都跑 `merge_groups()` 重新建对象，正是为了不污染缓存。

缓存不落盘，重启即空——这是刻意的，见下方「无状态」。

## 并发与请求礼貌

- `load_all_parts(data, workers=4)` 用线程池按稿件并行；每个线程只发 2 个请求（pagelist + view）。
- `api_get()` 是唯一出口：带 `User-Agent` 与 `Referer`，非 0 code 抛 `BiliError`，网络异常抛 `NetworkError`；
  命中 `-352 / -412 / -509 / -799` 才退避重试（最多 3 次，指数退避）。
- 列表翻页不带 delay（一页 100 条，几十页搞定）；逐稿补分P才需要 `--delay`，大合集建议 `--workers 2 --delay 0.3`。

## HTTP 层

`ThreadingHTTPServer` + 一个 `Handler`，无会话、无鉴权、无持久化：

| 路由 | 行为 | 失败 |
| --- | --- | --- |
| `/`、`/index.html` | 读 `static/index.html`（`_serve_file` 校验父目录，防穿越） | 404 JSON |
| `/api/resolve?url=…` | 重复 url 参数逐个 resolve → merge | 缺参数 400；`UnsupportedInput` 400；`BiliError` 502（带 code） |
| `/api/parts?bvid=…` | 分P + meta + sum；meta 失败降级为 `{"error": …}` 但仍给 parts | bvid 非法 400 |
| `/healthz` | `{"ok": true}` | — |
| 其他 | `{"ok": false, "error": "not found"}` | 404 |

`do_GET` 顶层兜底 `except Exception` → 500 JSON：单个坏请求不许打崩整个服务。

## 前端状态

单个 `state` 对象管全部界面，改完统一 `render()`：

```text
state.data      合并后的来源对象（决定表格行）
state.parts     bvid → [part]（逐稿异步填充，可能为空）
state.meta      bvid → {title, links, desc}（简介 chip 的来源）
state.errored   bvid → 错误串
state.queue     待补分P的 bvid 队列，并发 3（loadPartsQueue）
state.sources   来源条（label + 稿件数）
state.selected  bvid 集合（决定汇总与导出）
state.hideShort 隐藏 < 30 秒分P 的开关
```

`mergeIncoming()` 是「增量追加」的唯一入口，返回 `{added, dupe, dupSource}`：
页面据此说清「追加了几条 / 跳过几条重复 / 来源已在列表里」。

## 为什么无状态

这个工具的产物是一次性观看计划，数据随时可以从 B 站重取；落盘只会带来「数据陈旧」和「要清理」两个问题。
于是：缓存只在内存、导出由用户主动触发、服务端不存任何东西。代价是重启后第一次解析要重抓（约 1–2 秒，大合集按稿件数线性增长）。
