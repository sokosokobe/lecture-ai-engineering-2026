"""第1回 宿題（発展）: 応答時間とトークン数を、モデル × 質問で計測して比較する。

使い方:
    uv run --env-file .env python -m scripts.benchmark
    uv run --env-file .env python -m scripts.benchmark --models gemini-3.5-flash-lite --repeat 5
    uv run --env-file .env python -m scripts.benchmark --stream      # 最初のトークンまでの時間も測る
    uv run --env-file .env python -m scripts.benchmark --interval 0  # 間隔なしで連続で呼び、429 を観察する

1回の呼び出しごとの結果を CSV に保存し、最後にモデル × 質問ごとの集計を Markdown の表で表示する。
失敗した呼び出し（429 など）も1行として記録するので、レート制限にかかった回数も分かる。
無料枠には 1分あたり・1日あたりの上限があるので、--repeat や --models を増やしすぎないこと。
"""

import argparse
import csv
import re
import statistics
import time
from datetime import datetime
from pathlib import Path

from google import genai
from google.genai import errors

from app.config import api_error_message, get_api_key

DEFAULT_MODELS = ["gemini-3.5-flash-lite", "gemini-3.5-flash", "gemini-3.1-flash-lite"]

# 出力の長さが変わるように選んだ質問
QUESTIONS = {
    "short": "LoRAとは何ですか？一文で答えてください。",
    "course": "AIE2026の講座の宿題にある「3レベル」とは何ですか？",
    "long": "LoRAの仕組みと利点・欠点を800字程度で説明してください。",
}

DEFAULT_OUT = Path(__file__).resolve().parent.parent / "lectures" / "01" / "benchmark.csv"

FIELDS = [
    "started_at", "model", "question", "trial", "ok", "status", "latency_s", "ttft_s",
    "prompt_tokens", "output_tokens", "thoughts_tokens", "total_tokens", "output_tok_per_s",
    "retry_delay_s",
]


def retry_delay(e: errors.APIError) -> float | None:
    """429 の応答に含まれる RetryInfo（例: "31s"）から、待つべき秒数を取り出す。"""
    details = (e.details or {}).get("error", {}).get("details", []) if isinstance(e.details, dict) else []
    for d in details:
        if d.get("@type", "").endswith("RetryInfo"):
            m = re.match(r"([\d.]+)s", d.get("retryDelay", ""))
            if m:
                return float(m.group(1))
    return None


def call(client: genai.Client, model: str, question: str, stream: bool) -> dict:
    """1回呼び出し、応答時間とトークン数を返す。stream のときは最初のチャンクまでの時間も測る。"""
    ttft = None
    start = time.perf_counter()
    if stream:
        usage = None
        for chunk in client.models.generate_content_stream(model=model, contents=question):
            if ttft is None:
                ttft = time.perf_counter() - start
            # usage_metadata は最後のチャンクに最終値が入る
            usage = chunk.usage_metadata or usage
    else:
        usage = client.models.generate_content(model=model, contents=question).usage_metadata
    latency = time.perf_counter() - start

    output = (usage.candidates_token_count or 0) if usage else 0
    return {
        "latency_s": round(latency, 3),
        "ttft_s": round(ttft, 3) if ttft is not None else "",
        "prompt_tokens": usage.prompt_token_count if usage else "",
        "output_tokens": output,
        "thoughts_tokens": (usage.thoughts_token_count or 0) if usage else "",
        "total_tokens": usage.total_token_count if usage else "",
        "output_tok_per_s": round(output / latency, 1) if latency > 0 else "",
    }


