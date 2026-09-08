# AGENTS.md — mm-abstract-workbench

数模论文**摘要撰写**专用下游工作流（`mm-draft-workbench` 出稿 → `mm-frame-workbench` 整框架 → `mm-polish-workbench` 打磨正文 →
**本仓库写摘要** → `mm-layout-workbench` 排版）。输入一个项目目录 `<proj>`（含 `polish/sections/*.md` 或 `paper/sections/*.md`、
可选 `reports/*.md`），输出全部在 `<proj>/abstract/`。入口技能：`.agents/skills/abstract-kickoff/SKILL.md`。

本仓库是通用工具，服务于任何一届比赛的任何项目：**不得写入任何具体项目的题目、模型名、变量名、结论或术语**
（示例项目 `examples/demo-drug-decay/` 用合成药动学数据，是唯一允许出现具体术语的地方）。
写法规范的唯一依据是优秀论文摘要语料（`_references/`，脚本生成，不存 PDF）。

## 硬规则（违反即失败）

1. **只写 `<proj>/abstract/`**。`paper/`（含 `main.docx`）、`polish/`、`frame/`、`data/`、`results/`、`reports/`、`figures/`、`code/` 一律只读。
   摘要产物是 Markdown（`abstract/sections/00_abstract.md`），不生成也不改 Word。
2. **事实零漂移**。摘要里每个数字必须能在正文或 `reports/*.md` 里找到（`verify_abstract.py` V01）；约数只允许"约 / 近 / 超过 / 不到"引导且 ≤ 3 位有效数字。
   不新增正文没有的数字、方法、结论。
3. **限定词只增不减**。正文里"探索性假设 / 初步 / 低置信 / 待复核 / 无标签 / 无真值 / 合成数据 / 不能解读为…"等限定，进摘要必须保留（V02）。
   预测标签不写成真实标签，一致率不写成准确率。
4. **先计划后写作**。`intake → select` 生成 `ABSTRACT_PLAN.md` 后，由人 / Agent 按 `abstract-write/SKILL.md` 与 `_references/abstract_style_card.md` 写摘要；
   脚本不自动生成摘要文字（自动拼接正文句子正是"啰嗦、堆数字"的来源）。
5. **阈值有出处**。lint 与预算只读 `_references/abstract_corpus_stats.json`（`abstract_corpus_stats.py` 生成，勿手改）；
   加规则先在语料上数，计数写进 `abstract_anti_patterns.md`。> P75 WARN、> 语料最大值 FAIL；覆盖性 / 内部名 / Markdown 残留是结构性硬 FAIL。
6. **通用性**。不假设题型、问题数量、章节文件名、模型名；问题章靠一级标题 `问题 N / 第 N 问` 识别；证据靠文件契约（`polish|frame|paper/sections/*.md`、`reports/*.md`）。
7. **摘要自足**。摘要中不得出现 `reports/`、`results/`、`figures/`、`abstract/`、文件扩展名、图表编号、章节号、`$…$` 公式、Markdown 加粗 / 列表。
8. 代码：Python 3.10+ 标准库，`pathlib`，读写显式 `encoding="utf-8"`，`setup_stdout()` 处理控制台编码，不写绝对路径，不调 bash，子进程用列表形式 + `sys.executable`。
   `abstract-corpus` 例外依赖 `pymupdf`，仅维护语料时运行。
9. 不提交比赛数据、论文 PDF、项目稿件、凭据到仓库。

## 管线

```text
abstract-kickoff/scripts/run_abstract.py <proj> [--strict] [--skip-intake]
  → abstract-intake/scripts/intake_abstract.py    正文 + reports → abstract/ABSTRACT_FACTS.json（数字/结论/限定词/术语/数字池/改前基线）
  → abstract-select/scripts/select_facts.py       打分选候选 + 预算 → ABSTRACT_CANDIDATES.json / ABSTRACT_PLAN.md
  → abstract-lint（对旧摘要，若有）               → ABSTRACT_LINT_BEFORE.md
  → （人 / Agent 依据 PLAN + 风格卡写 abstract/sections/00_abstract.md，见 abstract-write/SKILL.md）
  → abstract-lint/scripts/lint_abstract.py        → ABSTRACT_LINT.md（A01–A18）
  → abstract-verify/scripts/verify_abstract.py    → ABSTRACT_FACT_DIFF.md（V01–V04）
  → run_abstract.py 汇总                          → ABSTRACT_REPORT.md（改前/改后、数字取舍、待人工复核）
```

语料更新：`python .agents/skills/abstract-corpus/scripts/abstract_corpus_stats.py <pdf 目录> --year 23 [--append]`。

## 改代码后必须跑

```bash
python -m compileall -q .agents/skills scripts
python scripts/smoke_test.py      # 临时项目：intake/select 产物 → 旧摘要 FAIL → demo 摘要 strict 通过 → 编造数字/丢限定/内部路径/数字堆叠各被拦 → 源文件未动
```

有真实项目时 `run_abstract.py <proj> --skip-intake --strict` 看 `ABSTRACT_LINT.md` / `ABSTRACT_FACT_DIFF.md` 没有新增误报。

## 常见任务

| 任务 | 做法 |
| --- | --- |
| 给一个项目写 / 重写摘要 | 读 `abstract-kickoff/SKILL.md`，三步走 |
| 只想体检一份摘要 | `python .agents/skills/abstract-lint/scripts/lint_abstract.py <md> --problems N` |
| 只想核对数字 | `python .agents/skills/abstract-verify/scripts/verify_abstract.py <proj>` |
| 加语料 / 调阈值 | `abstract-corpus/SKILL.md` |
| 加 lint 规则 | 先语料计数 → `abstract_anti_patterns.md` → `lint_abstract.py` |
