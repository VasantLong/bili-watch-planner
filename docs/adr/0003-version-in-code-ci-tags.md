# 版本号在代码里，tag 与 Release 交给 CI

手工 `git tag` + `gh release create` 出过一次事故：tag 指的 commit、`__version__` 与 Release 说明三者不一致，
而且 tag 推错了要 `--force` 才能改（`--force` 属禁止 flag）。所以版本号只保留一个真相：`bili_planner.py` 里的 `__version__`。

- `scripts/release.sh X.Y.Z` 改版本号 → 跑单测与前端语法检查 → 提交 `chore(release): vX.Y.Z` → 推 main，**不建 tag**。
- `.github/workflows/release.yml` 读 `__version__`：tag `vX.Y.Z` 不存在就建 tag 发 Release；已存在则不重复发版。
- 版本号没升、但 `bili_planner.py` / `static/` 有改动时，workflow 直接失败，逼你补版本号。

## Consequences

- 发版失败点从「人记得做几步」变成「CI 的 3 个 job」，本地不再有权限把 tag 推歪。
- 改版本号必须走脚本（或手改 `__version__` 后推 main），不能只打个 tag 了事。
