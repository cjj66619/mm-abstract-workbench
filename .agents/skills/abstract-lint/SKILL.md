---
name: abstract-lint
description: 摘要工作台第 4 步。对一份摘要 Markdown 做"像不像优秀论文摘要"的体检：长度、数字密度、有效位、单句数字堆叠、问题覆盖与每问方法/结果、关键词、结尾段、内部名、Markdown 残留、套话。阈值只来自 39 篇优秀论文摘要语料：> P75 WARN，> 最大值 FAIL。
---

# abstract-lint

```bash
python .agents/skills/abstract-lint/scripts/lint_abstract.py <proj>            # 读 <proj>/abstract/sections/00_abstract.md
python .agents/skills/abstract-lint/scripts/lint_abstract.py some/abstract.md --problems 4 --strict
```

传项目目录时自动读 `abstract/ABSTRACT_FACTS.json` 取正文实际问题号；输出 `abstract/ABSTRACT_LINT.md` + `abstract_lint.json`。
`--strict` 时 FAIL > 0 返回 1。

## 规则

| 规则 | 级别 | 内容 | 阈值来源 |
| --- | --- | --- | --- |
| A00 | FAIL | 摘要正文为空 | — |
| A01 | WARN/FAIL | 汉字数 > P75 / > max；< P25 WARN | `zh_chars` |
| A02 | WARN/FAIL | 数字个数、每千字数字数 > P75 / > max；小数个数 > P75 | `num_count` `num_per_k` `dec_count` |
| A03 | WARN/FAIL | ≥ 4 位有效数字个数 > P75 / > max | `sig4_count` |
| A04 | WARN/FAIL | 单句最多数字 > P75 / > max；`a / b / c` 式数字并列 | `max_nums_per_sentence` `slash_list` |
| A05 | FAIL | 正文有的问题号在摘要里没提 | facts / `--problems` |
| A05 | WARN | 某问段落无方法词、无可核验结果、或长度 > 整篇 35%；提到正文不存在的问题号 | — |
| A06 | FAIL/WARN | 缺 `关键词：` 行；个数超出 P25–P75；关键词含标点或过长 | `kw_count` |
| A07 | WARN | 结尾没有创新 / 局限 / 推广句 | 语料 59% 有 |
| A08 | WARN | AI 套话（`AI_PHRASES`） | 语料 P75 = 0 |
| A09 | FAIL/WARN | 内部目录名（`reports/` `results/` `figures/` …）FAIL；扩展名（`.mat` `.csv`）WARN | — |
| A10 | WARN | 句长 P90 > 语料 P75；单句 > 语料 `sent_max` P75 | `sent_p90` `sent_max` |
| A12 | WARN/INFO | 只有一段；段落数 < 问题数 + 1；第一个"问题 N"之前过长 | `lead_zh` |
| A13 | WARN | 每千字括号 / 引号数 > P75 | `paren_per_k` `quote_per_k` |
| A15 | WARN/INFO | 每千字英文缩写 > P75；缩写无中文释义 | `en_abbr_per_k` |
| A16 | FAIL/WARN | 残留 Markdown（`**` 列表 标题 链接）FAIL；`$…$` 公式 WARN | — |
| A17 | FAIL/WARN | 引用正文图表 / 章节编号 FAIL；引用题面表格 WARN | — |
| A18 | WARN/INFO | "进行了 X / 开展了 X" 空转词；"本文"过密 | — |

## 加规则的规矩

先在语料上数（`abstract_corpus_stats.py` 加一个指标字段重跑），确认优秀论文里这个模式确实少见，把计数写进 `_references/abstract_anti_patterns.md`，再改 `lint_abstract.py`；阈值一律读 `abstract_corpus_stats.json`，不在代码里写死。
