# 第3回 解答

## 演習

- 第1回（素のLLM）とエージェントの回答の違い：
  - `app.ask`（素のLLM）は「lecNN-start」を「ニューラルネットワーク（NN）の講義の開始位置を示すタグ」と推測し、もっともらしい説明を長々と続けた（ハルシネーション）。入力23トークン・出力368トークン
  - `app.agent` は `search_glossary` で用語集を引き、「各回の演習開始時点のコードに付けた Git タグ（例：`lec03-start`）」と正しく答え、最後に「第1回」と添えた。用語集という根拠があると、短く正確になる
- `--trace` で見えたツール呼び出し（ツール名と引数）：
  - 「LoRAとQLoRAの違いは？」→ `search_glossary({'query': 'LoRA'})` と `search_glossary({'query': 'QLoRA'})` を **1回の応答で並列に** 呼んだ（docstring の「query には用語を1つだけ」に従い、2語を分けて検索した）
  - 「lecNN-start タグ」→ `search_glossary({'query': 'lecNN-start タグ'})`
  - 「第2回の内容から確認問題を1問出して」→ `make_quiz({'lecture': 2})`
- 1つの質問での LLM 呼び出し回数（`requests`）：どの質問でも 2 回（①ツールを呼ぶと決める → ②ツールの結果を見て回答を書く）。並列呼び出しのおかげで、ツールが2つでも 2 回で済んだ
- 追加したツールと、docstring に書いた説明：
  - `make_quiz(lecture: int)`（[app/tools.py](../../app/tools.py)）：用語集からその回の用語を1つランダムに選び、`{"question": "「◯◯」の意味は？", "answer": 定義, "related": [...]}` を返す。回に用語がなければ、用語がある回の一覧を返す
  - docstring：「『第2回の確認問題を出して』『復習のクイズがほしい』のように、利用者が理解度を確かめる問題を求めたときに使う。問題は用語集の定義に基づくので、自分で問題を作らずにこのツールを使うこと。返した答えは、利用者が考えられるよう問題の後に分けて示す。」
  - `INSTRUCTIONS` にも「確認問題やクイズを求められたら make_quiz を使い、答えは問題の後に分けて示す」を足した。実行すると、モデルは答えを伏せて問題だけを出し「答えを確認したいときはお知らせください」と返した
  - テスト：`tests/test_tools.py` に、選ばれた用語がその回のもので答えが定義と一致すること、存在しない回で案内を返すことを追加

## 宿題

- 取り組んだレベル：発展（a）Google ADK で作り直して比較
- やったこと：
  - [homework/study_agent/agent.py](homework/study_agent/agent.py)：ADK（`google-adk==2.13.0`）の `Agent` で同じエージェントを作った。ツールの関数（`app/tools.py`）と `INSTRUCTIONS` は Pydantic AI 版のものをそのまま import し、**フレームワークだけを変えて**比べられるようにした
  - [homework/run_adk.py](homework/run_adk.py)：`app.agent --trace` と同じ形式でツール呼び出しを表示する CLI
  - [tests/test_adk_agent.py](../../tests/test_adk_agent.py)：ADK には `TestModel` がないので、`BaseLlm` を継承した偽モデルを作り、APIキーなしでツールの登録・呼び出し・戻り値の受け渡しを確かめた
  - 依存は `pyproject.toml` の依存グループ `adk` に分けた（`uv sync --group adk` で入る。入れていなければ ADK のテストはスキップ）
  - 実行方法：
    ```bash
    uv sync --group adk
    uv run --env-file .env python lectures/03/homework/run_adk.py --trace "LoRAとQLoRAの違いは？"
    uv run --env-file .env adk web lectures/03/homework   # ブラウザで http://localhost:8000
    ```
- 結果：
  - 同じ3つの質問で、ツールの選び方・引数・`requests`（2回）は Pydantic AI 版と同じ。回答の内容もほぼ同じ

    | 質問 | ツール呼び出し（両方とも同じ） | 入力トークン Pydantic AI / ADK |
    |---|---|---|
    | lecNN-start タグとは？ | `search_glossary('lecNN-start タグ')` | 1101 / 1287 |
    | LoRAとQLoRAの違いは？ | `search_glossary('LoRA')`, `search_glossary('QLoRA')` | 1514 / 1698 |
    | 第2回の確認問題を1問 | `make_quiz(2)` | 1053 / 1279 |

  - ADK のほうが毎回 190〜230 トークン多い。偽モデルで実際のリクエストを見ると、主な理由は次の2つだった
    1. ADK は `instruction` の後ろに `You are an agent. Your internal name is "study_agent". The description about you is "..."` を自動で付け足す（`name` と `description` は複数エージェント間の引き継ぎに使われる）
    2. ツールが返した文字列を `{"result": "..."}` で包んで返す。また引数のスキーマに `title` が付く
  - 書き方の比較：

    | 観点 | Pydantic AI | ADK |
    |---|---|---|
    | ツールの登録 | `agent.tool_plain(f)` を1つずつ | `Agent(tools=[f, g, h])` に並べる |
    | ツールの説明文 | docstring と型ヒント | 同じ（docstring と型ヒント） |
    | モデルの指定 | 実行時に渡せる（`run_sync(model=...)`） | `Agent(model="gemini-...")` に文字列で書く |
    | 実行 | `agent.run_sync(質問)` で結果が返る | `Runner` と `SessionService` を用意し、`run_async()` が出す `Event` を順に読む |
    | 会話履歴 | `result.all_messages()`（呼び出し側が持つ） | `Session` に保存される（既定はメモリ） |
    | テスト | `TestModel` が組み込みで用意されている | 組み込みの偽モデルはなく、`BaseLlm` を継承して自作した |
    | 実行の様子を見る | 自作の `--trace`（または Logfire） | `adk web` の UI が組み込みで付いている |
  - `adk web` での見え方：
    - プロンプトを入力すると、`study_agent` とツール（`search_glossary` など）の関係を表す図が表示された
    - 質問すると図の `search_glossary` の部分が光り、どのツールが呼ばれたかが目で見て分かった
    - 裏側では、1つの質問が `functionCall` → `functionResponse` → `text` の3つの Event として記録される（Pydantic AI の `ToolCallPart` / `ToolReturnPart` に対応する）
    - Pydantic AI 版では、同じ情報を自作の `--trace` で文字として出していた。ADK では、エージェントとツールの構成と呼び出しの流れを図で確かめられる
- 気づき・疑問：
  - どちらのフレームワークでも「モデル＋ループ＋ツール」の中身は同じで、モデルが読むのは結局 `instruction` とツールの docstring だった。フレームワークを替えても、ツールの選び方は変わらなかった
  - ただしフレームワークは、プロンプトに見えない文（ADK の英語の自己紹介文）やツール結果の包み方を勝手に足す。トークン数（料金）が増え、回答に影響することもありうるので、実際に送られたリクエストを一度は確かめるべきだと感じた
  - Pydantic AI は「1回の質問に1関数呼び出し」で小さく試すのに向き、ADK は Session・イベント・Web UI まで揃っていて、複数エージェントや対話を続けるアプリに向くように見えた
  - 疑問：ADK が付け足す自己紹介文は、`name` / `description` を日本語にすると変わるのか。外す設定はあるのか
