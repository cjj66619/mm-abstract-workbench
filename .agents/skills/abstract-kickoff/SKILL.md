---
name: abstract-kickoff
description: mm-abstract-workbench 入口。对任意数模论文项目（polish/sections 或 paper/sections 下的 Markdown 正文 + reports/）撰写竞赛风格摘要：intake 建事实账本 → select 选高价值事实并出预算 → 按风格卡写 abstract/sections/00_abstract.md → lint 体检 → verify 数字/限定词溯源 → ABSTRACT_REPORT.md。原始正文与 Word 一律不改。用户说"写摘要 / 重写摘要 / 摘要太啰嗦 / 跑 abstract"时使用。
---

# abstract-kickoff

## 输入与前提

- 一个项目目录 `<proj>`，正文为 Markdown 章节：优先 `polish/sections/*.md`（润色稿），其次 `frame/sections/`、`paper/sections/`；`--source` 可指定。
- 问题章靠一级标题里的"问题 N / 第 N 问"识别；有 `reports/*.md` 则其数字也进数字池；`paper/paper.yaml` / `project.yaml` 提供题目名。
- 不需要 Word、pandoc。摘要产物是 Markdown，用户自己粘到 Word 摘要页或交给 mm-layout-workbench。

## 工作区（只写 `<proj>/abstract/`）

```text
<proj>/abstract/
├── ABSTRACT_FACTS.json        # 事实账本：每问的数字（含上下文/标签/限定词）、结论句、限定句、术语、数字池
├── ABSTRACT_CANDIDATES.json   # 排序后的候选数字/结论句/方法链/关键词 + 预算
├── ABSTRACT_PLAN.md           # 人看的写作计划：每段预算、每问候选事实（按分排序）
├── ABSTRACT_LINT_BEFORE.md    # 现有摘要的改前体检（若项目里已有 00_abstract.md）
├── sections/00_abstract.md    # 新摘要（人/Agent 写）
├── ABSTRACT_REWRITE_LOG.md    # 取舍理由（人/Agent 写，可选）
├── ABSTRACT_LINT.md           # 改后体检
├── ABSTRACT_FACT_DIFF.md      # 每个数字/限定词/关键词的溯源
└── ABSTRACT_REPORT.md         # 改前/改后指标、数字取舍、待人工复核清单
```

## 流程

```text
1 python .agents/skills/abstract-kickoff/scripts/run_abstract.py <proj>
     → intake + select + 改前体检；摘要不存在时停下并打印 PLAN 路径
2 读 abstract/ABSTRACT_PLAN.md + _references/abstract_style_card.md，按 abstract-write/SKILL.md 写 abstract/sections/00_abstract.md
3 python .agents/skills/abstract-kickoff/scripts/run_abstract.py <proj> --skip-intake --strict
     → lint + verify + report；任一 FAIL 返回 1，回到第 2 步改
4 交付 abstract/ 目录；把 ABSTRACT_REPORT.md 的"待人工复核"逐条给用户
```

`--target-zh` / `--num-budget` / `--per-problem` 可覆盖默认预算（默认取语料 P50：1137 汉字、≤ 24 个数字、每问 ≤ 4 个数字）。

## 交付标准

- `ABSTRACT_LINT.md` 与 `ABSTRACT_FACT_DIFF.md` FAIL 均为 0；WARN 逐条在报告里说明保留理由或已修。
- 每个问题都有一段，段内有方法、有结果、有验证或交接。
- 正文里的"探索性假设 / 无标签 / 无真值 / 低置信 / 待复核 / 合成数据"等限定在摘要中保留。
- 摘要中的每个数字都能在 `ABSTRACT_FACT_DIFF.md` 里指到正文或报告。

## 禁止

- 修改 `paper/`、`polish/`、`frame/`、`data/`、`results/`、`reports/`、`figures/`、`code/`。
- 新增正文与报告中不存在的数字、方法、结论；把预测标签写成真实标签；把一致率写成准确率。
- 摘要里出现内部文件名、图表编号、章节号、`$…$` 公式、Markdown 加粗。
