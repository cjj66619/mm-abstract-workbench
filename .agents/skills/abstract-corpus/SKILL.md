---
name: abstract-corpus
description: 维护摘要语料阈值。从一批优秀论文 PDF 中切出摘要页（"摘要"到"关键词"），统计汉字数、数字个数与密度、有效位、单句数字、句长、问题分段、开头长度、结尾段、关键词数、缩写、括号引号、套话等指标的分位数，覆盖 _references/abstract_corpus_stats.json/.md。仅在新增语料或加 lint 指标时运行。
---

# abstract-corpus

```bash
pip install pymupdf                                   # 仅本 skill 需要
python .agents/skills/abstract-corpus/scripts/abstract_corpus_stats.py <pdf 目录> --year 23
python .agents/skills/abstract-corpus/scripts/abstract_corpus_stats.py <另一批> --year 24 --append
```

- 输出默认覆盖 `.agents/skills/_references/abstract_corpus_stats.json` 与 `.md`；`--append` 在已有 `papers` 上追加后重算分位数。
- `--dump-dir` 可把切出的摘要纯文本落盘到仓库外，用于人工核对切分边界与看范文；**不要提交 PDF 或摘要文本**。
- 指标定义与 `lint_abstract.py` 共用 `abstract_common.abstract_metrics()`，保证语料阈值与被检摘要用同一把尺。

## 当前语料

39 篇 2023 年研究生数模竞赛优秀论文（C/D/E/F 题各约 10 篇）。摘要页由 PDF 文本层切出，个别论文因排版导致
`lead_zh`（第一个"问题 N"前汉字数）离群（max 844），这是 A12 只 WARN 不 FAIL 的原因。

## 加指标

1. 在 `abstract_common.abstract_metrics()` 里加字段（同时服务 lint 与语料）；
2. 重跑本脚本；
3. 在 `lint_abstract.py` 里用 `band(th, "<字段>", …)` 接阈值；
4. 在 `_references/abstract_anti_patterns.md` 记下语料计数与理由。

## 切分失败

`cut_abstract()` 在前 6 页找不到"摘要…关键词"就跳过该篇并打印文件名；扫描版 PDF（无文本层）不支持，
需要 OCR 后再喂或直接排除。
