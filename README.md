# mm-abstract-workbench

`mm-polish-workbench` 的下游：在正文润色完成后，把一篇数模论文压缩成**评委愿意读完的摘要**。
只读正文与报告，只写 `<proj>/abstract/`，不碰模型、数据、公式和 Word。

## 解决什么问题

自动生成 / 初稿阶段的摘要通常有三个毛病：内容繁杂啰嗦、把正文数字一字不差搬进来、文字不专业逻辑弱。
对照 39 篇 2023 年研究生数模竞赛优秀论文（C/D/E/F 各约 10 篇）摘要的实测分布：

| 指标 | 初稿摘要（一个真实项目） | 优秀论文 P50（P75） |
| --- | ---: | ---: |
| 汉字数 | 1700 | 1137（1377） |
| 数字个数 | 93 | 15（24） |
| 数字 / 千汉字 | 54.7 | 12.5（22.1） |
| ≥ 4 位有效数字 | 10 | 0（5） |
| 单句最多数字 | 7 | 4（6） |
| 关键词 | 10 | 5（7） |
| 英文缩写 | 16 | 3（4） |
| 结尾创新 / 局限段 | 无 | 59% 有 |

数字六倍、缩写五倍、没有结尾——优秀摘要每问一段，每段 3–4 个能证明结论的数字，其余全部退回正文，并在结尾诚实写出特点与局限。

## 它做什么 / 不做什么

做：从正文与报告建立**事实账本**（每个数字带上下文、标签、限定词）→ 给数字和结论**打分选候选**并按语料给**预算** → 人 / Agent 按**风格卡**写摘要 → **lint**（18 条规则，阈值来自语料）→ **verify**（每个数字回溯正文、限定词不丢、关键词出自正文、问题全覆盖）→ 改前 / 改后**报告**。

不做：自动拼接摘要文字（那正是啰嗦与堆数字的来源）；改任何正文；生成或修改 Word。

## 用法

```bash
# 1 建账本 + 选候选 + 旧摘要体检；摘要不存在时停下并给出 abstract/ABSTRACT_PLAN.md
python .agents/skills/abstract-kickoff/scripts/run_abstract.py <proj>

# 2 人 / Agent 读 ABSTRACT_PLAN.md + .agents/skills/_references/abstract_style_card.md，
#   按 .agents/skills/abstract-write/SKILL.md 写 <proj>/abstract/sections/00_abstract.md

# 3 体检 + 溯源 + 报告；任一 FAIL 返回 1
python .agents/skills/abstract-kickoff/scripts/run_abstract.py <proj> --skip-intake --strict
```

也可单独用：

```bash
python .agents/skills/abstract-lint/scripts/lint_abstract.py some/abstract.md --problems 4
python .agents/skills/abstract-verify/scripts/verify_abstract.py <proj> --strict
```

`<proj>` 需要 `polish/sections/*.md`（或 `frame/` / `paper/sections/`）；有 `reports/*.md` 会一并进数字池。问题章靠一级标题里的"问题 N"识别。

## 输出

```text
<proj>/abstract/
├── ABSTRACT_FACTS.json        事实账本：每问数字（上下文/标签/限定词）、结论句、术语、数字池、改前基线
├── ABSTRACT_CANDIDATES.json   排序候选 + 预算
├── ABSTRACT_PLAN.md           写作计划（人看）
├── ABSTRACT_LINT_BEFORE.md    旧摘要体检（若有）
├── sections/00_abstract.md    新摘要（人 / Agent 写）
├── ABSTRACT_LINT.md           新摘要体检 A01–A18
├── ABSTRACT_FACT_DIFF.md      数字 / 限定词 / 关键词溯源 V01–V04
└── ABSTRACT_REPORT.md         改前改后指标、保留 / 删去 / 新引入数字、待人工复核
```

## 仓库结构

```text
.agents/skills/
├── abstract-kickoff/   入口；run_abstract.py 串起全流程
├── abstract-intake/    intake_abstract.py · abstract_common.py（共享解析 / 指标 / 限定词表）
├── abstract-select/    select_facts.py：打分、预算、ABSTRACT_PLAN.md
├── abstract-write/     写作规程（无脚本）
├── abstract-lint/      lint_abstract.py
├── abstract-verify/    verify_abstract.py
├── abstract-corpus/    abstract_corpus_stats.py：从优秀论文 PDF 生成阈值（需 pymupdf）
└── _references/        abstract_style_card · abstract_anti_patterns · abstract_corpus_stats（阈值，脚本生成）
scripts/smoke_test.py       临时项目端到端自检（含四种坏摘要必须被拦）
examples/demo-drug-decay/   合成药动学示例项目：paper/sections + reports + 已通过 strict 的 abstract/
docs/DESIGN.md              设计与语料分析
```

标准库，Python 3.10+，Windows / Linux / macOS。

## 状态

- 在一个真实四问项目上验证：旧摘要 lint 3 FAIL / 15 WARN → 新摘要 0 / 0，数字 93 → 16，限定词全部保留，每个数字可溯源。
- 示例项目 `examples/demo-drug-decay/` 与 `scripts/smoke_test.py` 在 CI（ubuntu / windows）上运行。
