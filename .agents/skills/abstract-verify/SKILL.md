---
name: abstract-verify
description: 摘要工作台第 5 步。把摘要里的每个数字、限定词、关键词、问题号回溯到正文与 reports/：数字不在数字池 → FAIL；正文里始终带强限定词的数字在摘要里失去限定 → FAIL；多数时候被限定的术语在摘要里变成确定语气 → WARN；关键词/缩写正文没有 → WARN；问题号不一致 → FAIL。输出 ABSTRACT_FACT_DIFF.md。
---

# abstract-verify

```bash
python .agents/skills/abstract-verify/scripts/verify_abstract.py <proj> [--abstract <md>] [--strict]
```

读 `abstract/ABSTRACT_FACTS.json`（intake 产物）与摘要，写 `abstract/ABSTRACT_FACT_DIFF.md`。`--strict` 时 FAIL > 0 返回 1。

## 规则

| 规则 | 级别 | 判定 |
| --- | --- | --- |
| V01 数字溯源 | PASS / PASS(约数) / FAIL | 摘要每个数字（年份、`问题 N` 除外）归一化后必须在 `number_pool`（正文 + reports）里。句中带"约 / 近 / 超过 / 不到 / 以上 / 左右"且 ≤ 3 位有效数字时，允许池中某数按同样位数四舍五入后相等（相对误差 ≤ 6%）。 |
| V02 数字限定 | FAIL | 某数字在正文的**每一次**出现都带强限定词（`STRONG_HEDGE`：假设 / 探索性 / 待复核 / 低置信 / 无标签 / 无真值 / 合成数据 / 演示数据 / 不能据此 / 尚未 / 初步 / 推断 / 旁证 / 假想），而摘要含该数字的句子没有任何限定词。表格内数字不参与。 |
| V02 术语限定 | WARN | 某加粗术语（2–8 汉字）在正文出现 ≥ 50% 的次数都在强限定句里，而摘要含该术语的句子无限定词。依赖 `term_counts`。 |
| V03 关键词 / 缩写 | WARN | 关键词或英文缩写在正文中未出现。 |
| V04 问题覆盖 | FAIL | 摘要提及的问题号集合 ≠ 正文问题号集合。 |

## 报告

`ABSTRACT_FACT_DIFF.md`：逐条表格（规则 / 状态 / 项 / 摘要句 / 说明）+ 汇总（数字 N 个，其中约数 M 个；FAIL / WARN 计数）。
FAIL 必须清零；WARN 逐条人工确认后在 `ABSTRACT_REWRITE_LOG.md` 说明。

## 边界

- 正文里带限定词但**不总是**带限定词的数字（如某指标在小结里被确定地引用）不触发 V02 —— 避免误报；判"总是"用的是强限定词表，不是全部 `HEDGE_WORDS`。
- 摘要写了正文没有、但 reports 有的数字算 PASS；写了 results/ 原始数据里才有的数字算 FAIL —— 摘要不应绕过正文直接引用原始结果。
- 不检查语义是否篡改（"一致率"写成"准确率"这类要靠 abstract-write 的规矩 + 人审）。
