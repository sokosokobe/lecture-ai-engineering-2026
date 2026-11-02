"""第2回 宿題（発展）: 学習データ B を作る。

scripts/make_sft_dataset.py と同じ Q&A（データ A）に、「用語集にない語」を聞かれたら
「用語集に載っていません」と答える負例を足す。評価セットの unknown の語とは重ねない。

使い方（リポジトリのルートで）:
    uv run python lectures/02/homework/make_plus_dataset.py > lectures/02/homework/glossary_sft_plus.jsonl
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from make_sft_dataset import GLOSSARY, TEMPLATES  # noqa: E402

EVAL = Path(__file__).resolve().parent / "glossary_eval.json"

# 用語集にない語（実在する語と架空の語）。「プロンプト」「トークン」など用語集の語を含むものも混ぜる
NEGATIVE_TERMS = [
    "強化学習", "畳み込みニューラルネットワーク", "勾配消失", "バッチ正規化", "アテンション",
    "ドロップアウト", "Docker", "CI/CD", "ゼロショット学習", "マルチモーダル",
    "プロンプトインジェクション", "データ拡張", "交差検証", "モデルブレンド指数", "トークン予算係数",
]
NEGATIVE_ANSWER = "「{term}」は講座の用語集に載っていません。推測で説明せず、講座の資料や担当者に確認してください。"


def record(question: str, answer: str) -> dict:
    return {"messages": [{"role": "user", "content": question}, {"role": "assistant", "content": answer}]}


def main() -> None:
    terms = json.loads(GLOSSARY.read_text(encoding="utf-8"))["terms"]
    names = {n for t in terms for n in [t["term"], *t["aliases"]]}
    eval_questions = " ".join(item["q"] for item in json.loads(EVAL.read_text(encoding="utf-8"))["items"])
    for neg in NEGATIVE_TERMS:
        assert neg not in names, f"{neg} は用語集にあります"
        assert neg not in eval_questions, f"{neg} は評価セットに出てきます"

    rows = [record(tpl.format(term=t["term"]), t["definition"]) for t in terms for tpl in TEMPLATES]
    rows += [record(tpl.format(term=neg), NEGATIVE_ANSWER.format(term=neg)) for neg in NEGATIVE_TERMS for tpl in TEMPLATES]
    for r in rows:
        sys.stdout.write(json.dumps(r, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
