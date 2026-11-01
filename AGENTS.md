# AGENTS.md

B 站观看时长规划工具：贴「系列 / 合集 / BV 号」链接 → 列出稿件与分P时长 → 勾选导出 CSV。
后端纯标准库单文件，前端单页无构建。

## 命令

```bash
bash run.sh                                  # 网页 http://127.0.0.1:8770
python3 bili_planner.py BV1L8xH6pEhr         # 命令行，产物写 out/
python3 -m unittest -q test_planner          # 单测（30 例）
python3 scripts/check_ui.py                  # 前端内联 JS 语法自检（需 node，缺则跳过）
bash scripts/release.sh X.Y.Z [notes.md]     # 发版：改版本号 → 测试 → 提交 → 推 main
```

改过 `static/index.html` **必须**跑 `scripts/check_ui.py`：模板字符串里一个 `\n` 会被写成真换行，
内联 JS 静默变坏，页面白屏但服务端 200（CI 会在 push 后拦下）。

## 文件职责

| 文件 | 职责 |
| --- | --- |
| `bili_planner.py` | 全部后端：输入解析 / 抓取 / 合并 / 输出 / CLI / HTTP 服务（758 行） |
| `static/index.html` | 单页前端：内联 CSS 与 JS，无框架、无构建、无 CDN |
| `test_planner.py` | unittest：纯函数与输出写入 |
| `scripts/release.sh` | 发版入口，也是唯一改版本号的地方 |
| `scripts/check_ui.py` | 从 index.html 抽内联脚本丢给 `node --check` |
| `.github/workflows/` | `tests.yml` 跑单测与前端语法检查；`release.yml` 由版本号建 tag 发 Release |

## 不要让它漂移的契约

- `__version__` 是版本号唯一真相。**不手工 `git tag`、不手工 `gh release create`**，tag 与 Release 只由 CI 建。
- `/api/resolve` 永远返回 `merge_groups()` 的结果，哪怕只有一个 url —— 前端依赖 `from` / `sources` 字段常驻。
- 稿件去重键是 `bvid.upper()`；来源去重键是 `source_label()` 的返回值。
- 分P 的唯一键是 `(bvid, cid)`，不是 `part`：不同稿件的分P标题会重名。
- 前端渲染只走 DOM API（`createElement` / `textContent`），不拼 innerHTML；外链只经 `openLink()` 白名单重拼。
- 抓取只带 `User-Agent` 与 `Referer`，不带 Cookie；只对 `-352/-412/-509/-799` 退避重试。

## 文档分工

| 文件 | 读者 | 放什么 |
| --- | --- | --- |
| `README.md` | 想用它的人 | 怎么用、输出长什么样、接口表、部署、合规 |
| `AGENTS.md`（本文件） | 改它的 agent | 命令、文件职责、不许漂移的契约 |
| `CONTEXT.md` | 人 + agent | 领域术语与禁用同义词 |
| `CODING_STANDARDS.md` | reviewer / agent | 可判定的风格规则 |
| `docs/architecture.md` | 想改内部的人 | 数据在管线里怎么变形、缓存与并发 |
| `docs/bilibili-api.md` | 撞接口问题的人 | 实测接口台账：端点、单位、坑 |
| `docs/adr/` | 好奇「为什么这么设计」的人 | 难回退的决策与取舍 |

## 坑

- 起服务前先 `ss -ltnp | grep 8770`：旧进程占着端口时新进程抛 `OSError: Address already in use`，
  但脚本接着往下跑，所有验证其实打在旧代码上。
- `pkill -f 'bili_planner.py --port 8770'` 会匹配到自己那条命令行而导致自杀。
- 网页端验证要打真实 `/api/resolve`：解析缓存 10 分钟，改代码后旧结果可能还在。

## Agent skills

### Issue tracker

Issues 与 spec 都住在 GitHub Issues（`VasantLong/bili-watch-planner`），用 `gh` 操作。见 `docs/agents/issue-tracker.md`。

### Triage labels

五个规范角色：`needs-triage` / `needs-info` / `ready-for-agent` / `ready-for-human` / `wontfix`。见 `docs/agents/triage-labels.md`。

### Domain docs

单上下文：根 `CONTEXT.md` + `docs/adr/`。见 `docs/agents/domain.md`。

### Coding standards

见 `CODING_STANDARDS.md`。
