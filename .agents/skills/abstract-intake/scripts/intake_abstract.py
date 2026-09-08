"""intake_abstract.py — 摘要工作台第 1 步：读取项目正文（润色稿优先）与报告，建立"摘要事实账本"。

用法：
    python .agents/skills/abstract-intake/scripts/intake_abstract.py <proj> [--source auto|polish|frame|paper]
                                                                     [--out <proj>/abstract/ABSTRACT_FACTS.json]

只读 <proj>；只写 --out 一个文件。
做的事：
1. 选正文来源：--source auto 时按 polish/sections → frame/sections → paper/sections 取第一个存在的目录；
2. 按一级标题识别章节角色（problem / robustness / evaluation / analysis / ...），"问题 N"章按 N 编号；
3. 从每章抽取：小节标题、加粗术语、英文缩写、带上下文的数字（句子 + 标签）、结论句、限定词句；
4. 从 reports/*.md 抽取数字池（摘要里每个数字必须能在正文或报告里找到）；
5. 记录当前摘要（若有）的指标，作为 lint/报告的"改前"基线。
输出 JSON 供 select_facts.py / lint_abstract.py / verify_abstract.py 使用。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from abstract_common import (  # noqa: E402
    COMPARE_MARK, DATA_MARK, HEDGE_WORDS, METRIC_MARK, NUM, PARAM_MARK, RESULT_MARK, UNIT_AFTER, YEAR, abstract_metrics,
    dump_json, heading_role, norm_num, problem_index_of_text, read_text, sentences, setup_stdout, sig_digits,
    split_abstract_md, strip_markdown, zh,
)

SOURCE_ORDER = ("polish", "frame", "paper")


def pick_source(proj: Path, want: str) -> Path | None:
    cands = [proj / want / "sections"] if want != "auto" else [proj / s / "sections" for s in SOURCE_ORDER]
    for c in cands:
        if c.is_dir() and any(c.glob("*.md")):
            return c
    return None


def has_any(s: str, words: list[str]) -> bool:
    return any(w in s for w in words)


def tag_sentence(sent: str, in_summary: bool, in_table: bool) -> list[str]:
    tags = []
    if has_any(sent, METRIC_MARK):
        tags.append("metric")
    if has_any(sent, DATA_MARK):
        tags.append("data")
    if has_any(sent, PARAM_MARK):
        tags.append("param")
    if has_any(sent, RESULT_MARK):
        tags.append("result")
    if has_any(sent, COMPARE_MARK):
        tags.append("compare")
    if has_any(sent, HEDGE_WORDS):
        tags.append("hedged")
    if in_summary:
        tags.append("summary")
    if in_table:
        tags.append("table")
    return tags


def number_kind(sent: str, m: re.Match) -> dict:
    """数字局部上下文：前后 14 字的窗口里有没有指标词、后面接的单位、是否是 x/y 形式。"""
    tok = m.group(0)
    left = sent[max(0, m.start() - 14): m.start()]
    right = sent[m.end(): m.end() + 14]
    unit = UNIT_AFTER.match(right)
    frac = bool(re.match(r"\s*/\s*\d", right)) or bool(re.search(r"\d\s*/\s*$", left))
    rng = bool(re.match(r"\s*[–\-~～]\s*\d", right)) or bool(re.search(r"\d\s*[–\-~～]\s*$", left))
    metric_local = any(w in left + right for w in METRIC_MARK)
    small_int = bool(re.fullmatch(r"-?\d{1,2}", tok)) and not unit and not frac and "%" not in tok
    return {"unit": unit.group(1) if unit else "", "fraction": frac, "range": rng, "metric_local": metric_local,
            "small_int": small_int, "window": (left + "【" + tok + "】" + right).strip()}


def parse_section(path: Path) -> dict:
    text = read_text(path)
    plain_all = strip_markdown(text)
    lines = text.split("\n")
    h1 = ""
    subs: list[dict] = []
    cur_sub = ""
    in_code = False
    bold: list[str] = []
    abbrs: dict[str, int] = {}
    numbers: list[dict] = []
    claims: list[dict] = []
    hedges: list[dict] = []
    zh_total = 0
    para_buf: list[str] = []
    para_start = 0
    display_math = 0

    def flush_para(end_line: int) -> None:
        nonlocal para_buf, zh_total
        if not para_buf:
            return
        raw = " ".join(para_buf).strip()
        para_buf = []
        if not raw or raw.startswith("$$"):
            return
        in_table = raw.startswith("|")
        plain = strip_markdown(raw)
        plain = re.sub(r"\$\$.*?\$\$", " ", plain)
        plain = re.sub(r"\{#[^}]*\}", "", plain)
        plain = re.sub(r"@(fig|tbl|eq|sec):[\w\-]+", "", plain)
        zh_total += zh(plain)
        in_summary = bool(re.search(r"小结|总结|结论", cur_sub))
        for sent in sentences(plain):
            sent = sent.strip()
            tags = tag_sentence(sent, in_summary, in_table)
            for m in NUM.finditer(sent):
                tok = m.group(0)
                if YEAR.fullmatch(tok):
                    continue
                kind = number_kind(sent, m)
                numbers.append({"raw": tok, "norm": norm_num(tok), "sig": sig_digits(tok), "sentence": sent[:240],
                                "subsection": cur_sub, "line": para_start, "tags": tags, **kind})
            if "result" in tags and not in_table and zh(sent) >= 12:
                claims.append({"sentence": sent[:300], "subsection": cur_sub, "line": para_start, "tags": tags})
            if "hedged" in tags and not in_table:
                hedges.append({"sentence": sent[:300], "subsection": cur_sub, "line": para_start,
                               "words": [w for w in HEDGE_WORDS if w in sent]})

    for i, line in enumerate(lines, 1):
        s = line.strip()
        if s.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        if s.startswith("$$"):
            display_math += 1
        m = re.match(r"^(#{1,6})\s+(.*)$", s)
        if m:
            flush_para(i)
            level, title = len(m.group(1)), m.group(2).strip()
            if level == 1 and not h1:
                h1 = title
            else:
                subs.append({"level": level, "title": title, "line": i})
                cur_sub = title
            continue
        if not s:
            flush_para(i)
            continue
        if not para_buf:
            para_start = i
        para_buf.append(s)
        for b in re.findall(r"\*\*(.+?)\*\*", s):
            b = b.strip().rstrip("。：:")
            if 1 < zh(b) + len(re.findall(r"[A-Za-z]", b)) <= 24 and b not in bold:
                bold.append(b)
        for a in re.findall(r"\b[A-Z][A-Za-z]*[A-Z][A-Za-z0-9\-]*\b|\b[A-Z]{2,}\b", strip_markdown(s)):
            abbrs[a] = abbrs.get(a, 0) + 1
    flush_para(len(lines))

    role = heading_role(h1, path.name)
    term_counts = {b: plain_all.count(b) for b in bold}
    return {"file": path.name, "title": h1, "role": role, "problem": problem_index_of_text(h1) if role == "problem" else 0,
            "zh_chars": zh_total, "subsections": subs, "bold_terms": bold[:60], "term_counts": term_counts,
            "abbreviations": dict(sorted(abbrs.items(), key=lambda kv: -kv[1])[:40]), "display_math": display_math,
            "numbers": numbers, "claims": claims, "hedges": hedges}


def report_numbers(reports_dir: Path) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    if not reports_dir.is_dir():
        return out
    for p in sorted(reports_dir.glob("*.md")):
        toks = {norm_num(m.group(0)) for m in NUM.finditer(read_text(p)) if not YEAR.fullmatch(m.group(0))}
        out[p.name] = sorted(toks)
    return out


def read_meta(proj: Path) -> dict:
    """从 project.yaml / paper/paper.yaml 里拿 title / contest / keywords（简单逐行解析，不依赖 PyYAML）。"""
    meta: dict = {}
    for rel in ("project.yaml", "paper/paper.yaml"):
        p = proj / rel
        if not p.exists():
            continue
        for line in read_text(p).split("\n"):
            m = re.match(r"^\s*(title|contest|name|lang|language)\s*:\s*(.+?)\s*$", line)
            if m and m.group(1) not in meta:
                meta[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    return meta


def main() -> int:
    setup_stdout()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("proj")
    ap.add_argument("--source", default="auto", choices=["auto", *SOURCE_ORDER])
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    proj = Path(a.proj).resolve()
    src = pick_source(proj, a.source)
    if not src:
        print(f"[intake] 找不到正文目录（{'/'.join(SOURCE_ORDER)}/sections）：{proj}")
        return 2
    out = Path(a.out) if a.out else proj / "abstract" / "ABSTRACT_FACTS.json"

    sections = [parse_section(p) for p in sorted(src.glob("*.md"))]
    body_secs = [s for s in sections if s["role"] not in ("abstract", "references", "appendix")]
    problems = sorted([s for s in body_secs if s["role"] == "problem"], key=lambda s: s["problem"])
    extras = [s for s in body_secs if s["role"] != "problem"]

    pool: set[str] = set()
    for s in body_secs:
        pool.update(n["norm"] for n in s["numbers"])
    reports = report_numbers(proj / "reports")
    for toks in reports.values():
        pool.update(toks)

    all_terms = sorted({b for s in body_secs for b in s["bold_terms"]})
    body_plain = "\n".join(strip_markdown(read_text(src / s["file"])) for s in body_secs)
    term_counts = {b: body_plain.count(b) for b in all_terms}

    current = None
    abs_path = src / "00_abstract.md"
    if not abs_path.exists():
        cands = [s for s in sections if s["role"] == "abstract"]
        abs_path = src / cands[0]["file"] if cands else abs_path
    if abs_path.exists():
        parts = split_abstract_md(read_text(abs_path))
        current = {"path": str(abs_path.relative_to(proj)).replace("\\", "/"), "keywords": parts["keywords"],
                   "paragraphs": len(parts["paragraphs"]), "metrics": abstract_metrics(parts["body"], parts["keywords"])}

    facts = {
        "project": {**read_meta(proj), "root": proj.name, "source_dir": str(src.relative_to(proj)).replace("\\", "/"),
                    "sections": [{"file": s["file"], "title": s["title"], "role": s["role"], "problem": s["problem"],
                                  "zh_chars": s["zh_chars"]} for s in sections]},
        "current_abstract": current,
        "problems": problems,
        "extras": extras,
        "reports": {k: len(v) for k, v in reports.items()},
        "term_counts": term_counts,
        "number_pool": sorted(pool),
    }
    dump_json(out, facts)
    print(f"[intake] 正文来源 {facts['project']['source_dir']}：{len(sections)} 个文件，问题章 {len(problems)} 个 "
          f"({', '.join(str(p['problem']) for p in problems)})，其它正文章 {len(extras)} 个")
    for p in problems:
        print(f"  问题{p['problem']} {p['title'][:30]}：{p['zh_chars']} 字，数字 {len(p['numbers'])}，结论句 {len(p['claims'])}，限定句 {len(p['hedges'])}")
    if current:
        m = current["metrics"]
        print(f"[intake] 当前摘要 {current['path']}：{m['zh_chars']} 字，数字 {m['num_count']}（{m['num_per_k']}/千字），关键词 {m['kw_count']}")
    print(f"[intake] 数字池 {len(pool)} 个（正文 + {len(reports)} 份报告）→ {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
