"""第3回 宿題（発展a）: app/agent.py と同じ学習支援エージェントを Google ADK で作り直したもの。

使い方（リポジトリのルートで）:
    uv sync --group adk
    uv run --env-file .env adk web lectures/03/homework               # ブラウザで対話・イベントを確認
    uv run --env-file .env adk run lectures/03/homework/study_agent   # ターミナルで対話
    uv run --env-file .env python lectures/03/homework/run_adk.py --trace "LoRAとQLoRAの違いは？"
（google-genai は GEMINI_API_KEY も読むので、GOOGLE_API_KEY を別に設定しなくてよい）

Pydantic AI 版との違い:
- ツールは関数を tools=[...] に並べるだけ（docstring と型ヒントが説明文になるのは同じ）
- モデルは文字列で指定する（Pydantic AI 版はテストのため実行時に渡していた）
- 実行には Runner と SessionService が要る（会話履歴は Session に保存される）
"""

import sys
from pathlib import Path

from google.adk.agents import Agent

# adk web / adk run から読み込まれたときにも app パッケージを import できるようにする
REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app import tools  # noqa: E402
from app.agent import INSTRUCTIONS  # noqa: E402  プロンプトは Pydantic AI 版と共通にして比べる
from app.config import MODEL  # noqa: E402

root_agent = Agent(
    name="study_agent",
    model=MODEL,
    description="AIE2026 の学習支援エージェント（用語集・各回の要点・確認問題）",
    instruction=INSTRUCTIONS,
    tools=[tools.search_glossary, tools.get_lecture_summary, tools.make_quiz],
)