def run(models: list[str], repeat: int, interval: float, stream: bool, out: Path) -> list[dict]:
    client = genai.Client(api_key=get_api_key())
    rows: list[dict] = []
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for model in models:
            for qid, question in QUESTIONS.items():
                for trial in range(1, repeat + 1):
                    row = {"started_at": time.time(), "model": model, "question": qid, "trial": trial}
                    try:
                        row |= {"ok": True, "status": 200, **call(client, model, question, stream)}
                        wait = interval
                        print(f"{model:<24} {qid:<7} #{trial}  {row['latency_s']:>6.2f}s  "
                              f"in={row['prompt_tokens']} out={row['output_tokens']} "
                              f"think={row['thoughts_tokens']}")
                    except errors.APIError as e:
                        delay = retry_delay(e)
                        row |= {"ok": False, "status": e.code, "retry_delay_s": delay or ""}
                        # 429 は指示された秒数（なければ60秒）待つ。それ以外は通常の間隔で次へ
                        wait = (delay or 60) if e.code == 429 else interval
                        print(f"{model:<24} {qid:<7} #{trial}  {api_error_message(e.code, e.message)}")
                    rows.append(row)
                    writer.writerow(row)
                    f.flush()
                    time.sleep(wait)
    return rows


def peak_per_minute(rows: list[dict], key: str | None) -> int:
    """任意の60秒の窓に入ったリクエスト数（key=None）またはトークン数の最大値。"""
    times = sorted((r["started_at"], (r.get(key) or 0) if key else 1) for r in rows)
    best = 0
    for i, (t0, _) in enumerate(times):
        best = max(best, sum(v for t, v in times[i:] if t - t0 < 60))
    return best


def summarize(rows: list[dict], stream: bool) -> str:
    def fmt(values: list[float]) -> str:
        if not values:
            return "-"
        return f"{statistics.mean(values):.2f} ({min(values):.2f}–{max(values):.2f})"

    header = ["モデル", "質問", "成功/試行", "応答時間 s 平均(最小–最大)", "入力", "出力", "推論", "出力 tok/s"]
    if stream:
        header.insert(4, "最初のトークン s")
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    for model in dict.fromkeys(r["model"] for r in rows):
        for qid in QUESTIONS:
            group = [r for r in rows if r["model"] == model and r["question"] == qid]
            ok = [r for r in group if r["ok"]]
            mean = lambda k: f"{statistics.mean(r[k] for r in ok):.0f}" if ok else "-"  # noqa: E731
            cells = [model, qid, f"{len(ok)}/{len(group)}", fmt([r["latency_s"] for r in ok]),
                     mean("prompt_tokens"), mean("output_tokens"), mean("thoughts_tokens"),
                     fmt([r["output_tok_per_s"] for r in ok])]
            if stream:
                cells.insert(4, fmt([r["ttft_s"] for r in ok]))
            lines.append("| " + " | ".join(cells) + " |")

    errors_by_status: dict[int, int] = {}
    for r in rows:
        if not r["ok"]:
            errors_by_status[r["status"]] = errors_by_status.get(r["status"], 0) + 1
    wall = rows[-1]["started_at"] - rows[0]["started_at"] if rows else 0
    lines += [
        "",
        f"- 総リクエスト数: {len(rows)}（エラー: {errors_by_status or 'なし'}）、所要時間: {wall:.0f} 秒",
        f"- 60秒間の最大リクエスト数: {peak_per_minute(rows, None)}",
        f"- 60秒間の最大トークン数（合計）: {peak_per_minute(rows, 'total_tokens')}",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="応答時間とトークン数をモデル × 質問で計測する")
    parser.add_argument("--models", nargs="+", default=DEFAULT_MODELS)
    parser.add_argument("--repeat", type=int, default=3, help="同じ質問の繰り返し回数")
    parser.add_argument("--interval", type=float, default=5.0, help="呼び出しの間隔（秒）")
    parser.add_argument("--stream", action="store_true", help="ストリーミングで最初のトークンまでの時間も測る")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="結果の CSV")
    args = parser.parse_args()

    total = len(args.models) * len(QUESTIONS) * args.repeat
    print(f"[計測開始] {datetime.now():%Y-%m-%d %H:%M:%S}  {total} 回呼び出します（間隔 {args.interval} 秒）\n")
    rows = run(args.models, args.repeat, args.interval, args.stream, args.out)
    print(f"\n[CSV] {args.out}\n")
    print(summarize(rows, args.stream))


if __name__ == "__main__":
    main()
