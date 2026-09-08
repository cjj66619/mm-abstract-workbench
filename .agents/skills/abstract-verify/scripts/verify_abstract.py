"""verify_abstract.py — 摘要工作台第 5 步：摘要里的每个事实都能回到正文/报告（零漂移），限定词不丢。

用法：
    python .agents/skills/abstract-verify/scripts/verify_abstract.py <proj> [--abstract <md>]
        [--facts <proj>/abstract/ABSTRACT_FACTS.json] [--out <proj>/abstract/ABSTRACT_FACT_DIFF.md] [--strict]

检查项：
- V01 数字溯源：摘要每个数字（年份、"问题 N"除外）必须在数字池（正文 + reports/*.md）里；
       允许"约 / 近 / 超过 / 不到 / 以上 / 左右"引导的约数：约数的有效位 ≤3，且池中存在某数按同样位数四舍五入后相等 → PASS(约数)；
       否则 FAIL。
- V02 限定词保留：某个数字在正文里的**全部**出现都带限定词（假设 / 探索性 / 待复核 / 低置信 …），摘要里含该数字的句子也必须带限定词，否则 FAIL；
       正文里多数时候带强限定词的加粗术语（如某个"等效参数假设"）若在摘要里出现且所在句无限定词 → WARN。
- V03 关键词与缩写：关键词、英文缩写必须在正文里出现过（WARN）。
- V04 问题覆盖：摘要提及的问题号 = 正文问题号（FAIL）。
--strict 时 FAIL > 0 返回 1。人改完摘要后重跑本脚本即可。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "abstract-intake" / "scripts"))
from abstract_common import (  # noqa: E402
    HEDGE_WORDS, NUM, PROBLEM_MARK, STRONG_HEDGE, YEAR, load_json, norm_num, problem_index, read_text, sentences, setup_stdout, sig_digits,
    split_abstract_md, strip_markdown, write_text, zh,
)

APPROX = re.compile(r"(约|近|接近|超过|不到|不足|以上|以下|左右|以内|高于|低于|逾|余|多于|少于|达)\s*$")


def to_float(tok: str) -> float | None:
    t = tok.replace(",", "").replace("−", "-").replace("%", "")
    t = re.sub(r"\s*[×x]\s*10\^?(-?\d+)", r"e\1", t)
    try:
        return float(t)
    except ValueError:
        return None


def approx_match(tok: str, pool_vals: list[tuple[str, float]]) -> str:
    """约数匹配：按摘要数字的小数位数把池中数四舍五入后相等即可；返回匹配到的原值。"""
    v = to_float(tok)
    if v is None or sig_digits(tok) > 3:
        return ""
    dec = len(tok.split(".")[1].rstrip("%")) if "." in tok else 0
    pct = "%" in tok
    for raw, pv in pool_vals:
        cands = [pv] + ([pv * 100] if pct and abs(pv) <= 1 else [])
        for c in cands:
            if round(c, dec) == round(v, dec) and abs(c - v) <= max(abs(v), 1e-9) * 0.06:
                return raw
    return ""


def hedged_norms(facts: dict) -> dict[str, list[str]]:
    """正文中“每一次出现都带强限定词”的数字 → 限定词列表。"""
    occ: dict[str, list[list[str]]] = {}
    for sec in facts["problems"] + facts["extras"]:
        for n in sec["numbers"]:
            if "table" in n["tags"]:
                continue
            words = [w for w in STRONG_HEDGE if w in n["sentence"]]
            occ.setdefault(n["norm"], []).append(words)
    return {k: sorted({w for ws in v for w in ws}) for k, v in occ.items() if v and all(ws for ws in v)}


def hedged_terms(facts: dict) -> dict[str, list[str]]:
    """正文里多数时候被强限定词修饰的加粗术语：术语 → 限定词。"""
    total = facts.get("term_counts", {})
    secs = facts["problems"] + facts["extras"]
    hits: dict[str, set[str]] = {}
    for b, n in total.items():
        if not n or not (2 <= zh(b) <= 8) or re.search(r"[，。；：“”]|^问题|^第", b):
            continue
        strong: set[str] = set()
        n_hedged = 0
        for sec in secs:
            for h in sec["hedges"]:
                if b in h["sentence"]:
                    n_hedged += 1
                    strong.update(w for w in h["words"] if w in STRONG_HEDGE)
        if strong and n_hedged / n >= 0.5:
            hits[b] = strong
    return {b: sorted(ws) for b, ws in hits.items()}


def body_text(proj: Path, facts: dict) -> str:
    src = proj / facts["project"]["source_dir"]
    parts = [strip_markdown(read_text(p)) for p in sorted(src.glob("*.md"))]
    rep = proj / "reports"
    if rep.is_dir():
        parts += [read_text(p) for p in sorted(rep.glob("*.md"))]
    return "\n".join(parts)


def main() -> int:
    setup_stdout()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("proj")
    ap.add_argument("--abstract", default="")
    ap.add_argument("--facts", default="")
    ap.add_argument("--out", default="")
    ap.add_argument("--strict", action="store_true")
    a = ap.parse_args()
    proj = Path(a.proj).resolve()
    md = Path(a.abstract) if a.abstract else proj / "abstract" / "sections" / "00_abstract.md"
    facts_p = Path(a.facts) if a.facts else proj / "abstract" / "ABSTRACT_FACTS.json"
    out = Path(a.out) if a.out else proj / "abstract" / "ABSTRACT_FACT_DIFF.md"
    if not md.exists() or not facts_p.exists():
        print(f"[verify] 缺少 {md if not md.exists() else facts_p}")
        return 2
    facts = load_json(facts_p)
    parts = split_abstract_md(read_text(md))
    body, kws = parts["body"], parts["keywords"]
    pool = set(facts["number_pool"])
    pool_vals = [(p, v) for p in pool if (v := to_float(p)) is not None]
    hn = hedged_norms(facts)
    ht = hedged_terms(facts)
    full = body_text(proj, facts)

    rows: list[dict] = []
    fails = warns = 0
    seen: set[str] = set()
    for sent in sentences(body):
        for m in NUM.finditer(sent):
            tok = m.group(0)
            if YEAR.fullmatch(tok) or PROBLEM_MARK.search(sent[max(0, m.start() - 3): m.end()]):
                continue
            norm = norm_num(tok)
            key = norm + "|" + sent[:30]
            if key in seen:
                continue
            seen.add(key)
            left = sent[max(0, m.start() - 4): m.start()]
            if norm in pool:
                status, note = "PASS", ""
            else:
                hit = approx_match(tok, pool_vals) if (APPROX.search(left) or sig_digits(tok) <= 2) else ""
                if hit:
                    status, note = "PASS", f"约数 ← 正文 {hit}"
                else:
                    status, note = "FAIL", "正文与报告中都找不到该数字（也不是可接受的约数）；删掉或改回正文原值"
                    fails += 1
            if norm in hn and not any(w in sent for w in STRONG_HEDGE):
                status = "FAIL"
                note = (note + "；" if note else "") + f"正文中该数字始终带限定词（{'、'.join(hn[norm])}），摘要句里限定词丢了"
                fails += 1
            rows.append({"rule": "V01" if "限定" not in note else "V02", "status": status, "item": tok, "sentence": sent[:80], "note": note})
    for term, words in ht.items():
        for sent in sentences(body):
            if term in sent and not any(w in sent for w in HEDGE_WORDS):
                rows.append({"rule": "V02", "status": "WARN", "item": term, "sentence": sent[:80],
                             "note": f"正文用限定词（{'、'.join(words)}）修饰该术语，摘要此句为确定语气，请复核"})
                warns += 1
                break
    for k in kws:
        if k and k not in full and not (zh(k) >= 4 and any(k[i:i + 3] in full for i in range(len(k) - 2))):
            rows.append({"rule": "V03", "status": "WARN", "item": k, "sentence": "关键词", "note": "正文中未出现该关键词"})
            warns += 1
    for ab in sorted(set(re.findall(r"\b[A-Z][A-Za-z]*[A-Z][A-Za-z0-9\-]*\b|\b[A-Z]{2,}\b", body))):
        if ab not in full:
            rows.append({"rule": "V03", "status": "WARN", "item": ab, "sentence": "缩写", "note": "正文中未出现该缩写"})
            warns += 1
    exp = [p["problem"] for p in facts["problems"]]
    got = sorted({problem_index(m) for m in PROBLEM_MARK.finditer(body)} - {0})
    if exp and got != exp:
        rows.append({"rule": "V04", "status": "FAIL", "item": str(got), "sentence": "问题覆盖", "note": f"正文问题号为 {exp}"})
        fails += 1

    n_pass = sum(1 for r in rows if r["status"] == "PASS")
    L = ["# ABSTRACT_FACT_DIFF — 摘要事实溯源", "", f"摘要：`{md.name}`；事实账本：`{facts_p.name}`（数字池 {len(pool)} 个）", "",
         f"FAIL {fails} · WARN {warns} · PASS {n_pass}", "", "| 规则 | 结果 | 项 | 摘要句 | 说明 |", "| --- | --- | --- | --- | --- |"]
    for r in sorted(rows, key=lambda r: ({"FAIL": 0, "WARN": 1, "PASS": 2}[r["status"]], r["rule"])):
        L.append(f"| {r['rule']} | {r['status']} | {r['item']} | {r['sentence'].replace('|', '/')} | {r['note']} |")
    L += ["", "V01 数字溯源 · V02 限定词保留 · V03 关键词/缩写出自正文 · V04 问题覆盖。FAIL 必须清零；WARN 逐条人工确认。", ""]
    write_text(out, "\n".join(L))
    n_num = sum(1 for r in rows if r["rule"] in ("V01", "V02") and r["item"][:1].isdigit())
    print(f"[verify] {md.name}：数字 {n_num} 个 → "
          f"FAIL {fails} / WARN {warns} / PASS {n_pass}（{out}）")
    for r in rows:
        if r["status"] == "FAIL":
            print(f"  FAIL [{r['rule']}] {r['item']}：{r['note']}｜{r['sentence'][:50]}")
    return 1 if (a.strict and fails) else 0


if __name__ == "__main__":
    raise SystemExit(main())
