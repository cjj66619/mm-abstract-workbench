"""abstract_corpus_stats.py — 从一批优秀论文 PDF 中抽出摘要页，统计摘要专用指标，生成 lint 阈值文件。

用法：
    python .agents/skills/abstract-corpus/scripts/abstract_corpus_stats.py <pdf 目录> [--year 23]
        [--out-json .agents/skills/_references/abstract_corpus_stats.json]
        [--out-md   .agents/skills/_references/abstract_corpus_stats.md]
        [--append]            # 在已有 json 的 papers 上追加（分批喂不同年份）
        [--dump-dir <目录>]   # 可选：把切出的摘要纯文本落盘（本地看语料用，不要提交）

依赖：pymupdf（仅维护语料阈值时运行；输出项目与其它脚本不需要）。
摘要边界：前 6 页内第一次出现"摘要"到第一次出现"关键词/关键字"之间；关键词行到下一页或"目录"之前。
仓库只保存统计结果，不保存 PDF 与摘要正文。
"""
from __future__ import annotations

import argparse
import json
import re
import statistics as st
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REF = HERE.parents[1] / "_references"
sys.path.insert(0, str(HERE.parents[1] / "abstract-intake" / "scripts"))
from abstract_common import abstract_metrics, setup_stdout, zh  # noqa: E402


def cut_abstract(pages: list[str]) -> tuple[str, list[str]] | None:
    text = ""
    for i, p in enumerate(pages[:6]):
        text += f"\n\x0c{i}\n" + p
    m = re.search(r"摘\s*要\s*[:：]?", text)
    if not m:
        return None
    rest = text[m.end():]
    k = re.search(r"关\s*键\s*[词字]\s*[:：]?", rest)
    if not k:
        return None
    body_raw, kw_raw = rest[: k.start()], rest[k.end():]
    stop = re.search(r"\x0c\d+\n|目\s*录", kw_raw)
    if stop:
        kw_raw = kw_raw[: stop.start()]
    lines = [l.strip() for l in body_raw.splitlines()]
    lines = [l for l in lines if l and not re.fullmatch(r"\d{1,2}|\x0c\d+", l)]
    body = "".join(lines)
    kws = [x.strip() for x in re.split(r"[；;，,、\n]", kw_raw) if zh(x.strip()) or re.search(r"[A-Za-z]{2,}", x)]
    return body, kws[:15]


def pdf_abstract(path: Path) -> tuple[str, list[str]] | None:
    import pymupdf  # type: ignore

    doc = pymupdf.open(path)
    pages = [doc[i].get_text() for i in range(min(6, doc.page_count))]
    return cut_abstract(pages)


def percentiles(vals: list[float]) -> dict:
    if not vals:
        return {}
    v = sorted(vals)
    q = st.quantiles(v, n=4) if len(v) >= 4 else [v[0], st.median(v), v[-1]]
    return {"min": v[0], "p25": round(q[0], 2), "p50": round(st.median(v), 2), "p75": round(q[2], 2), "max": v[-1],
            "mean": round(st.mean(v), 2)}


def build(papers: dict[str, dict]) -> dict:
    keys = ["zh_chars", "num_count", "num_per_k", "dec_count", "sig4_count", "max_nums_per_sentence", "sent_count",
            "sent_median", "sent_p90", "sent_max", "problem_mentions", "problem_count", "lead_zh", "kw_count", "en_abbr_count",
            "en_abbr_per_k", "paren_per_k", "quote_per_k", "slash_list", "ai_phrase_count"]
    summary = {k: percentiles([p[k] for p in papers.values() if isinstance(p.get(k), (int, float))]) for k in keys}
    summary["has_tail_ratio"] = round(sum(1 for p in papers.values() if p.get("has_tail")) / max(len(papers), 1), 2)
    ai_total: dict[str, int] = {}
    for p in papers.values():
        for w, c in p.get("ai_hits", {}).items():
            ai_total[w] = ai_total.get(w, 0) + c
    return {"n": len(papers), "unit": "摘要正文汉字数；密度按每千汉字；年份不计入数字", "summary": summary,
            "ai_phrase_totals": ai_total, "papers": papers}


