# bili-watch-planner

把 B 站的系列、合集或单个稿件读成「稿件 + 分P + 时长」的表，用来规划观看时间。下文术语收紧到本项目里的含义，不是 B 站官方定义的复述。

## 语言

**稿件**：
一个 BV 号对应的视频，是抓取的原子单位；有标题、UP 主、总时长、以及零到多个分P。
_Avoid_: 视频项、条目、item、entry

**分P**：
稿件内部的一段，播放器里的一个 P；字段固定为 `page`（序号）、`part`（标题）、`duration`（秒）、`cid`。
_Avoid_: 分段、章节、segment、clip

**系列 / 合集**：
UP 主把多个稿件归到一起的两种容器，抓取方式不同（系列走 `/x/series/archives`，合集走 `seasons_archives_list`），但在本项目里被读成同一种来源。
_Avoid_: 播放列表、playlist、收藏夹、favorite

**来源**：
一次解析的输入，可以是单个稿件、一个系列或一个合集；多个来源可以合并成一张表。
_Avoid_: 输入、数据源、feed、dataset

**来源标签**：
来源的稳定短名，形如 `series-4495895` / `video-BV1L8xH6pEhr`；它同时是来源去重的键，也写进导出与合并表。
_Avoid_: 来源 ID、source key、origin

**合并**：
把多个来源的稿件按 BV 号去重后并成一张表；重复稿件保留首次出现的 `from`，并在 `also_in` 记下后来命中它的来源。
_Avoid_: 聚合、join、union、concat

**增量追加**：
网页端把新解析结果并进当前列表而不是替换它；不产生新行、不产生新来源的追加要如实告诉用户被跳过了。
_Avoid_: 加载更多、分页、append mode

**stamp**：
导出文件名前缀：单稿件用 BV 号，系列/合集用 `{series|season}-{oid}`，多来源合并用 `merged-{N}src`。
_Avoid_: 文件名前缀、slug、hash

**简介链接**：
稿件简介与分P标题里出现的其他 B 站链接，抽出来供一键追加；自身链接要剔除。
_Avoid_: 描述、desc、外链、related
