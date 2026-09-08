"""run_abstract.py — 摘要工作台一键管线：intake → select → （人/Agent 写摘要）→ lint → verify → report。

用法：
    python .agents/skills/abstract-kickoff/scripts/run_abstract.py <proj> [--source auto|polish|frame|paper]
        [--target-zh N] [--num-budget N] [--per-problem N] [--strict] [--skip-intake]

- 第一次跑（<proj>/abstract/sections/00_abstract.md 还不存在）：只做 intake + select，并给当前摘要（若有）做一份"改前体检"
  ABSTRACT_LINT_BEFORE.md，然后停下来让人/Agent 按 abstract-write/SKILL.md 写新摘要；
- 摘要写好后再跑：lint + verify + ABSTRACT_REPORT.md；--strict 时任一 FAIL 返回 1。
- --skip-intake：改了摘要重跑时不重新扫正文（事实账本已存在）。
只写 <proj>/abstract/，其它目录只读。
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILLS = HERE.parents[1]
sys.path.insert(0, str(SKILLS / "abstract-intake" / "scripts"))
from abstract_common import abstract_metrics, load_json, numbers_in, read_text, setup_stdout, split_abstract_md, write_text  # noqa: E402

INTAKE = SKILLS / "abstract-intake" / "scripts" / "intake_abstract.py"
SELECT = SKILLS / "abstract-select" / "scripts" / "select_facts.py"
LINT = SKILLS / "abstract-lint" / "scripts" / "lint_abstract.py"
VERIFY = SKILLS / "abstract-verify" / "scripts" / "verify_abstract.py"


def run(script: Path, *args: str) -> int:
    cmd = [sys.executable, str(script), *args]
    print("$", " ".join(Path(c).name if c.endswith(".py") else c for c in cmd), flush=True)
    return subprocess.run(cmd, check=False).returncode


def metric_rows(before: dict | None, after: dict) -> list[str]:
    keys = (("zh_chars", "汉字数"), ("num_count", "数字个数"), ("num_per_k", "数字/千字"), ("dec_count", "小数个数"),
            ("sig4_count", "≥4 位有效数字"), ("max_nums_per_sentence", "单句最多数字"), ("sent_count", "句数"), ("sent_p90", "句长 P90"),
            ("problem_count", "提及问题数"), ("lead_zh", "开头段汉字"), ("kw_count", "关键词数"), ("en_abbr_count", "英文缩写数"),
            ("paren_per_k", "括号/千字"), ("has_tail", "有结尾段"))
    rows = ["| 指标 | 改前 | 改后 |", "| --- | ---: | ---: |"]
    for k, label in keys:
        b = "" if before is None else before.get(k, "")
        rows.append(f"| {label} | {b} | {after.get(k, '')} |")
    return rows


def report(proj: Path, strict: bool) -> int:
    ab = proj / "abstract"
    facts = load_json(ab / "ABSTRACT_FACTS.json")
    new_md = ab / "sections" / "00_abstract.md"
    new_parts = split_abstract_md(read_text(new_md))
    after = abstract_metrics(new_parts["body"], new_parts["keywords"])
    cur = facts.get("current_abstract")
    before = cur["metrics"] if cur else None
    lint = load_json(ab / "abstract_lint.json") if (ab / "abstract_lint.json").exists() else {"fail": 0, "warn": 0, "items": []}
    diff_md = read_text(ab / "ABSTRACT_FACT_DIFF.md") if (ab / "ABSTRACT_FACT_DIFF.md").exists() else ""
    vf = vw = 0
    for line in diff_md.split("\n"):
        if line.startswith("FAIL "):
            parts = line.replace("·", " ").split()
            vf, vw = int(parts[1]), int(parts[3])
            break
    old_nums = set()
    if cur:
        old_md = proj / cur["path"]
        if old_md.exists():
            old_nums = set(numbers_in(split_abstract_md(read_text(old_md))["body"]))
    new_nums = set(numbers_in(new_parts["body"]))
    kept = sorted(old_nums & new_nums, key=lambda s: (len(s), s))
    dropped = sorted(old_nums - new_nums, key=lambda s: (len(s), s))
    added = sorted(new_nums - old_nums, key=lambda s: (len(s), s))
    status = "PASS" if (lint["fail"] == 0 and vf == 0) else "FAIL"

    L = ["# ABSTRACT_REPORT — 摘要撰写报告", "",
         f"项目：{facts['project'].get('title', proj.name)}；正文来源：`{facts['project']['source_dir']}`；新摘要：`abstract/sections/00_abstract.md`", "",
         f"**结论：{status}** — lint FAIL {lint['fail']} / WARN {lint['warn']}；事实溯源 FAIL {vf} / WARN {vw}。", "",
         "## 1 改前 / 改后", ""]
    L += metric_rows(before, after)
    L += ["", f"关键词（改后）：{'；'.join(new_parts['keywords'])}", ""]
    if cur:
        L += ["## 2 数字取舍", "",
              f"改前摘要 {len(old_nums)} 个不同数字 → 改后 {len(new_nums)} 个；保留 {len(kept)}，删去 {len(dropped)}，新引入 {len(added)}（新引入的都已在 `ABSTRACT_FACT_DIFF.md` 溯源）。", "",
              f"- 保留：{'、'.join(kept) or '（无）'}", f"- 删去（回正文查看）：{'、'.join(dropped) or '（无）'}", f"- 新引入：{'、'.join(added) or '（无）'}", ""]
    L += ["## 3 待人工复核", ""]
    warn_items = [i for i in lint["items"] if i["level"] != "INFO"]
    if warn_items:
        L += [f"- lint [{i['rule']}] {i['msg']}" for i in warn_items]
    if vf or vw:
        L.append("- 事实溯源的 FAIL/WARN 见 `ABSTRACT_FACT_DIFF.md`")
    if not warn_items and not (vf or vw):
        L.append("- 无自动告警。仍请通读一遍：每问是否“方法 + 结果 + 验证”齐全、限定词是否到位、结尾是否讲清创新与局限。")
    L += ["", "## 4 产物", "",
          "| 文件 | 用途 |", "| --- | --- |",
          "| `ABSTRACT_FACTS.json` | 正文/报告事实账本（数字池、结论句、限定句） |",
          "| `ABSTRACT_CANDIDATES.json` / `ABSTRACT_PLAN.md` | 候选事实排序与每段预算 |",
          "| `sections/00_abstract.md` | 新摘要（Markdown，纯段落 + 关键词行） |",
          "| `ABSTRACT_REWRITE_LOG.md` | 取舍理由（人/Agent 手写） |",
          "| `ABSTRACT_LINT_BEFORE.md` / `ABSTRACT_LINT.md` | 改前 / 改后体检 |",
          "| `ABSTRACT_FACT_DIFF.md` | 每个数字、限定词、关键词的溯源 |", "",
          "## 5 下一步", "",
          "- 新摘要不自动写回 `paper/main.docx`：把 `sections/00_abstract.md` 的正文与关键词粘贴到 Word 摘要页（或交给 mm-layout-workbench）。",
          "- 若正文后续有改动（数字变化），重跑 `run_abstract.py <proj> --strict`，FACT_DIFF 会指出摘要里过期的数字。", ""]
    write_text(ab / "ABSTRACT_REPORT.md", "\n".join(L))
    print(f"[report] {status} → {ab / 'ABSTRACT_REPORT.md'}")
    return 1 if (strict and status == "FAIL") else 0


def main() -> int:
    setup_stdout()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("proj")
    ap.add_argument("--source", default="auto")
    ap.add_argument("--target-zh", type=int, default=0)
    ap.add_argument("--num-budget", type=int, default=0)
    ap.add_argument("--per-problem", type=int, default=4)
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--skip-intake", action="store_true")
    a = ap.parse_args()
    proj = Path(a.proj).resolve()
    ab = proj / "abstract"
    facts_p = ab / "ABSTRACT_FACTS.json"

    if not a.skip_intake or not facts_p.exists():
        if run(INTAKE, str(proj), "--source", a.source):
            return 2
        sel = [str(proj), "--per-problem", str(a.per_problem)]
        if a.target_zh:
            sel += ["--target-zh", str(a.target_zh)]
        if a.num_budget:
            sel += ["--num-budget", str(a.num_budget)]
        if run(SELECT, *sel):
            return 2
        cur = load_json(facts_p).get("current_abstract")
        if cur:
            run(LINT, str(proj / cur["path"]), "--facts", str(facts_p), "--out", str(ab / "ABSTRACT_LINT_BEFORE.md"),
                "--json", str(ab / "abstract_lint_before.json"))

    new_md = ab / "sections" / "00_abstract.md"
    if not new_md.exists():
        print(f"[run] 计划已生成：{ab / 'ABSTRACT_PLAN.md'}\n[run] 请按 abstract-write/SKILL.md 撰写 {new_md}，然后重跑本脚本（可加 --skip-intake --strict）。")
        return 0
    rc_l = run(LINT, str(proj), "--strict")
    rc_v = run(VERIFY, str(proj), "--strict")
    rc_r = report(proj, a.strict)
    return 1 if (a.strict and (rc_l or rc_v or rc_r)) else 0


if __name__ == "__main__":
    raise SystemExit(main())
