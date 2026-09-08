"""abstract_common.py — mm-abstract-workbench 各脚本共用的纯标准库工具。

包含：控制台编码设置、汉字计数、数字/句子/问题编号识别、摘要指标计算、Markdown 摘要切分、阈值加载。
其它脚本通过 `sys.path.insert(0, <本目录>)` 后 `from abstract_common import ...` 使用。
"""
from __future__ import annotations

import json
import re
import statistics as st
import sys
from pathlib import Path

SKILLS = Path(__file__).resolve().parents[2]
REF = SKILLS / "_references"

# ---- 与语料统计保持一致的模式（改一处即全局生效） ----
PROBLEM_MARK = re.compile(r"问题\s*([一二三四五六七八九十0-9]+)|第\s*([一二三四五六七八九十0-9]+)\s*(?:个问题|问|题)")
CN_NUM = {c: i + 1 for i, c in enumerate("一二三四五六七八九")}
CN_NUM["十"] = 10
TAIL_MARK = ("最后", "综上", "总体", "总的来说", "总之", "本文的创新", "创新点", "优点", "不足", "推广", "展望", "局限")
AI_PHRASES = ["赋能", "需要指出的是", "全方位", "有力支撑", "不难发现", "多维度", "值得一提的是", "众所周知",
              "不言而喻", "毫无疑问", "极大地", "极具", "深远影响", "强有力", "深入浅出", "一站式", "闭环"]
NUM = re.compile(r"(?<![A-Za-z0-9_.])[-−]?\d+(?:[.,]\d+)*(?:\s*[×x]\s*10\^?-?\d+|e-?\d+)?%?")
YEAR = re.compile(r"[12]\d{3}")

# 限定词：正文里带这些词的结论，进摘要时不能被"增强"成确定结论
HEDGE_WORDS = ["假设", "探索性", "待复核", "低置信", "中置信", "尚未", "未覆盖", "仅作", "仅为", "不能解读", "不构成",
               "可能", "近似", "假想", "合成数据", "演示数据", "旁证", "不确定", "推断", "无标签", "无真值", "初步", "不能据此"]
# 强限定词：丢了会把“推断/假设”变成“事实”，核验时按 FAIL 处理
STRONG_HEDGE = ["假设", "探索性", "待复核", "低置信", "无标签", "无真值", "合成数据", "演示数据", "不能据此", "尚未", "初步", "推断", "旁证", "假想"]
UNIT_AFTER = re.compile(r"^\s*(%|％|‰|°C|℃|°|kHz|Hz|MHz|dB|rpm|mg|kg|km|cm|mm|ms|min|h\b|s\b|m\b|L\b|mL|元|万|亿|倍|个百分点|百分点"
                        r"|维|折|段|条|次|轮|层|组|类|簇|种|台|人|例|点|周|天|年|月|日|小时|分钟|秒|页|篇|张|行|列|档|级|阶|hp)")
# 结论/结果标志：句子里出现这些词，说明它在陈述"结果"而不是"过程"
RESULT_MARK = ["最终", "综上", "结果表明", "结果显示", "表明", "说明", "可见", "得到", "达到", "为最优", "最优", "最佳",
               "推荐", "判决", "结论", "验证了", "证实", "取得", "优于", "显著", "一致率", "准确率", "宏 F1", "F1", "AUC",
               "误差", "R²", "RMSE", "MAE", "召回", "精度", "相关系数", "概率", "P 值", "p 值"]
METRIC_MARK = ["准确率", "精度", "宏 F1", "F1", "AUC", "召回", "RMSE", "MAE", "MAPE", "R²", "R^2", "R2", "误差", "一致率",
               "相关系数", "置信", "概率", "得分", "损失", "MMD", "距离", "p 值", "P 值", "轮廓系数", "KS", "残差", "偏差",
               "稳定率", "比例", "占比", "命中", "覆盖率", "灵敏度", "特异度", "AIC", "BIC", "均方", "拟合", "半衰期", "上限", "下限"]
DATA_MARK = ["个文件", "文件", "条", "段", "维", "样本", "记录", "kHz", "Hz", "采样", "时长", "行", "列", "变量", "受试者",
             "个点", "有效点", "个体", "缺失", "离群", "异常值", "类", "簇", "组", "折"]
