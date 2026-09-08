---
name: _references
description: mm-abstract-workbench 共享知识库：摘要风格卡、摘要反模式清单、优秀论文摘要语料统计与阈值。其他 skills 按需读取，无需单独触发。
---

| 文件 | 用途 | 谁读 |
| --- | --- | --- |
| `abstract_style_card.md` | 摘要硬指标 + 结构模板 + 数字取舍规则 + 改写模板 | abstract-write、abstract-select |
| `abstract_anti_patterns.md` | 经语料计数校验的摘要反模式，每条对应一个 lint / verify 规则 | abstract-lint 规则来源、abstract-write 自查 |
| `abstract_corpus_stats.md` / `.json` | 39 篇优秀论文摘要实测分布；json 是 `lint_abstract.py` 与 `select_facts.py` 的阈值文件 | 脚本自动读取 |

更新语料阈值：`python .agents/skills/abstract-corpus/scripts/abstract_corpus_stats.py <pdf 目录> --year 23 [--append]`，
输出直接覆盖本目录两个 stats 文件。不要把 PDF 提交进仓库；不要手改 json。
