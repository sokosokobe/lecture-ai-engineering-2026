# 第2回 宿題（発展）: 用語集の Q&A で LoRA 学習

| ファイル | 内容 |
| --- | --- |
| `glossary_lora_tuning.ipynb` | 学習・評価用のノートブック（`notebooks/lora_format_tuning.ipynb` をもとに改変） |
| `glossary_sft.jsonl` | 学習データ A：`scripts/make_sft_dataset.py` の出力そのまま（116 件） |
| `glossary_sft_plus.jsonl` | 学習データ B：A ＋ 用語集にない語の負例 30 件（146 件） |
| `make_plus_dataset.py` | データ B を作るスクリプト |
| `glossary_eval.json` | 評価セット 34 問（exact 12 / paraphrase 12 / unknown 10） |
| `glossary.json` | `data/glossary.json` のコピー（Colab にアップロードする用） |
| `out/<データ名>/` | 実行結果（`result.json`、`eval_*.json`、出力付きのノートブック `executed.ipynb`） |

## データの作り直し（リポジトリのルートで）

```bash
uv run python scripts/make_sft_dataset.py > lectures/02/homework/glossary_sft.jsonl
uv run python lectures/02/homework/make_plus_dataset.py > lectures/02/homework/glossary_sft_plus.jsonl
```

## Colab で実行

1. `glossary_lora_tuning.ipynb` を Colab で開き、T4 GPU を選ぶ
2. `glossary_sft.jsonl`・`glossary_sft_plus.jsonl`・`glossary_eval.json`・`glossary.json` を `/content` にアップロードする
3. 上から実行する。データ B を試すときは、セッションを再起動し、`CONFIG["train_file"]` を `glossary_sft_plus.jsonl` にしてから上から実行する

## ローカルで実行（CUDA の GPU）

演習と同じ版を、プロジェクト本体とは別の venv に入れる（`.venv/` は git の対象外）。

```bash
cd lectures/02/homework
uv venv .venv --python 3.12
uv pip install -p .venv/bin/python "torch==2.11.0" --index-url https://download.pytorch.org/whl/cu130
uv pip install -p .venv/bin/python "transformers==5.18.0" "peft==0.21.1" "trl==1.14.2" "accelerate==1.15.0" "datasets==5.1.0" pandas nbconvert ipykernel

for f in glossary_sft glossary_sft_plus; do
  GLOSSARY_TRAIN=$f.jsonl .venv/bin/python -m jupyter nbconvert --to notebook --execute \
    --ExecutePreprocessor.timeout=-1 --output-dir out/$f --output executed.ipynb glossary_lora_tuning.ipynb
done
```

VS Code で開いて 1 セルずつ実行する場合は、カーネルに `lectures/02/homework/.venv/bin/python` を選ぶ。
