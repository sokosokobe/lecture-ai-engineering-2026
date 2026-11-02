"""保存済みの出力（out/<データ名>/eval_*.json）を、glossary_eval.json の現在の基準で採点し直す。

生成はやり直さない。正解の語句や unknown_markers を直したときに使う。判定はノートブックの judge と同じ。

使い方（このディレクトリで）:
    python3 rescore.py
"""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVAL = json.loads((HERE / "glossary_eval.json").read_text(encoding="utf-8"))
ITEMS = {it["q"]: it for it in EVAL["items"]}
KINDS = ["exact", "paraphrase", "unknown"]


def said_unknown(raw):
    return any(m in raw for m in EVAL["unknown_markers"])


def judge(item, raw):
    if item["kind"] == "unknown":
        return said_unknown(raw)
    return not said_unknown(raw) and all(any(w in raw for w in group) for group in item["must_include"])


def rescore(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data["rows"]
    for r in rows:
        r["ok"] = judge(ITEMS[r["q"]], r["raw"])
    s = data["summary"]
    s["overall"] = sum(r["ok"] for r in rows) / len(rows)
    for k in KINDS:
        s[k] = sum(r["ok"] for r in rows if r["kind"] == k) / sum(r["kind"] == k for r in rows)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return s, rows


for result_path in sorted(HERE.glob("out/*/result.json")):
    result = json.loads(result_path.read_text(encoding="utf-8"))
    rows = {}
    for label in ["before", "after", "retrieval"]:
        result[label], rows[label] = rescore(result_path.parent / f"eval_{label}.json")
    result["regressed"] = [b["q"] for b, a in zip(rows["before"], rows["after"]) if b["ok"] and not a["ok"]]
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"== {result_path.parent.name}")
    for label in ["before", "after", "retrieval"]:
        print(f"  {label:9s}", " ".join(f"{k}={result[label][k]:.2f}" for k in ["overall", *KINDS]))
    print("  退行:", result["regressed"])
