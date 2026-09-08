---
name: abstract-intake
description: 摘要工作台第 1 步。读取项目正文（polish/sections 优先）与 reports/*.md，建立摘要事实账本 abstract/ABSTRACT_FACTS.json：每问的带上下文数字、结论句、限定词句、加粗术语、缩写、全文数字池、现有摘要基线。只读项目，只写一个 JSON。
---

# abstract-intake

```bash
python .agents/skills/abstract-intake/scripts/intake_abstract.py <proj> [--source auto|polish|frame|paper] [--out <json>]
```

## 做什么

1. 选正文来源：`auto` 按 `polish/sections` → `frame/sections` → `paper/sections` 取第一个存在的目录。
2. 按一级标题给每个文件分角色：`problem`（含"问题 N / 第 N 问"，按 N 编号）、`robustness`、`evaluation`、`analysis`、`intro`、`abstract`、`other`。
3. 对每个正文章节抽取：
   - `numbers[]`：每个数字的原文、归一化值、有效位、所在句、局部上下文、标签（`metric / data_size / param / table / fraction / range / unit / small_int`…）；
   - `conclusions[]`：含"结果表明 / 最终 / 说明 / 表明 / 一致 / 优于"等判决词的句子；
   - `hedges[]`：含限定词（`HEDGE_WORDS`）的句子及命中词；
   - `bold_terms`、`abbrs`、小节标题、汉字数。
4. `number_pool`：正文 + `reports/*.md` 全部归一化数字（verify 的唯一依据）；`term_counts`：加粗术语在正文中的全局出现次数（verify 判"多数时候被限定"用）。
5. `baseline`：若项目已有摘要（`abstract/sections/00_abstract.md` 或正文 `摘要` 章），记录其指标作为"改前"。

## 输出契约

`abstract/ABSTRACT_FACTS.json` 顶层：`source`、`title`、`problems[]`、`extras[]`、`number_pool`、`term_counts`、`baseline`、`reports[]`。
下游三个脚本都只读这一个文件；改字段名要同步 `select_facts.py` / `verify_abstract.py` / `smoke_test.py`。

## 不做什么

- 不判断哪些事实重要（那是 abstract-select）；不改任何正文；不读 Word、`results/` 原始数据。
- 数字识别规则见 `abstract_common.NUM` / `norm_num()`；年份、`问题 N`、公式内数字不进数字池。