PARAM_MARK = ["=", "阈值", "步长", "窗长", "窗", "深度", "种子", "折", "参数", "设为", "取", "网格", "学习率", "迭代", "层",
              "epoch", "batch", "k=", "n_estimators", "max_depth"]
COMPARE_MARK = ["从", "到", "由", "降", "升", "vs", "优于", "高于", "低于", "提升", "下降", "对比", "相比", "虚高", "变为"]
INTERNAL_NAMES = ["reports/", "figures/", "results/", "polish/", "frame/", "layout/", "abstract/", "run_all", "AGENTS.md",
                  "plan.md", "todo.md", "HANDOFF", "RESULTS_REPORT", ".py", ".csv", ".json", ".mat", ".docx"]


def setup_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def zh(s: str) -> int:
    return sum(1 for c in s if "\u4e00" <= c <= "\u9fff")


def read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8").replace("\r\n", "\n")


def write_text(p: Path, s: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(s, encoding="utf-8")


def load_json(p: Path) -> dict:
    return json.loads(read_text(p))


def dump_json(p: Path, obj) -> None:
    write_text(p, json.dumps(obj, ensure_ascii=False, indent=1) + "\n")


def problem_index(m: re.Match) -> int:
    tok = m.group(1) or m.group(2) or ""
    if tok.isdigit():
        return int(tok)
    if tok in CN_NUM:
        return CN_NUM[tok]
    if len(tok) == 2 and tok[0] == "十" and tok[1] in CN_NUM:
        return 10 + CN_NUM[tok[1]]
    return 0


def problem_index_of_text(s: str) -> int:
    """标题/句子里第一个"问题 N"的 N；没有则 0。"""
    m = PROBLEM_MARK.search(s)
    return problem_index(m) if m else 0


def sig_digits(tok: str) -> int:
    t = tok.strip("%").replace(",", "").lstrip("-−")
    if "e" in t or "×" in t or "x" in t:
        t = re.split(r"[e×x]", t)[0]
    digits = t.replace(".", "").lstrip("0")
    return len(digits.rstrip("0")) if "." in t else len(digits)


def norm_num(tok: str) -> str:
    """数字归一化：去千分位逗号、统一负号、去掉尾随零，'%' 保留。"""
    t = tok.strip().replace(",", "").replace("−", "-")
    pct = t.endswith("%")
    t = t.rstrip("%")
    if re.fullmatch(r"-?\d+\.\d+", t):
        t = t.rstrip("0").rstrip(".")
    return t + ("%" if pct else "")


def numbers_in(s: str, drop_years: bool = True) -> list[str]:
    out = [m.group(0) for m in NUM.finditer(s)]
    if drop_years:
        out = [t for t in out if not YEAR.fullmatch(t)]
    return out


def sentences(body: str) -> list[str]:
    return [s for s in re.split(r"[。！？；!?;\n]|(?<=[\u4e00-\u9fff])\.\s", body) if zh(s) >= 4]


def strip_markdown(s: str) -> str:
    """去掉行内 Markdown 标记（加粗/代码/链接），保留文字与公式内容。"""
    s = re.sub(r"^\s*(?:[-*+]|\d+[.)、])\s+", "", s)
    s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)
    s = re.sub(r"`([^`]*)`", r"\1", s)
    s = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", s)
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)
    return s


