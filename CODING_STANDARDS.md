# Coding Standards

## 项目速览

- 语言/框架：Python 3.9+，纯标准库；前端是单文件原生 JS，无构建步骤。
- 运行：`bash run.sh`（网页）或 `python3 bili_planner.py <URL|BV>`（命令行）。
- 测试：`python3 -m unittest -q test_planner`。
- 语法检查：`python3 scripts/check_ui.py`（前端内联 JS，需 node），CI 另跑 `compileall`。

## 编码标准

### 命名

- 模块级常量全大写下划线（`CACHE_TTL`、`LINK_LIMIT`、`DEFAULT_REFERER`），集中放在文件头部常量区。
- 只在文件内部用的函数加 `_` 前缀（`_http_json`、`_to_parts`、`_int`），对外的（CLI / HTTP / 测试直接调的）不加。
- 测试类以 `Test` 起、方法以 `test_` 起，名字描述行为而不是函数名（`test_duplicate_source_is_ignored`）。
- 对外数据键一律 snake_case，单位写进名字（`duration_s`、`duration_hms`）。

### 模块与文件组织

- 后端逻辑只写在 `bili_planner.py` 单文件里，不新建包或第二模块（理由见 ADR-0001）。
- 前端不新增第二个前端文件、不引 CDN：CSS 与 JS 都内联在 `static/index.html`（ADR-0004）。
- 文件内按「常量 → 解析层 → 合并层 → 网络层 → 抓取层 → 缓存 → HTTP → CLI」分段，段间用 `# ---- #` 分隔注释。

### 错误处理

- 只抛既有的四类异常：`UnsupportedInput`（输入认不出来）、`BiliError`（接口返回非 0 code，带 `.code`）、`NetworkError`（网络层失败）、`OutputError`（写盘失败）。新增错误场景优先复用，不新造类型。
- 所有 B 站请求必须经 `api_get()`，不要在别处直接 `urlopen`（重试、UA、Referer 的收敛点）。
- 禁止 `except Exception: pass`。确实要做降级的地方，必须给调用方留下可判断的痕迹（例如 `/api/parts` 的 `meta` 降级成 `{"error": ...}`）。
- HTTP 处理器里 `except Exception` 只能出现在 `do_GET` 的顶层兜底，且必须返回错误 JSON（500），不许让连接挂掉。

### 数据形状

- `parse_target()` 的返回值必须含 `kind`；`kind == "video"` 时含 `bvid` 或 `aid`，列表类含 `mid` / `oid` / `kind`。
- 解析结果必须含 `kind`、`title`、`videos`、`source`；`videos` 每项必须含 `bvid`、`title`、`duration`、`parts`、`url`。
- 分P 字典的键固定为 `page` / `part` / `duration` / `cid`，不要加临时字段。

### 前端

- 渲染只用 `document.createElement` / `textContent` / `append`；接口数据一律不进 innerHTML。
- 外链只经 `openLink()`：先用白名单（BV 号 / 数字 / b23 短链）重拼 URL，再临时 `<a rel="noopener noreferrer">` 点击。
- 状态集中在 `state` 对象里，改状态后统一 `render()`；不要在事件处理里零散改 DOM。

### 风格

- 字符串格式化用 `%`（与既有代码一致），不要在同一文件里混用 f-string。
- 不加类型注解：数据是 dict 流转，注解只会说谎（ADR-0001）。
- 函数写一行中文 docstring 说意图，不复述函数名；复杂分支才写行内注释。

## 工具强制清单（审查跳过）

- 语法：CI 跑 `python -m compileall`（`.github/workflows/tests.yml`）。
- 前端语法：`scripts/check_ui.py` → `node --check`（本地与 CI 都跑）。
- 没有配置 linter / 格式化器（无 ruff、black、eslint、prettier），因此没有规则可跳过；新增格式化配置时，把它的规则并进本节。

## 测试标准

- 框架：标准库 `unittest`。
- 布局：单测放在仓库根 `test_planner.py`，不放 `tests/` 子目录（保持 `python3 -m unittest test_planner` 可直接运行、无需包结构）。
- 粒度：纯函数必须有单测 —— 链接解析、分P聚合、来源合并与去重、简介链接提取、`hms`、输出写盘。网络请求与 HTTP 路由不写单测，用真实接口做端到端手工验证（`/healthz`、`/api/resolve`、`/api/parts`）。
- 新增行为时先加失败用例，再改实现；用例名说明行为。
