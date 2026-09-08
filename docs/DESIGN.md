# DESIGN — mm-abstract-workbench

## 1. 定位

数模论文工作流的最后一个文字环节：

```text
mm-draft-workbench（出稿） → mm-frame-workbench（框架） → mm-polish-workbench（正文） → mm-abstract-workbench（摘要） → mm-layout-workbench（排版）
```

摘要是评委读的第一页。它不是正文的压缩包，而是一份"论证已经完成"的证据清单：每一问用什么方法、得到什么可核验的结论、结论可靠到什么程度。
本仓库把这件事拆成**机器擅长的**（找事实、算密度、核数字、查限定词）与**人 / Agent 擅长的**（取舍、组织、措辞），中间用文件契约交接。

## 2. 为什么不自动生成摘要

初稿摘要的三个毛病（啰嗦、堆数字、逻辑弱）都来自同一个动作：把正文各章的结果句拼起来。任何"自动摘录 + 拼接"的脚本都会复现这三个毛病，
因为脚本不知道哪个数字证明了哪个结论。所以脚本只做到 `ABSTRACT_PLAN.md`：告诉写作者每问最值得写的 3–5 个数字和 2–3 句结论、每段的预算，
以及哪些事实进摘要时必须带限定词。写作由人 / Agent 按风格卡完成，然后脚本用 lint + verify 把关。

## 3. 语料与阈值

39 篇 2023 年研究生数模竞赛优秀论文（C/D/E/F 题各约 10 篇），`abstract_corpus_stats.py` 从 PDF 前 6 页切"摘要 … 关键词"段，
用与 lint 相同的 `abstract_metrics()` 计算指标，输出分位数到 `_references/abstract_corpus_stats.json`。

关键发现（P50 / P75 / max）：

| 指标 | P50 | P75 | max | 对规则的影响 |
| --- | ---: | ---: | ---: | --- |
| 汉字数 | 1137 | 1377 | 1697 | 预算默认 1137；> 1697 FAIL |
| 数字个数 | 15 | 24 | 52 | 预算 ≤ 24；每问 ≤ 4 |
| 数字 / 千字 | 12.5 | 22.1 | 39.2 | > 39.2 FAIL（初稿常见 50+） |
| ≥ 4 位有效数字 | 0 | 5 | 14 | 约数优先；`round_hint` |
| 单句最多数字 | 4 | 6 | 18 | 一句 ≤ 3 个为佳；`a / b / c` 并列语料 0 例 |
| 开头段汉字 | 156 | 243 | 844 | 背景 + 任务 + 方案 ≤ 240 字 |
| 关键词 | 5 | 7 | 15 | 3–6 个 |
| 英文缩写 | 3 | 4 | 29 | 只留反复出现的模型名 |
| 结尾段 | 59% 有 | | | A07 WARN |
| "针对问题 N" 分段 | 31–35 / 39 篇 | | | 段首模板 |
| AI 套话 | P75 = 0 | | 1 | A08 |

阈值策略：**> P75 WARN，> 语料最大值 FAIL**；覆盖性、内部名、Markdown 残留、数字不可溯源、强限定词丢失是与分布无关的硬 FAIL。
所有阈值只从 json 读取，代码里不写死数字，换一批语料重跑即可。

## 4. 管线与文件契约

```text
intake_abstract.py   <proj>/{polish|frame|paper}/sections/*.md + reports/*.md
                     → abstract/ABSTRACT_FACTS.json
select_facts.py      FACTS → abstract/ABSTRACT_CANDIDATES.json + ABSTRACT_PLAN.md
（写作）             PLAN + style card → abstract/sections/00_abstract.md
lint_abstract.py     00_abstract.md (+FACTS 取问题号) → ABSTRACT_LINT.md / abstract_lint.json
verify_abstract.py   00_abstract.md + FACTS → ABSTRACT_FACT_DIFF.md
run_abstract.py      串起以上 + 旧摘要 LINT_BEFORE + ABSTRACT_REPORT.md
```

### 4.1 事实账本（intake）