def abstract_metrics(body: str, kws: list[str]) -> dict:
    """摘要正文（不含"摘要"标题与关键词行）→ 指标字典。语料统计与 lint 共用。"""
    n = zh(body)
    k = max(n, 1) / 1000.0
    nums = numbers_in(body)
    sents = sentences(body)
    slen = [zh(s) for s in sents]
    per_sent = [len(numbers_in(s)) for s in sents]
    mlist = list(PROBLEM_MARK.finditer(body))
    marks = [m.start() for m in mlist]
    problems = sorted({problem_index(m) for m in mlist} - {0})
    lead = body[: marks[0]] if marks else body
    tail = body[-220:]
    ai = {p: body.count(p) for p in AI_PHRASES}
    return {
        "zh_chars": n,
        "num_count": len(nums),
        "num_per_k": round(len(nums) / k, 1),
        "dec_count": sum(1 for t in nums if "." in t),
        "sig4_count": sum(1 for t in nums if sig_digits(t) >= 4),
        "max_nums_per_sentence": max(per_sent) if per_sent else 0,
        "sent_count": len(sents),
        "sent_median": st.median(slen) if slen else 0,
        "sent_p90": sorted(slen)[int(len(slen) * 0.9)] if slen else 0,
        "sent_max": max(slen) if slen else 0,
        "problem_mentions": len(marks),
        "problem_count": len(problems),
        "problems": problems,
        "lead_zh": zh(lead),
        "has_tail": any(t in tail for t in TAIL_MARK),
        "kw_count": len(kws),
        "en_abbr_count": len(re.findall(r"\b[A-Z][A-Za-z]*[A-Z][A-Za-z0-9\-]*\b|\b[A-Z]{2,}\b", body)),
        "en_abbr_per_k": round(len(re.findall(r"\b[A-Z]{2,}\b", body)) / k, 2),
        "paren_per_k": round((body.count("（") + len(re.findall(r"\([^)]*[\u4e00-\u9fff][^)]*\)", body))) / k, 2),
        "quote_per_k": round(body.count("“") / k, 2),
        "slash_list": len(re.findall(r"\d\s*/\s*\d[^/]*?/\s*\d", body)),
        "ai_phrase_count": sum(ai.values()),
        "ai_hits": {p: c for p, c in ai.items() if c},
    }


def split_abstract_md(text: str) -> dict:
    """把 Markdown 摘要文件切成：title、paragraphs（正文段）、keywords（列表）、body（正文纯文本）。

    约定：可选的一行 `# 摘要` 标题；关键词行以 `关键词` / `关键字` 开头（允许加粗），用 `；` `;` `，` `、` 分隔。
    """
    lines = text.split("\n")
    title = ""
    paras: list[str] = []
    kws: list[str] = []
    has_kw = False
    buf: list[str] = []

    def flush() -> None:
        if buf:
            paras.append(" ".join(x.strip() for x in buf).strip())
            buf.clear()

    for line in lines:
        s = line.strip()
        if not s:
            flush()
            continue
        if s.startswith("#"):
            flush()
            if not title:
                title = s.lstrip("#").strip()
            continue
        plain = strip_markdown(s)
        m = re.match(r"^\s*关\s*键\s*[词字]\s*[:：]?\s*(.*)$", plain)
        if m:
            flush()
            has_kw = True
            kws = [x.strip() for x in re.split(r"[；;，,、]", m.group(1)) if x.strip()]
            continue
        buf.append(plain)
    flush()
    return {"title": title, "paragraphs": paras, "keywords": kws, "has_kw_line": has_kw, "body": "\n".join(paras)}


def load_thresholds(path: Path | None = None) -> dict:
    p = path or (REF / "abstract_corpus_stats.json")
    if not p.exists():
        return {}
    return load_json(p).get("summary", {})


def heading_role(title: str, filename: str = "") -> str:
    """一级标题 → 语义角色。通用规则，不含项目私有词。"""
    t = title
    if PROBLEM_MARK.search(t) and not re.search(r"重述|分析与?思路|问题分析|背景", t):
        return "problem"
    if re.search(r"摘要", t):
        return "abstract"
    if re.search(r"稳健|灵敏|敏感|检验|误差分析", t):
        return "robustness"
    if re.search(r"评价|推广|优缺点|优点|改进|展望|总结", t):
        return "evaluation"
    if re.search(r"问题分析|总体思路|分析思路|研究思路|技术路线", t):
        return "analysis"
    if re.search(r"重述|背景", t):
        return "restatement"
    if re.search(r"假设|符号", t):
        return "assumptions"
    if re.search(r"参考文献|References", t, re.I):
        return "references"
    if re.search(r"附录|伪代码|声明|全表|完整表", t) or re.match(r"^[A-Za-z]_", filename):
        return "appendix"
    return "other"
