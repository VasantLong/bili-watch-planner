# 前端内联在单文件里，不做构建

前端只有一屏表格 + 一个筛选栏，用户打开就为看一次时长。为此引入 npm 工具链（打包、热更新、依赖树）会让
「clone 下来直接 `python3 bili_planner.py` 就能跑」这个前提失效，因此 CSS 与 JS 全部内联在 `static/index.html` 里，
由 `http.server` 直接吐文件，无框架、无 CDN。

## Consequences

- 没有模块系统：状态集中在 `state` 对象，函数按 `render` / `load` / `merge` 分组，靠命名维持边界。
- 内联脚本写坏不会被浏览器在构建期拦住，所以有 `scripts/check_ui.py`（`node --check`）兜底，CI 也跑。
- 页面体积约 24 KB，一次请求拿完，部署时不需要反代静态资源。
