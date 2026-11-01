# Domain Docs

工程类 skill 在探索代码前，按这里的规则读本仓的领域文档。

## 探索之前先读

- 仓库根 `CONTEXT.md`（单上下文，无 `CONTEXT-MAP.md`）。
- `docs/adr/` 里与本次改动相关的 ADR（现在有 0001–0004 四条）。

文件不存在时**静默跳过**，不要提示缺失，也不要提议补建——术语与决策是在 `/domain-modeling` 真正收敛时才写入。

## 文件结构

单上下文仓库：

```text
/
├── CONTEXT.md
├── CODING_STANDARDS.md
├── docs/
│   ├── adr/
│   │   ├── 0001-stdlib-only.md
│   │   ├── 0002-merge-by-bvid.md
│   │   ├── 0003-version-in-code-ci-tags.md
│   │   └── 0004-no-build-inline-frontend.md
│   ├── architecture.md
│   └── bilibili-api.md
├── bili_planner.py
└── static/index.html
```

## 用术语表里的词

输出里提到领域概念（issue 标题、重构提案、假设、测试名）时，用 `CONTEXT.md` 里的词，不要漂到它标了 `_Avoid_` 的同义词
（例如写「分P」不写「分段」，写「来源」不写「数据源」）。

需要的概念不在表里时，这本身是信号：要么是在发明项目并不使用的语言（重新考虑），要么是真有缺口（留给 `/domain-modeling`）。

## ADR 冲突要摆到明面

输出与既有 ADR 相悖时，显式指出来，不要默默覆盖：

> _与 ADR-0001（纯标准库）冲突，但值得重开，因为……_