def to_md(data: dict) -> str:
    s = data["summary"]
    out = ["# 优秀论文摘要语料统计", "",
           f"n = {data['n']} 篇；摘要正文 = “摘要”起、“关键词”止；{data['unit']}。由 `abstract-corpus/scripts/abstract_corpus_stats.py` 生成，勿手改。",
           "", "| 指标 | min | P25 | P50 | P75 | max | mean |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for k, v in s.items():
        if isinstance(v, dict) and v:
            out.append(f"| {k} | {v['min']} | {v['p25']} | {v['p50']} | {v['p75']} | {v['max']} | {v['mean']} |")
    out += ["", f"结尾段（创新/优缺点/推广）出现比例：{s['has_tail_ratio']}", "",
            "## AI 高频措辞在全部摘要中的合计出现次数", "",
            "、".join(f"{w}: {c}" for w, c in sorted(data["ai_phrase_totals"].items())) or "（无）", "",
            "## 各篇明细", "",
            "| 论文 | 汉字 | 数字 | 数字/千字 | ≥4位有效数字 | 单句最多数字 | 句数 | 句长中位 | 问题提及/问题数 | 首段汉字 | 结尾段 | 关键词 |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: |"]
    for name, p in data["papers"].items():
        out.append(f"| {name} | {p['zh_chars']} | {p['num_count']} | {p['num_per_k']} | {p['sig4_count']} | {p['max_nums_per_sentence']} | "
                   f"{p['sent_count']} | {p['sent_median']} | {p['problem_mentions']}/{p['problem_count']} | {p['lead_zh']} | "
                   f"{'是' if p['has_tail'] else '否'} | {p['kw_count']} |")
    return "\n".join(out) + "\n"


def main() -> int:
    setup_stdout()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf_dir")
    ap.add_argument("--year", default="")
    ap.add_argument("--out-json", default=str(REF / "abstract_corpus_stats.json"))
    ap.add_argument("--out-md", default=str(REF / "abstract_corpus_stats.md"))
    ap.add_argument("--append", action="store_true")
    ap.add_argument("--dump-dir", default="")
    a = ap.parse_args()

    out_json = Path(a.out_json)
    papers: dict[str, dict] = {}
    if a.append and out_json.exists():
        papers = json.loads(out_json.read_text(encoding="utf-8")).get("papers", {})
    pdfs = sorted(Path(a.pdf_dir).rglob("*.pdf"))
    if not pdfs:
        print(f"[corpus] 未找到 PDF：{a.pdf_dir}")
        return 2
    dump = Path(a.dump_dir) if a.dump_dir else None
    if dump:
        dump.mkdir(parents=True, exist_ok=True)
    skipped = []
    for p in pdfs:
        got = pdf_abstract(p)
        if not got or zh(got[0]) < 200:
            skipped.append(p.name)
            continue
        body, kws = got
        name = p.stem if not a.year else f"{a.year}:{p.stem}"
        papers[name] = abstract_metrics(body, kws)
        if dump:
            (dump / f"{p.stem}.txt").write_text(body + "\n\n关键词：" + "；".join(kws) + "\n", encoding="utf-8")
        print(f"[corpus] {p.stem}: 汉字 {papers[name]['zh_chars']} 数字 {papers[name]['num_count']} 关键词 {papers[name]['kw_count']}")
    data = build(papers)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    Path(a.out_md).write_text(to_md(data), encoding="utf-8")
    if skipped:
        print(f"[corpus] 跳过（未识别到摘要/关键词）：{', '.join(skipped)}")
    print(f"[corpus] n={data['n']} → {out_json.name}, {Path(a.out_md).name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
