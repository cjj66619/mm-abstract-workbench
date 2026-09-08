"""select_facts.py — 摘要工作台第 2 步：从事实账本里挑"值得进摘要"的事实，给出每段的字数与数字预算，写成计划。

用法：
    python .agents/skills/abstract-select/scripts/select_facts.py <proj>
        [--facts <proj>/abstract/ABSTRACT_FACTS.json]
        [--out-json <proj>/abstract/ABSTRACT_CANDIDATES.json] [--out-md <proj>/abstract/ABSTRACT_PLAN.md]
        [--target-zh 1137] [--num-budget 24] [--per-problem 4]

原则（来自优秀论文摘要语料 `_references/abstract_corpus_stats.json`）：
- 整篇 900–1400 汉字、15–24 个数字；每问 3–5 个数字，优先"最终指标 / 对照差距 / 判决结论"，其次数据规模，参数几乎不进摘要；
- 带限定词（假设 / 探索性 / 待复核 / 低置信…）的结论进摘要时必须带着限定词；
- ≥4 位有效数字建议在摘要里取约数（正文保留原值），计划里给出建议写法；
- 计划只是候选与预算，写摘要的人/Agent 按 abstract-write/SKILL.md 决定取舍。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "abstract-intake" / "scripts"))
from abstract_common import HEDGE_WORDS, dump_json, load_json, load_thresholds, setup_stdout, write_text, zh  # noqa: E402

SUMMARY_RE = re.compile(r"小结|总结|结论")


def round_hint(raw: str, sig: int) -> str:
    """≥4 位有效数字 → 建议约数（保留 2–3 位有效数字，百分数/整数照抄）。"""
    if sig < 4 or "%" in raw or "." not in raw:
        return ""
    try:
        v = float(raw.replace(",", "").replace("−", "-"))
    except ValueError:
        return ""
    if abs(v) < 1:
        return f"约 {v:.2f}"
    if abs(v) < 100:
        return f"约 {v:.1f}"
    return f"约 {round(v):d}"


def score_number(n: dict, dup: int) -> float:
    """单次出现的重要性：紧邻指标词的“结果数”最高，参数、表格内、无单位小整数最低。"""
    t = set(n["tags"])
    s = 0.0
    s += 4 if n.get("metric_local") else (1.5 if "metric" in t else 0)
    s += 2 if "result" in t else 0
    s += 2 if "summary" in t else 0
    s += 1 if "compare" in t else 0
    s += 1 if n.get("fraction") else 0
    s += 0.5 if ("%" in n["raw"] or n.get("unit")) else 0
    s -= 3 if "table" in t else 0
    s -= 2 if ("param" in t and not n.get("metric_local")) else 0
    s -= 1 if ("data" in t and not n.get("metric_local") and "result" not in t) else 0
    s -= (2 if n.get("metric_local") else 4) if n.get("small_int") else 0
    s -= 1.5 if n["sig"] >= 4 else 0
    s += min(dup - 1, 4) * 0.5
    return round(s, 2)


def score_claim(c: dict) -> float:
    t = set(c["tags"])
    sent = c["sentence"]
    s = 0.0
    s += 3 if SUMMARY_RE.search(c["subsection"]) else 0
    s += 2 if "metric" in t else 0
    s += 1 if "compare" in t else 0
    s += 1 if re.search(r"最终|综上|表明|说明|因此|可见|推荐|判决为|结论", sent) else 0
    s -= 2 if zh(sent) > 150 else 0
    s -= 1 if zh(sent) < 20 else 0
    s -= 2 if re.search(r"^(这里|其中|此外|另|注|回到题面|本章|本节)", sent) else 0
    s -= 3 if re.search(r"(如下|如下几点|以下几方面|[:：])\s*$", sent) else 0
    s -= 1 if re.search(r"见表|见图|如表|如图|@|面板|图\s|表\s", sent) else 0
    s -= 1 if re.search(r"问题[一二三四五六七八九十\d]+(需要|将|将会|中讨论|回答)", sent) else 0
    return round(s, 2)


def pick_numbers(sec: dict, k: int) -> list[dict]:
    """按归一化值合并重复出现，取分数最高的 k 个；每个带最佳上下文句与限定词提示。"""
    groups: dict[str, list[dict]] = {}
    for n in sec["numbers"]:
        groups.setdefault(n["norm"], []).append(n)
    cands = []
    for norm, occ in groups.items():
        best = max(occ, key=lambda x: (score_number(x, len(occ)), -len(x["sentence"])))
        sc = score_number(best, len(occ))
        hedges = sorted({w for o in occ for w in HEDGE_WORDS if w in o["sentence"]})
        cands.append({"value": best["raw"], "norm": norm, "score": sc, "occurrences": len(occ), "tags": sorted(set(sum((o["tags"] for o in occ), []))),
                      "context": best["sentence"], "window": best.get("window", ""), "subsection": best["subsection"], "line": best["line"],
                      "must_hedge": hedges, "round_hint": round_hint(best["raw"], best["sig"])})
    cands.sort(key=lambda c: (-c["score"], -c["occurrences"]))
    return cands[:k]


def pick_claims(sec: dict, k: int = 5) -> list[dict]:
    seen: set[str] = set()
    out = []
    for c in sorted(sec["claims"], key=lambda c: -score_claim(c)):
        key = c["sentence"][:40]
        if key in seen:
            continue
        seen.add(key)
        out.append({"score": score_claim(c), "sentence": c["sentence"], "subsection": c["subsection"], "line": c["line"],
                    "must_hedge": [w for w in HEDGE_WORDS if w in c["sentence"]]})
        if len(out) >= k:
            break
    return out


def method_chain(sec: dict) -> list[str]:
    h2 = [s["title"] for s in sec["subsections"] if s["level"] == 2]
    h2 = [re.sub(r"^\d+(\.\d+)*\s*", "", t) for t in h2]
    return h2


def keyword_candidates(facts: dict) -> list[str]:
    """关键词候选：题目 + 在正文里反复出现的加粗术语（短名词）+ 高频英文缩写 + 当前摘要关键词。"""
    freq: dict[str, int] = {}
    for sec in facts["problems"] + facts["extras"]:
        for b, c in sec.get("term_counts", {}).items():
            b = b.strip("。，；：")
            if 2 <= zh(b) <= 8 and c >= 3 and not re.search(r"[。，；“”、：]|^问题|^第|不|没有|均|未|是|了|的$", b):
                freq[b] = freq.get(b, 0) + c
        for a, c in sec["abbreviations"].items():
            if c >= 8 and 3 <= len(a) <= 12:
                freq[a] = freq.get(a, 0) + c
    title = facts["project"].get("title", "")
    out = [title] if title else []
    out += [k for k, _ in sorted(freq.items(), key=lambda kv: -kv[1])[:12]]
    cur = (facts.get("current_abstract") or {}).get("keywords", [])
    out += [k for k in cur if k not in out]
    return out


def budget(facts: dict, th: dict, target_zh: int, num_budget: int, per_problem: int) -> dict:
    n_prob = max(len(facts["problems"]), 1)
    has_rob = any(e["role"] == "robustness" for e in facts["extras"])
    has_eval = any(e["role"] == "evaluation" for e in facts["extras"])
    lead = 0.13
    rob = 0.08 if has_rob else 0.0
    tail = 0.09
    body = 1.0 - lead - rob - tail
    per = body / n_prob
    plan = {"lead": {"zh": round(target_zh * lead), "nums": min(2, num_budget)},
            "problems": {p["problem"]: {"zh": round(target_zh * per), "nums": per_problem} for p in facts["problems"]},
            "robustness": {"zh": round(target_zh * rob), "nums": 2 if has_rob else 0},
            "tail": {"zh": round(target_zh * tail), "nums": 0, "source": "evaluation" if has_eval else "problems"},
            "total_zh": target_zh, "total_nums": num_budget,
            "corpus": {k: th.get(k, {}) for k in ("zh_chars", "num_count", "sig4_count", "max_nums_per_sentence", "kw_count", "lead_zh", "sent_p90")}}
    return plan


def render_plan(facts: dict, cands: dict) -> str:
    b = cands["budget"]
    cur = facts.get("current_abstract")
    L = ["# ABSTRACT_PLAN — 摘要写作计划（候选事实 + 预算）", "",
         f"项目：{facts['project'].get('title', facts['project'].get('root', ''))}；正文来源：`{facts['project']['source_dir']}`；"
         f"问题章 {len(facts['problems'])} 个。本文件由 `select_facts.py` 生成，供写摘要时逐段取舍；写完后跑 `lint_abstract.py` 与 `verify_abstract.py`。", ""]
    if cur:
        m = cur["metrics"]
        L += ["## 0 当前摘要基线", "",
              f"`{cur['path']}`：{m['zh_chars']} 汉字、{m['num_count']} 个数字（{m['num_per_k']}/千字）、≥4 位有效数字 {m['sig4_count']} 个、"
              f"单句最多 {m['max_nums_per_sentence']} 个数字、关键词 {m['kw_count']} 个、{'有' if m['has_tail'] else '无'}结尾段。", ""]
    c = b["corpus"]
    L += ["## 1 预算（依据优秀论文摘要语料）", "",
          "| 段落 | 目标汉字 | 数字预算 | 语料参考 |", "| --- | ---: | ---: | --- |",
          f"| 开头（背景 + 总体方案） | {b['lead']['zh']} | ≤{b['lead']['nums']} | 首段汉字 P25–P75 = "
          f"{c.get('lead_zh', {}).get('p25', '?')}–{c.get('lead_zh', {}).get('p75', '?')} |"]
    for k, v in b["problems"].items():
        L.append(f"| 问题{k} | {v['zh']} | ≤{v['nums']} | 每问：矛盾/输入 → 方法与改进点 → 1–3 个可核验结果 → 验证动作 |")
    if b["robustness"]["zh"]:
        L.append(f"| 模型检验 | {b['robustness']['zh']} | ≤{b['robustness']['nums']} | 只给总体稳定性结论 + 最敏感因素 |")
    L += [f"| 结尾（创新 / 局限 / 推广） | {b['tail']['zh']} | 0 | 语料 59% 有结尾段；来源：{b['tail']['source']} 章 |",
          f"| **合计** | **{b['total_zh']}** | **≤{b['total_nums']}** | 汉字 P25–P75 = "
          f"{c.get('zh_chars', {}).get('p25', '?')}–{c.get('zh_chars', {}).get('p75', '?')}；"
          f"数字 P50–P75 = {c.get('num_count', {}).get('p50', '?')}–{c.get('num_count', {}).get('p75', '?')}；"
          f"≥4 位有效数字 P75 = {c.get('sig4_count', {}).get('p75', '?')} |", ""]

    L += ["## 2 开头段候选（背景与总体方案）", ""]
    for s in cands["lead"]:
        L.append(f"- [{s['role']}] {s['sentence']}")
    L.append("")
    for p in cands["problems"]:
        L += [f"## 3.{p['problem']} 问题{p['problem']}：{p['title']}", "",
              f"方法链（二级标题）：{' → '.join(p['method_chain']) or '（无二级标题）'}", "",
              f"术语/加粗：{'、'.join(p['bold_terms'][:12]) or '（无）'}", "",
              "### 候选数字（按重要性排序，取前 ≤{} 个）".format(b["problems"].get(p["problem"], {}).get("nums", 4)), "",
              "| 分 | 数字 | 建议写法 | 标签 | 限定词 | 上下文 |", "| ---: | --- | --- | --- | --- | --- |"]
        for n in p["numbers"]:
            L.append(f"| {n['score']} | {n['value']} | {n['round_hint'] or '照抄'} | {','.join(t for t in n['tags'] if t not in ('data', 'param'))} | "
                     f"{'、'.join(n['must_hedge']) or ''} | {n['context'][:110].replace('|', '/')} |")
        L += ["", "### 候选结论句", ""]
        for cl in p["claims"]:
            hed = f"（须保留限定词：{'、'.join(cl['must_hedge'])}）" if cl["must_hedge"] else ""
            L.append(f"- [{cl['score']}] {cl['sentence'][:200]}{hed}")
        L.append("")
    if cands["robustness"]:
        r = cands["robustness"]
        L += [f"## 4 模型检验候选：{r['title']}", "", "| 分 | 数字 | 建议写法 | 限定词 | 上下文 |", "| ---: | --- | --- | --- | --- |"]
        for n in r["numbers"]:
            L.append(f"| {n['score']} | {n['value']} | {n['round_hint'] or '照抄'} | {'、'.join(n['must_hedge'])} | {n['context'][:110].replace('|', '/')} |")
        L.append("")
        for cl in r["claims"]:
            L.append(f"- [{cl['score']}] {cl['sentence'][:200]}")
        L.append("")
    L += ["## 5 结尾段候选（创新 / 局限 / 推广）", ""]
    for s in cands["tail"]:
        L.append(f"- [{s['role']}] {s['sentence']}")
    L += ["", "## 6 关键词候选（取 4–7 个：研究对象 + 核心模型 + 主要方法 + 任务性质）", "",
          "、".join(cands["keywords"]), "",
          "## 7 必须保留限定词的结论（摘要里出现这些结论时不得改成确定语气）", ""]
    for h in cands["hedged_claims"][:15]:
        L.append(f"- 问题{h['problem'] or '-'}｜{'、'.join(h['words'])}｜{h['sentence'][:160]}")
    L += ["", "## 8 写作顺序", "",
          "1. 先写每问的一句话结论（各 ≤ 40 字），再往前补方法、往后补验证；", "2. 开头段最后一句交代总体方案，与各问首句衔接；",
          "3. 结尾段只写创新、局限、推广三件事，不重复结果；", "4. 关键词 4–7 个；",
          "5. 跑 `lint_abstract.py --strict` 与 `verify_abstract.py --strict`，FAIL 清零后写 `ABSTRACT_REPORT.md`。", ""]
    return "\n".join(L)


def lead_candidates(facts: dict) -> list[dict]:
    out = []
    for e in facts["extras"]:
        if e["role"] in ("restatement", "analysis"):
            for c in e["claims"][:4]:
                out.append({"role": e["role"], "sentence": c["sentence"][:200]})
    if not out:
        for p in facts["problems"][:1]:
            for c in p["claims"][:2]:
                out.append({"role": "problem", "sentence": c["sentence"][:200]})
    return out[:8]


def tail_candidates(facts: dict) -> list[dict]:
    out = []
    for e in facts["extras"]:
        if e["role"] == "evaluation":
            for b in e["bold_terms"][:10]:
                out.append({"role": "evaluation/加粗要点", "sentence": b})
            for c in e["claims"][:6]:
                out.append({"role": "evaluation", "sentence": c["sentence"][:200]})
    return out[:16]


def main() -> int:
    setup_stdout()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("proj")
    ap.add_argument("--facts", default="")
    ap.add_argument("--out-json", default="")
    ap.add_argument("--out-md", default="")
    ap.add_argument("--target-zh", type=int, default=0)
    ap.add_argument("--num-budget", type=int, default=0)
    ap.add_argument("--per-problem", type=int, default=4)
    a = ap.parse_args()
    proj = Path(a.proj).resolve()
    facts_p = Path(a.facts) if a.facts else proj / "abstract" / "ABSTRACT_FACTS.json"
    if not facts_p.exists():
        print(f"[select] 缺少事实账本 {facts_p}，先跑 intake_abstract.py")
        return 2
    facts = load_json(facts_p)
    th = load_thresholds()
    target_zh = a.target_zh or int(th.get("zh_chars", {}).get("p50", 1150))
    num_budget = a.num_budget or int(th.get("num_count", {}).get("p75", 20))
    b = budget(facts, th, target_zh, num_budget, a.per_problem)

    problems = []
    hedged = []
    for p in facts["problems"]:
        k = b["problems"][p["problem"]]["nums"]
        problems.append({"problem": p["problem"], "title": p["title"], "file": p["file"], "method_chain": method_chain(p),
                         "bold_terms": p["bold_terms"], "numbers": pick_numbers(p, k + 4), "claims": pick_claims(p)})
        for h in p["hedges"]:
            hedged.append({"problem": p["problem"], **h})
    rob = None
    for e in facts["extras"]:
        if e["role"] == "robustness":
            rob = {"title": e["title"], "file": e["file"], "numbers": pick_numbers(e, 5), "claims": pick_claims(e, 4)}
            for h in e["hedges"]:
                hedged.append({"problem": 0, **h})
    cands = {"budget": b, "lead": lead_candidates(facts), "problems": problems, "robustness": rob, "tail": tail_candidates(facts),
             "keywords": keyword_candidates(facts), "hedged_claims": hedged}
    out_json = Path(a.out_json) if a.out_json else proj / "abstract" / "ABSTRACT_CANDIDATES.json"
    out_md = Path(a.out_md) if a.out_md else proj / "abstract" / "ABSTRACT_PLAN.md"
    dump_json(out_json, cands)
    write_text(out_md, render_plan(facts, cands))
    print(f"[select] 目标 {target_zh} 汉字 / ≤{num_budget} 个数字；每问 ≤{a.per_problem} 个数字 → {out_md.name}, {out_json.name}")
    for p in problems:
        top = "、".join(n["value"] for n in p["numbers"][:4])
        print(f"  问题{p['problem']}：候选数字 {top}；结论句 {len(p['claims'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
