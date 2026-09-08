"""smoke_test.py — 仓库自检：把 examples/demo-drug-decay 复制到临时目录，走完整管线并做正反两组断言。

    python scripts/smoke_test.py

正向：intake → select → （拷入示例摘要）→ lint/verify --strict 均 0 FAIL → ABSTRACT_REPORT.md 为 PASS；
反向：编造数字 / 丢限定词 / 正文内部路径 / 数字堆叠 的坏摘要必须被 lint 或 verify 拦住；
只读：paper/、reports/ 在整个过程中哈希不变。
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SK = ROOT / ".agents" / "skills"
DEMO = ROOT / "examples" / "demo-drug-decay"
RUN = SK / "abstract-kickoff" / "scripts" / "run_abstract.py"
LINT = SK / "abstract-lint" / "scripts" / "lint_abstract.py"
VERIFY = SK / "abstract-verify" / "scripts" / "verify_abstract.py"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def sh(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, *map(str, args)], capture_output=True, text=True, encoding="utf-8", errors="replace")


def tree_hash(root: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(root.rglob("*")):
        if p.is_file():
            h.update(str(p.relative_to(root)).encode("utf-8"))
            h.update(p.read_bytes())
    return h.hexdigest()


def check(cond: bool, msg: str, fails: list[str]) -> None:
    print(("  ok   " if cond else "  FAIL ") + msg)
    if not cond:
        fails.append(msg)


def main() -> int:
    fails: list[str] = []
    with tempfile.TemporaryDirectory() as td:
        proj = Path(td) / "demo"
        shutil.copytree(DEMO, proj, ignore=shutil.ignore_patterns("abstract"))
        before = tree_hash(proj / "paper") + tree_hash(proj / "reports")
        ab = proj / "abstract"

        print("[1] 首跑：intake + select + 改前体检")
        r = sh(RUN, proj)
        check(r.returncode == 0, f"run_abstract 首跑 rc=0（实际 {r.returncode}）", fails)
        if r.returncode:
            print(r.stdout[-1500:], r.stderr[-1500:])
        for f in ("ABSTRACT_FACTS.json", "ABSTRACT_CANDIDATES.json", "ABSTRACT_PLAN.md", "ABSTRACT_LINT_BEFORE.md"):
            check((ab / f).exists(), f"生成 {f}", fails)
        check(not (ab / "sections" / "00_abstract.md").exists(), "首跑不自动生成摘要正文", fails)
        facts = json.loads((ab / "ABSTRACT_FACTS.json").read_text(encoding="utf-8"))
        check([p["problem"] for p in facts["problems"]] == [1, 2, 3], "识别出问题 1/2/3", fails)
        check(len(facts["number_pool"]) > 100, f"数字池 {len(facts['number_pool'])} > 100", fails)
        check(any(h for p in facts["problems"] for h in p["hedges"]), "抓到限定句", fails)
        check(all("/home/" not in s and ":\\" not in s for s in (ab / "ABSTRACT_PLAN.md").read_text(encoding="utf-8").split("\n")),
              "PLAN 无绝对路径", fails)
        lint_before = json.loads((ab / "abstract_lint_before.json").read_text(encoding="utf-8"))
        check(lint_before["fail"] >= 1, f"示例旧摘要（数字过密）改前体检有 FAIL（{lint_before['fail']}）", fails)

        print("[2] 写入示例新摘要后复跑 --skip-intake --strict")
        (ab / "sections").mkdir(exist_ok=True)
        good = (DEMO / "abstract" / "sections" / "00_abstract.md").read_text(encoding="utf-8")
        (ab / "sections" / "00_abstract.md").write_text(good, encoding="utf-8")
        r = sh(RUN, proj, "--skip-intake", "--strict")
        check(r.returncode == 0, f"strict 复跑 rc=0（实际 {r.returncode}）", fails)
        if r.returncode:
            print(r.stdout[-1500:], r.stderr[-1500:])
        rep = (ab / "ABSTRACT_REPORT.md").read_text(encoding="utf-8") if (ab / "ABSTRACT_REPORT.md").exists() else ""
        check("**结论：PASS**" in rep, "ABSTRACT_REPORT 结论 PASS", fails)
        check("| 汉字数 |" in rep and "## 2 数字取舍" in rep, "报告含改前/改后指标与数字取舍", fails)
        lint_after = json.loads((ab / "abstract_lint.json").read_text(encoding="utf-8"))
        check(lint_after["fail"] == 0, "新摘要 lint 0 FAIL", fails)
        diff = (ab / "ABSTRACT_FACT_DIFF.md").read_text(encoding="utf-8")
        check(diff.startswith("# ABSTRACT_FACT_DIFF") and "FAIL 0" in diff, "新摘要 verify 0 FAIL", fails)

        print("[3] 反例：坏摘要必须被拦")
        bad_dir = Path(td) / "bad"
        bad_dir.mkdir()
        cases = {
            "fabricated": good.replace("达标概率为 100%", "达标概率为 98.7%"),
            "hedge_lost": good.replace("消除半衰期约 4.1 h", "消除半衰期精确为 4.12 h").replace("（合成演示数据）", ""),
            "internal_path": good.replace("并说明数据审计对结论的影响。", "并说明数据审计对结论的影响（详见 reports/RESULTS_REPORT.md）。"),
            "number_pile": good.replace("得到 33 个有效观测。", "得到 33 个有效观测，参数为 14.96、1.154、0.1682、4.12、1.95、9.20、0.989、0.23、0.40、"
                                        "0.2045、0.157、0.148、6.33、18.79、0.54、2.29、1.72、4.28、7.82、0.56、13.7。"),
        }
        for name, text in cases.items():
            p = bad_dir / f"{name}.md"
            p.write_text(text, encoding="utf-8")
            rl = sh(LINT, p, "--facts", ab / "ABSTRACT_FACTS.json", "--out", bad_dir / f"{name}_lint.md", "--strict")
            rv = sh(VERIFY, proj, "--abstract", p, "--out", bad_dir / f"{name}_diff.md", "--strict")
            out = (bad_dir / f"{name}_diff.md").read_text(encoding="utf-8") + (bad_dir / f"{name}_lint.md").read_text(encoding="utf-8")
            if name == "fabricated":
                check(rv.returncode == 1 and "98.7" in out, "编造的 98.7% → verify FAIL", fails)
            elif name == "hedge_lost":
                check("V02" in out and ("合成" in out or "4.12" in out), "去掉“合成演示数据”/精确化 → V02 告警", fails)
            elif name == "internal_path":
                check(rl.returncode == 1 and "A09" in out, "reports/ 路径 → lint A09 FAIL", fails)
            else:
                check(rl.returncode == 1 and "A04" in out, "一句 22 个数字（超语料最大值）→ lint A04 FAIL", fails)

        print("[4] 只读检查")
        check(tree_hash(proj / "paper") + tree_hash(proj / "reports") == before, "paper/ 与 reports/ 未被改动", fails)

    print(f"\nsmoke: {'PASS' if not fails else f'FAIL ({len(fails)})'}")
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(main())
