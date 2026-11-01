# Bilibili 接口台账（实测）

本项目只用免登录公开接口，只发 `User-Agent` 与 `Referer: https://www.bilibili.com`，不带 Cookie。
下表是 2026-11 实测通过的端点、单位与坑；改抓取逻辑前先读这里，别靠猜。

## 端点

| 用途 | 端点 | 关键参数 | 返回里要什么 |
| --- | --- | --- | --- |
| 分P列表 | `/x/player/pagelist` | `bvid` | `data[]` 的 `page` / `part` / `duration`(秒) / `cid` |
| 稿件详情 | `/x/web-interface/view` | `bvid` 或 `aid` | `title` / `owner.name` / `desc` / `videos` / `duration` / `pages[]` |
| 系列列表 | `/x/series/archives` | `mid` `series_id` `only_normal=true` `sort=desc` `pn` `ps=100` | `data.archives[]`(`bvid`/`title`/`duration`) + `data.page.total` |
| 系列元信息 | `/x/series/series` | `mid` `series_id` | `data.meta.name` / `data.meta.total` |
| 合集列表 | `/x/polymer/web-space/seasons_archives_list` | `mid` `season_id` `page_num` `page_size=100` | 同系列：`data.archives[]` + `data.page.total` |
| 合集元信息 | `/x/polymer/web-space/home/seasons_series` | `mid` `page_num` `page_size=20` | `data.items_lists.seasons_list[].meta`(`season_id`/`name`/`total`) |
| 番剧（未接入） | `/pgc/view/web/season` | `season_id` | `episodes[].duration`(**毫秒**) |

系列与合集的列表返回同形，所以 `fetch_videos_list()` 用两条分支喂同一个形状。

## 单位与含义

- UGC 的 `duration` 一律是**秒**（整数）；番剧 `pgc` 的是**毫秒**（`1551000` = 25.85 分钟）。混用会差 1000 倍。
- 列表里的 `archives[].duration` **等于该稿件全部分P时长之和**（样本系列 21 稿逐条核对，零误差）。
  所以只要总量时，不必逐稿拉分P；要分P标题才需要 `pagelist`。
- `pages[]` 里的分P标题可以跨稿件重名，唯一键必须用 `(bvid, cid)`。
- 存在 10 秒级的「补丁P」（例如「宝箱数从184变为177」），会把平均值拉低；网页端默认可以隐藏 < 30 秒的分P。

## 坑

- `home/seasons_series` 的 `page_size` **只接受 10 或 20**，传 50 直接 `code = -400`。
  另外它按页返回 UP 主的全部系列/合集，要找指定的 `season_id` 得翻页（`_season_meta()` 最多翻 5 页）。
- `seasons_archives_list` 的 `page_size=100` 可用（727 条合集实测通过）；`series/archives` 的 `ps=100` 可用。
- 频繁请求会拿到 `-352`（风控）/ `-412`（请求被拦截）/ `-509`（限流）/ `-799`（请求过频）。
  实测 574 个请求、`delay=0.3` 零失败；大合集建议 `--workers 2 --delay 0.3`。
- 部分番剧 `episodes` 为空（区域/版权限制），拿不到就如实报错，不要伪造。
- `b23.tv` 短链需要跟一次 302 才能拿到真实链接；跟随失败时原样返回，交给 `parse_target()` 报「认不出来」。

## 文档现状

社区非官方文档 `SocialSisterYi/bilibili-API-collect` 已于 **2026-01-28 因法务原因归档**（GitHub 仓库 `archived`），
原站 `socialsisteryi.github.io` 已 404；同生态的 `Nemo2011/bilibili-api`、`nilaoda/BBDown` 也已归档。
目前只有第三方镜像（如 `sessionhu.github.io/bilibili-API-collect`）还在线，内容可能滞后。

**本项目不复刻、不镜像这份文档**：本文件只记录自己实测过的端点与坑。接口随时可能变，以实测为准。
