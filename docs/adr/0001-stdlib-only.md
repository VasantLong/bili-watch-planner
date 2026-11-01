# 纯标准库单文件后端

本工具是给人临时用一次的小工具，要被丢到任何一台有 Python 的机器（含只有 3.9 的老环境、没有 pip 权限的共享主机）上直接跑，所以只依赖标准库
（`urllib` / `json` / `http.server` / `concurrent.futures`），全部逻辑收在单文件 `bili_planner.py` 里，不做包结构。

## Consequences

- 没有 `requests` 的会话复用、没有 `aiohttp` 的并发原语：HTTP 用 `urllib`，抓取并发用 `ThreadPoolExecutor`（默认 4 线程）。
- 数据一律用 dict 流转，不加类型注解——注解会与真实形状脱节；形状靠 `test_planner.py` 与 `docs/architecture.md` 固定。
- 单文件会继续变长（现在 758 行）；真正需要拆分时，先补一层显式接口再拆，而不是提前建包。
