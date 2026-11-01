# Issue tracker: GitHub

Issues 与 spec 都住在 GitHub Issues（`VasantLong/bili-watch-planner`）。用 `gh` 操作，在克隆目录里跑时它会自己认仓库。

## 约定

- **建 issue**：`gh issue create --title "..." --body "..."`，多行 body 用 heredoc。
- **读 issue**：`gh issue view <number> --comments`；需要结构化取用时加 `--json number,title,body,labels,comments`。
- **列 issue**：`gh issue list --state open --json number,title,body,labels,comments --jq '[.[] | {number, title, body, labels: [.labels[].name], comments: [.comments[].body]}]'`，配合 `--label` / `--state` 过滤。
- **评论**：`gh issue comment <number> --body "..."`。
- **打/撤标签**：`gh issue edit <number> --add-label "..."` / `--remove-label "..."`。
- **关闭**：`gh issue close <number> --comment "..."`。

## PR 作为请求入口

**PRs as a request surface: no.**（若以后想让人用 PR 提需求，把这里改成 `yes`，`/triage` 会照它执行。）

改成 `yes` 后，PR 走与 issue 相同的标签与状态，用 `gh pr` 对应命令：

- **读 PR**：`gh pr view <number> --comments`，diff 用 `gh pr diff <number>`。
- **列外部 PR**：`gh pr list --state open --json number,title,body,labels,author,authorAssociation,comments`，只保留 `authorAssociation` 为 `CONTRIBUTOR` / `FIRST_TIME_CONTRIBUTOR` / `NONE` 的项。
- **评论 / 打标签 / 关闭**：`gh pr comment`、`gh pr edit --add-label` / `--remove-label`、`gh pr close`。

GitHub 的 issue 与 PR 共用一套编号，裸 `#42` 可能指 PR：先 `gh pr view 42`，失败再 `gh issue view 42`。

## skill 说「publish to the issue tracker」时

建一个 GitHub issue。

## skill 说「fetch the relevant ticket」时

`gh issue view <number> --comments`。

## Wayfinding 操作

供 `/wayfinder` 使用：**map** 是一个 issue，**child** issue 是票。

- **Map**：单个 issue，标签 `wayfinder:map`，body 放 Notes / Decisions-so-far / Fog。`gh issue create --label wayfinder:map`。
- **Child ticket**：作为 map 的 GitHub sub-issue 关联（sub-issues 端点走 `gh api`）；不可用时退化为在 map body 里列 task list，并在 child 顶部写 `Part of #<map>`。标签 `wayfinder:<type>`（`research`/`prototype`/`grilling`/`task`）。被认领后 assign 给执行者。
- **Blocking**：用 GitHub 原生 issue dependencies（`.blocked_by`），加边：
  `gh api --method POST repos/<owner>/<repo>/issues/<child>/dependencies/blocked_by -F issue_id=<blocker-db-id>`，
  其中 `<blocker-db-id>` 是阻塞者的**数据库 id**（`gh api repos/<owner>/<repo>/issues/<n> --jq .id`），不是 `#number`。
  不可用时退化为 child 顶部 `Blocked by: #<n>, #<n>`。所有阻塞者关闭才算解除。
- **Frontier 查询**：列出 map 的 open children，剔除有 open blocker 或已有 assignee 的，按 map 顺序取第一个。
- **认领**：`gh issue edit <n> --add-assignee @me`（本轮会话的第一次写操作）。
- **结票**：`gh issue comment <n> --body "<结论>"` → `gh issue close <n>` → 把结论要点追加到 map 的 Decisions-so-far。