每个正文数字记录：原文、归一化值、有效位、所在句、局部窗口、标签。标签由句子 / 小节上下文给出：
`metric`（句中有指标词）、`metric_local`（数字紧邻指标词）、`result`（结果 / 小结小节）、`summary`、`compare`、`param`、`data`、`table`（表格行）、
`fraction`（a/b）、`range`（a–b）、`unit`、`small_int`（无单位、无百分号的一两位整数）。
限定句单独成表（`hedges[]`，命中 `HEDGE_WORDS`），并记录每个加粗术语在正文中的全局出现次数（`term_counts`），供 verify 判"该术语是否多数时候被限定"。
`number_pool` 是正文 + reports 全部归一化数字，是 V01 的唯一依据 —— 摘要不允许绕过正文直接引用 `results/` 原始数据。

### 4.2 候选打分（select）

`score_number`：`metric_local` +4；`result` / `summary` +2；`compare` / `fraction` +1；带单位 +0.5；`table` −3；`param` −2；`data` −1；
`small_int` −4（紧邻指标词时 −2）；≥ 4 位有效数字 −1.5；重复出现每次 +0.5（上限 +2）。
效果：留出集宏 F1、一致率、对照差距排最前；窗长、树深、样本数、章节号排最后。
`score_claim` 偏好小结小节里含指标词与"最终 / 综上 / 表明"的完整句，惩罚过长、引用图表、以冒号结尾的句子。
预算按语料 P50 给总量，按问题数等比分配；开头 ≤ 2 个数字，结尾 0 个。

### 4.3 lint

18 条规则见 `abstract-lint/SKILL.md`。特别处理：
- 问题段落归属：段落里第一个"问题 N"决定归属；每问检查有无方法词、有无数字或结论词、长度是否超过整篇 35%。
- 内部名：目录名（`reports/` 等）FAIL；扩展名（`.mat`）WARN —— 有的题目本身用文件格式描述数据。
- 引用编号：`图 3 / 表 2 / 第 4 章` FAIL；`题目表 2 / 附件表 1` 只 WARN（引用题面不是引用正文）。

### 4.4 verify

- V01：精确匹配 `number_pool`；带约数词且 ≤ 3 位有效数字时允许按同位数四舍五入匹配（相对误差 ≤ 6%）。
- V02（数字）：正文里**每一次**出现都带强限定词（`STRONG_HEDGE`）的数字，摘要句必须也带限定词，否则 FAIL。
  用"每一次"而不是"任一次"、用强限定词表而不是全部 `HEDGE_WORDS`，是为了消除早期版本对 0.771 / 0.645 这类"小结里确定引用、正文某处顺带说了'可能'"的数字的误报。
- V02（术语）：`term_counts` 里的加粗术语，若 ≥ 50% 的出现都在强限定句里，摘要句无限定词则 WARN（例：正文反复说"XX 为探索性假设"，摘要写成事实）。
- V03 / V04：关键词、缩写出自正文；问题号集合一致。

### 4.5 报告

改前 / 改后 14 项指标；数字保留 / 删去 / 新引入清单（新引入的必须已被 V01 溯源）；lint 与 verify 的 FAIL / WARN；待人工复核；明确写"不自动写回 Word"。

## 5. 通用性边界

- 不假设题型、问题数、章节文件名、模型名；仓库内除 `examples/demo-drug-decay/` 外不出现任何项目术语。
- 正文来源按 `polish → frame → paper` 回退，也可 `--source` 指定；没有 `reports/` 也能跑（数字池只含正文）。
- 语料是 2023 年一届；不同年份 / 赛种风格可能不同，`--append` 分批喂入后阈值自动更新。
- 只检测"像不像优秀摘要"和"有没有编数字 / 丢限定"，不判断语义是否篡改（"一致率"写成"准确率"靠写作规程与人审）。

## 6. 自检

`scripts/smoke_test.py` 在临时目录复制示例项目，检查：首轮产物齐全且不自动生成摘要；问题号与候选正确；计划无绝对路径；旧摘要 FAIL；
demo 摘要 strict 通过；四种坏摘要（编造数字、丢限定词、内部路径、一句 22 个数字）分别被 V01 / V02 / A09 / A04 拦下；`paper/` 与 `reports/` 字节未变。
CI 在 ubuntu / windows 上跑 compileall + smoke + 示例项目 strict。
