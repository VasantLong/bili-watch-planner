# bili-watch-planner · B站观看时间规划器

[![tests](https://github.com/VasantLong/bili-watch-planner/actions/workflows/tests.yml/badge.svg)](https://github.com/VasantLong/bili-watch-planner/actions/workflows/tests.yml)
[![python](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/)
[![license](https://img.shields.io/badge/license-MIT-green)](LICENSE)
![deps](https://img.shields.io/badge/dependencies-0-brightgreen)

贴一个 B 站链接（**系列 / 合集 / 单个 BV 号**都行），立刻看到里面每个稿件的分P标题、时长、占比，
外加"总共要看多久 / 平均每 P 多久"，再用复选框挑出你真正打算看的 P，一键导出 CSV。

纯标准库、零依赖、免登录、不需要 Cookie。

## 能做什么

- **系列 / 合集整包**：给 UP 主主页的系列或合集链接，一次列出全部稿件及其分P。
- **单个视频**：给 BV 号（或 av 号、带 `?p=3` 的链接），列出它的分P。
- **自动跳过补丁P**：隐藏 <30s 的分P（比如"宝箱数从 184 变为 177"这类 12 秒修正），可关闭。
- **简介里的链接**：扫描视频简介和分P标题里提到的其他 B 站视频（BV / av / b23 / 系列），一键加进列表一起统计——攻略系列经常靠简介串起来。
- **增量追加**：解析完一个系列后，勾上「追加到当前列表」再贴下一个链接（系列 / 合集 / 单个 BV 都行），
  新来源按 BV 号去重后并入同一张表，时长、勾选、导出全部按合并后的整体计算；
  同一个链接重复解析不会产生重复视频，也不会在来源条里堆出重复来源。
- **挑选后导出**：勾选任意视频，只按所选导出 CSV，附源视频与来源标签，方便做观看清单。
- **汇总卡片**：已选视频数 / 分P数 / 总时长 / 平均每P。

示例（【原神】一条龙全收集，21 个稿件 / 574 个分P）：总时长 **84:28:59**，平均每个分P约 8.8 分钟。

## 快速开始

需要 Python 3.9+（无第三方依赖）。

### 网页（推荐）

```bash
bash run.sh                 # http://127.0.0.1:8770
bash run.sh --port 9000     # 换端口
```

打开页面，粘贴链接，回车。也支持直接带参数打开：`http://127.0.0.1:8770/?url=<链接>`。

### 命令行

```bash
# 系列 / 合集 —— 逐稿抓分P
python3 bili_planner.py 'https://space.bilibili.com/431073645/lists/4495895?type=series' --out out

# 单个视频
python3 bili_planner.py BV1L8xH6pEhr --out out

# 多个来源合并成一份记录（增量解析的命令行形态）
python3 bili_planner.py BV1L8xH6pEhr BV1xw4m1v7cf --out out
python3 bili_planner.py 'https://space.bilibili.com/431073645/lists/4495895?type=series' \
    'https://space.bilibili.com/431073645/lists/3533058?type=season' --out out

# 只出稿件级汇总（不逐稿抓分P，秒回，适合大型合集）
python3 bili_planner.py 'https://space.bilibili.com/431073645/lists/261059?type=season' --no-parts

# 输出 stdout JSON
python3 bili_planner.py BV1L8xH6pEhr --json
```

常用参数：`--out DIR`（默认 `out`）、`--workers N`（并发，默认 4）、`--delay S`（每请求间隔，默认 0）、`--no-desc`（跳过简介扫描）、`--no-parts`、`--json`、`--version`。

## 输入格式

| 形式 | 例子 |
| --- | --- |
| 系列 / 合集 | `https://space.bilibili.com/<mid>/lists/<oid>?type=series`（或 `type=season`） |
| 老版收藏夹入口 | `https://space.bilibili.com/<mid>/channel/collectiondetail?sid=<sid>` |
| 单个视频 | `BV1L8xH6pEhr`、`av123456`、`https://www.bilibili.com/video/BV1L8xH6pEhr?p=3` |

## 输出

CLI 会在 `--out` 目录写三份（网页端用浏览器导出）：

- `{stamp}-parts.csv` — `bvid,video_title,page,part_title,duration_s,duration_hms,cid,source`
- `{stamp}-summary.md` — 汇总表（含来源列）+ 来源清单 + 简介/分P里提到的其他 B 站链接
- `{stamp}-links.csv` — `source_bvid,source_title,kind,target,url`

`stamp`：单视频用 BV 号，系列/合集用 `{series|season}-{oid}`，多来源合并用 `merged-{N}src`。
`source` 列是来源标签（`series-4495895` / `video-BV…`），合并后仍能看清每个 P 来自哪个链接。

## 网页界面

暗色单页，原生 JS，无框架、无构建：

- 行内复选框筛选要看的视频；表头三态复选框全选/全不选。
- 「追加到当前列表」：解析结果并入现有列表（BV 号去重），顶部来源条列出每条来源与稿件数。
- 每行分P用总时长降序，长 P 一眼可见。
- 简介链接以 chip 呈现：点文字在新标签打开，点 `+` 追加到当前列表。
- "隐藏 <30s 分P"开关、"导出所选 CSV"按钮。

后端接口（同一进程提供）：

| 接口 | 说明 |
| --- | --- |
| `GET /` | 单页应用 |
| `GET /api/resolve?url=` | 解析链接 → 稿件列表（系列/合集/单视频），4 分钟内缓存 |
| `GET /api/resolve?url=A&url=B` | 多个 url 参数 → 服务端合并（按 BV 去重），返回 `kind=merged` |
| `GET /api/parts?bvid=` | 单个稿件的分P + 简介链接 + 总时长 |
| `GET /healthz` | 存活探测 |

## 风控与请求礼貌

- 免登录走公开接口，不携带 Cookie；只发 `User-Agent` 与 `Referer: https://www.bilibili.com`。
- 遇到 `-352` / `-412` / `-509` / `-799` 自动退避重试（3 次，指数退避）。
- 并发默认 4；抓大合集建议 `--workers 2 --delay 0.3`。
- 结果在进程内缓存 10 分钟，避免反复打同一接口。

## 部署到自己的网站

单文件服务，任何能跑 Python 的地方都行：

```bash
nohup python3 bili_planner.py --host 127.0.0.1 --port 8770 > /tmp/bili-planner.log 2>&1 &
```

- 默认只监听 `127.0.0.1`，对外请用 Nginx / Caddy 反代并加 HTTPS。
- 本服务无鉴权、无速率限制、无持久化——公网暴露前请在反代层加限流（例如 `limit_req`），或加一层访问口令。
- 进程内缓存不落盘，重启即空；适合"工具型"小站，不适合高并发。

## 项目结构

```text
bili_planner.py     # 抓取 + 聚合 + CLI + HTTP 服务（纯标准库）
static/index.html   # 单页前端（内联 CSS/JS）
test_planner.py     # unittest 用例（解析 / 聚合 / 合并 / 链接提取 / 输出）
run.sh              # 启动脚本
scripts/release.sh  # 发版：改版本号 + 跑测试 + 推 main（tag 与 Release 交给 CI）
scripts/check_ui.py # 前端内联脚本语法自检（node --check）
.github/workflows/  # CI：tests.yml 跑单测；release.yml 按 __version__ 自动打 tag 发 Release
```

## 测试

```bash
python3 -m unittest -v test_planner
```

30 个用例，覆盖输入解析、时长聚合、多来源合并去重、链接提取、输出写入。

前端没有构建步骤，改过 `static/index.html` 记得跑 `python3 scripts/check_ui.py`（用 `node --check`
兜住模板字符串把 JS 写坏的坑，CI 也会跑）。

## 发版

版本号只有一个来源：`bili_planner.py` 里的 `__version__`。**不要手工 `git tag` 或 `gh release create`。**

```bash
bash scripts/release.sh 1.1.2            # 改版本号 → 跑测试 → 提交 → 推 main
bash scripts/release.sh 1.1.2 notes.md   # 顺带把发布说明写进 release-notes/v1.1.2.md
bash scripts/release.sh 1.1.2 --no-push  # 只准备提交，不推
```

推上去之后 `.github/workflows/release.yml` 会：读 `__version__` → 跑测试 → tag `v1.1.2` → 发 Release
（有 `release-notes/v1.1.2.md` 就用它，否则自动生成）。若已有同名 tag 却又有产品代码改动，
workflow 会直接失败，提醒你补版本号——代码版本、tag、Release 三者始终一致。

## 已知限制

- 番剧（`/bangumi/play/`）暂不解析；其接口时长单位是毫秒，与 UGC 的秒不同，需要单独处理。
- 部分番剧/区域受限稿件取不到分P。
- 系列内稿件总数很大时（千级），逐稿抓分P会比较慢，建议先 `--no-parts` 看总量。
- 只读公开数据，不做下载、不做去水印、不绕任何限制。

## 合规与免责

- 本项目仅调用 bilibili 网页端公开 JSON 接口读取**公开可见**的视频元信息，用于个人观看规划。
- 不存储、不分发视频内容；`out/` 与导出的 CSV 已加入 `.gitignore`，请不要把抓取结果提交到仓库。
- 请控制请求频率，勿用于批量爬取或任何商业用途。
- 接口随时可能变更或收紧，本项目不保证长期可用；与 bilibili 官方无关。
- 非官方社区 API 文档（SocialSisterYi/bilibili-API-collect）已于 2026-01-28 因法务原因归档，本项目不复刻、不镜像其文档内容。

## License

[MIT](LICENSE) © 2026 VasantLong
