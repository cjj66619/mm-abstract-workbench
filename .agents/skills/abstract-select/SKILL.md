---
name: abstract-select
description: 摘要工作台第 2 步。从 ABSTRACT_FACTS.json 里给每个数字和结论句打分，选出"值得进摘要"的候选，并按优秀论文语料给出每段的字数/数字预算，写成 ABSTRACT_CANDIDATES.json 与人看的 ABSTRACT_PLAN.md。计划只是候选，不替代写作判断。
---

# abstract-select

```bash
python .agents/skills/abstract-select/scripts/select_facts.py <proj> [--target-zh 1137] [--num-budget 24] [--per-problem 4]
```

## 评分（`score_number` / `score_claim`）

数字：紧邻指标词（准确率 / F1 / 一致率 / RMSE…）的结果数最高；带 `result / summary / compare` 标签、分数式、有单位再加分；
表格内值、参数（`param`）、数据规模（`data`）、无单位小整数、≥ 4 位有效数字扣分；同一数值多次出现加分。
每问按归一化值合并重复，取前 `--per-problem` 个，附最佳上下文句、`must_hedge`（该值出现时伴随的限定词）、`round_hint`（≥ 4 位有效数字的约数建议）。

结论句：来自"小结 / 结论"小节、含指标词、含"最终 / 综上 / 表明 / 因此"加分；过长、以"其中 / 此外 / 本节"开头、以冒号结尾、引用图表扣分。

## 预算（`budget`）

默认取 `_references/abstract_corpus_stats.json` 的 P50：总汉字 1137、数字 ≤ 24、每问 ≤ 4；开头 120–240 字 ≤ 2 个数字；结尾 0 个数字。
`--target-zh` / `--num-budget` 覆盖总量后按问题数等比分配。

## 输出

- `ABSTRACT_CANDIDATES.json`：`budget`、`lead`（开头可用的背景/总体方案句）、`problems[]`（每问候选数字 + 结论句 + 方法链）、`robustness`、`tail`（创新/局限候选）、`keywords`（按加粗术语与缩写频次）、`hedged_claims`（必须带限定词进摘要的结论）。
- `ABSTRACT_PLAN.md`：同一内容的表格版，供写作者阅读。不含绝对路径。

## 写作者如何用

按 `ABSTRACT_PLAN.md` 逐问看候选，**只取最能证明结论的 1–3 个数字**；`must_hedge` 非空的事实进摘要必须带限定词；
`round_hint` 有值时优先写约数。计划里没有的数字不要写（verify 会拦）。
