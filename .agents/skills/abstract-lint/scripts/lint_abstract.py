"""lint_abstract.py — 摘要工作台第 4 步：对一份摘要 Markdown 做"像不像优秀论文摘要"的体检。

用法：
    python .agents/skills/abstract-lint/scripts/lint_abstract.py <abstract.md 或 proj>
        [--facts <proj>/abstract/ABSTRACT_FACTS.json]   # 有则按正文实际问题数检查覆盖；无则用 --problems
        [--problems N] [--out ABSTRACT_LINT.md] [--json abstract_lint.json] [--strict]

传项目目录时默认读 <proj>/abstract/sections/00_abstract.md，输出到 <proj>/abstract/。
阈值只来自 `_references/abstract_corpus_stats.json`（优秀论文摘要语料统计，脚本生成）：
- 超过语料 P75 → WARN（"比大多数优秀摘要更啰嗦/更堆数字"），超过语料最大值 → FAIL；
- 覆盖性 / 关键词行 / 内部文件名 / Markdown 残留 属于结构性硬规则 → FAIL。
--strict 时 FAIL > 0 返回 1。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "abstract-intake" / "scripts"))
from abstract_common import (  # noqa: E402
    AI_PHRASES, INTERNAL_NAMES, PROBLEM_MARK, RESULT_MARK, abstract_metrics, dump_json, load_json, load_thresholds,
    numbers_in, problem_index, read_text, sentences, setup_stdout, split_abstract_md, write_text, zh,
)

METHOD_MARK = ["模型", "方法", "算法", "建立", "构建", "提出", "采用", "设计", "求解", "拟合", "估计", "优化", "分析", "检验", "回归",
               "网络", "森林", "聚类", "规划", "仿真", "识别", "预测", "分类", "分解", "变换", "迁移", "对齐", "训练"]
FILLER = ["进行了", "开展了", "实施了", "进行", "了一系列", "全面", "深入", "有效地", "成功地", "较好地", "很好地", "充分"]


class Lint:
    def __init__(self) -> None:
        self.items: list[dict] = []

    def add(self, level: str, rule: str, msg: str, where: str = "") -> None:
        self.items.append({"level": level, "rule": rule, "msg": msg, "where": where})

    def count(self, level: str) -> int:
        return sum(1 for i in self.items if i["level"] == level)


def band(th: dict, key: str, val: float, L: Lint, rule: str, label: str, fail_over_max: bool = True) -> None:
    """按语料分位数给 WARN/FAIL：> P75 → WARN，> max → FAIL。"""
    s = th.get(key)
    if not s:
        return
    if fail_over_max and val > s["max"]:
        L.add("FAIL", rule, f"{label} = {val}，超过优秀论文语料中该项的最大值 {s['max']}（P50 = {s['p50']}）")
    elif val > s["p75"]:
        L.add("WARN", rule, f"{label} = {val}，高于语料 P75 = {s['p75']}（P50 = {s['p50']}）")


def problem_paragraphs(paras: list[str]) -> dict[int, str]:
    """把段落归到问题号：段落里首个"问题 N"标记决定归属；同一问题多段合并。"""
    out: dict[int, str] = {}
    for p in paras:
        ms = list(PROBLEM_MARK.finditer(p))
        if not ms:
            continue
        idx = problem_index(ms[0])
        if idx:
            out[idx] = (out.get(idx, "") + " " + p).strip()
    return out


def lint(text: str, th: dict, expected: list[int]) -> tuple[Lint, dict]:
    L = Lint()
    parts = split_abstract_md(text)
    body, kws, paras = parts["body"], parts["keywords"], parts["paragraphs"]
    m = abstract_metrics(body, kws)

    if not body.strip():
        L.add("FAIL", "A00", "摘要正文为空")
        return L, m
    # 结构性硬规则
    if not parts["has_kw_line"]:
        L.add("FAIL", "A06", "缺少 `关键词：…` 行（用中文分号/顿号分隔）")
    else:
        kc = len(kws)
        if kc < 3 or kc > 8:
            L.add("WARN", "A06", f"关键词 {kc} 个，语料 P25–P75 = {th.get('kw_count', {}).get('p25', 4)}–{th.get('kw_count', {}).get('p75', 7)}，建议 4–7 个")
        for k in kws:
            if zh(k) > 10 or "，" in k or "。" in k:
                L.add("WARN", "A06", f"关键词过长或含标点：{k}")
    for name in INTERNAL_NAMES:
        if name in body:
            L.add("WARN" if name.startswith(".") else "FAIL", "A09", f"摘要出现内部文件/目录名：{name}")
    for pat, what in ((r"\*\*", "加粗标记 **"), (r"@(fig|tbl|eq|sec):", "交叉引用标签 @fig:/@tbl:"), (r"\{#", "标签 {#…}"),
                      (r"!\[", "图片"), (r"^\s*\|", "表格"), (r"^\s*#{2,}", "二级以下标题")):
        if re.search(pat, body, re.M):
            L.add("FAIL", "A16", f"摘要正文残留 Markdown：{what}（摘要应为纯段落文字）")
    if "$" in body:
        L.add("WARN", "A16", f"摘要含 {body.count('$') // 2} 处行内公式；优秀摘要几乎不放公式，能用文字说清就不要用")
    for mm in re.finditer(r"(见|如)\s*(图|表|第)\s*[\d一二三四五六七八九十]|(图|表)\s*\d+[-–.]?\d*", body):
        ctx = body[max(0, mm.start() - 4): mm.end()]
        if re.search(r"题目|题面|附件", ctx):
            L.add("WARN", "A17", f"引用题面图表编号“{ctx}”，评委未必对照题面，建议直接写内容")
        else:
            L.add("FAIL", "A17", f"摘要引用了正文图表/章节编号“{ctx}”（摘要必须自足）")

    # 覆盖性
    if expected:
        got = set(m["problems"])
        miss = [i for i in expected if i not in got]
        if miss:
            L.add("FAIL", "A05", f"未提及问题 {'、'.join(map(str, miss))}（正文有问题 {'、'.join(map(str, expected))}）")
        pp = problem_paragraphs(paras)
        for i in expected:
            seg = pp.get(i, "")
            if not seg:
                continue
            if not any(w in seg for w in METHOD_MARK):
                L.add("WARN", "A05", f"问题{i} 段落没有看到方法/模型词（{'/'.join(METHOD_MARK[:6])}…）")
            if not numbers_in(seg) and not any(w in seg for w in RESULT_MARK):
                L.add("WARN", "A05", f"问题{i} 段落没有可核验的结果（既无数字也无结论词）")
            if zh(seg) > int(th.get("zh_chars", {}).get("p50", 1137) * 0.35):
                L.add("WARN", "A05", f"问题{i} 段落 {zh(seg)} 汉字，超过整篇目标长度的 35%，应压缩到 150–260 字")
    elif m["problem_count"] == 0:
        L.add("WARN", "A05", "摘要里没有出现“问题 N”标记，无法核对覆盖性；若论文按问题组织，请逐问写")
    extra = [i for i in m["problems"] if expected and i not in expected]
    if extra:
        L.add("WARN", "A05", f"摘要提到正文不存在的问题号 {extra}")

    # 篇幅与数字密度（语料分位）
    band(th, "zh_chars", m["zh_chars"], L, "A01", "摘要汉字数")
    lo = th.get("zh_chars", {}).get("p25")
    if lo and m["zh_chars"] < lo * 0.7:
        L.add("WARN", "A01", f"摘要仅 {m['zh_chars']} 汉字，明显短于语料 P25 = {lo}，可能漏掉了方法或结论")
    band(th, "num_count", m["num_count"], L, "A02", "数字个数")
    band(th, "num_per_k", m["num_per_k"], L, "A02", "每千汉字数字数")
    band(th, "dec_count", m["dec_count"], L, "A02", "小数个数", fail_over_max=False)
    band(th, "sig4_count", m["sig4_count"], L, "A03", "≥4 位有效数字的数字个数")
    band(th, "max_nums_per_sentence", m["max_nums_per_sentence"], L, "A04", "单句最多数字数")
    for s in sentences(body):
        n = len(numbers_in(s))
        if n > th.get("max_nums_per_sentence", {}).get("p75", 6):
            L.add("WARN", "A04", f"一句话堆了 {n} 个数字：{s[:70]}…")
    if m["slash_list"]:
        L.add("WARN", "A04", f"出现 {m['slash_list']} 处 `a / b / c` 式数字并列，改为只报最关键的一个或写成对比")

    # 句子与段落
    band(th, "sent_p90", m["sent_p90"], L, "A10", "句长 P90（汉字）", fail_over_max=False)
    for s in sentences(body):
        if zh(s) > th.get("sent_max", {}).get("p75", 141):
            L.add("WARN", "A10", f"长句 {zh(s)} 汉字：{s[:60]}…")
    if len(paras) <= 1 and m["zh_chars"] > 400:
        L.add("WARN", "A12", "整篇只有一个段落；优秀摘要一般是 开头 + 每问一段 + 结尾")
    if expected and len(paras) < len(expected) + 1:
        L.add("INFO", "A12", f"段落数 {len(paras)} < 问题数 + 1，可考虑每问单独成段")
    lead = th.get("lead_zh", {})
    if lead and m["lead_zh"] > lead.get("p75", 243) * 1.3:
        L.add("WARN", "A12", f"第一个“问题 N”之前有 {m['lead_zh']} 汉字，开头过长（语料 P75 = {lead.get('p75')}）")
    if not m["has_tail"]:
        L.add("WARN", "A07", "结尾没有创新点/局限/推广句（语料约 59% 的摘要有，评委据此判断作者是否清楚自己做了什么）")

    # 用词
    for p in AI_PHRASES:
        c = body.count(p)
        if c:
            L.add("WARN", "A08", f"套话/AI 味词 “{p}” ×{c}")
    fill = {w: body.count(w) for w in FILLER if body.count(w)}
    if sum(fill.values()) >= 4:
        L.add("WARN", "A18", "空转词偏多：" + "、".join(f"{w}×{c}" for w, c in fill.items()) + "（“进行了 X”改为直接写 X）")
    bw = body.count("本文")
    if bw > 6:
        L.add("INFO", "A18", f"“本文” ×{bw}，段首连续用会显得机械")
    band(th, "paren_per_k", m["paren_per_k"], L, "A13", "每千字括号数", fail_over_max=False)
    band(th, "quote_per_k", m["quote_per_k"], L, "A13", "每千字引号数", fail_over_max=False)
    band(th, "en_abbr_per_k", m["en_abbr_per_k"], L, "A15", "每千字英文缩写数", fail_over_max=False)
    for a in sorted(set(re.findall(r"\b[A-Z]{2,}\b", body))):
        if not re.search(r"[\u4e00-\u9fff）)][（(]?\s*" + re.escape(a) + r"\b", body) and not re.search(re.escape(a) + r"\s*[（(]", body):
            L.add("INFO", "A15", f"缩写 {a} 未见中文名释义（首次出现应写 中文名（{a}））")
    return L, m


def render(L: Lint, m: dict, src: str, th: dict) -> str:
    rows = ["# ABSTRACT_LINT — 摘要体检", "", f"对象：`{src}`", "",
            f"FAIL {L.count('FAIL')} · WARN {L.count('WARN')} · INFO {L.count('INFO')}", "",
            "## 指标（vs 优秀论文摘要语料 P25 / P50 / P75）", "", "| 指标 | 本篇 | P25 | P50 | P75 | 最大 |", "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for key, label in (("zh_chars", "汉字数"), ("num_count", "数字个数"), ("num_per_k", "数字/千字"), ("dec_count", "小数个数"),
                       ("sig4_count", "≥4 位有效数字"), ("max_nums_per_sentence", "单句最多数字"), ("sent_count", "句数"),
                       ("sent_median", "句长中位数"), ("sent_p90", "句长 P90"), ("problem_count", "提及问题数"), ("lead_zh", "开头段汉字"),
                       ("kw_count", "关键词数"), ("en_abbr_count", "英文缩写数"), ("paren_per_k", "括号/千字"), ("quote_per_k", "引号/千字")):
        s = th.get(key, {})
        rows.append(f"| {label} | {m.get(key, '')} | {s.get('p25', '')} | {s.get('p50', '')} | {s.get('p75', '')} | {s.get('max', '')} |")
    rows += [f"| 有结尾段 | {'是' if m.get('has_tail') else '否'} | | 语料 59% 有 | | |", ""]
    for lv in ("FAIL", "WARN", "INFO"):
        its = [i for i in L.items if i["level"] == lv]
        if not its:
            continue
        rows += [f"## {lv}（{len(its)}）", ""]
        rows += [f"- [{i['rule']}] {i['msg']}" for i in its]
        rows.append("")
    rows += ["## 规则说明", "",
             "A01 篇幅 · A02 数字密度 · A03 高位小数 · A04 单句堆数 · A05 问题覆盖与每问要素 · A06 关键词 · A07 结尾段 · A08 套话 ·",
             "A09 内部文件名 · A10 句长 · A12 段落结构 · A13 括号/引号 · A15 缩写 · A16 Markdown 残留 · A17 引用正文图表 · A18 空转词。",
             "分位阈值来自 `_references/abstract_corpus_stats.json`；> P75 记 WARN，> 语料最大值记 FAIL。", ""]
    return "\n".join(rows)


def resolve(target: Path) -> tuple[Path, Path]:
    if target.is_dir():
        return target / "abstract" / "sections" / "00_abstract.md", target / "abstract"
    return target, target.parent.parent if target.parent.name == "sections" else target.parent


def main() -> int:
    setup_stdout()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("target", help="摘要 .md 文件，或项目目录（读 abstract/sections/00_abstract.md）")
    ap.add_argument("--facts", default="")
    ap.add_argument("--problems", type=int, default=0)
    ap.add_argument("--out", default="")
    ap.add_argument("--json", default="")
    ap.add_argument("--strict", action="store_true")
    a = ap.parse_args()
    md, outdir = resolve(Path(a.target).resolve())
    if not md.exists():
        print(f"[lint] 找不到摘要文件 {md}")
        return 2
    facts_p = Path(a.facts) if a.facts else outdir / "ABSTRACT_FACTS.json"
    expected: list[int] = []
    if facts_p.exists():
        expected = [p["problem"] for p in load_json(facts_p)["problems"]]
    elif a.problems:
        expected = list(range(1, a.problems + 1))
    th = load_thresholds()
    L, m = lint(read_text(md), th, expected)
    out = Path(a.out) if a.out else outdir / "ABSTRACT_LINT.md"
    js = Path(a.json) if a.json else outdir / "abstract_lint.json"
    write_text(out, render(L, m, md.name, th))
    dump_json(js, {"source": md.name, "metrics": m, "items": L.items, "fail": L.count("FAIL"), "warn": L.count("WARN")})
    print(f"[lint] {md.name}：{m['zh_chars']} 汉字，{m['num_count']} 个数字，问题 {m['problems']}，关键词 {m['kw_count']} → "
          f"FAIL {L.count('FAIL')} / WARN {L.count('WARN')} / INFO {L.count('INFO')}（{out}）")
    for i in L.items:
        if i["level"] == "FAIL":
            print(f"  FAIL [{i['rule']}] {i['msg']}")
    return 1 if (a.strict and L.count("FAIL")) else 0


if __name__ == "__main__":
    raise SystemExit(main())
