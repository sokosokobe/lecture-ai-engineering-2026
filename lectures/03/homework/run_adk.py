"""ADK 版エージェントに1回質問し、app.agent の --trace と同じ形でツール呼び出しを表示する。

    uv run --env-file .env python lectures/03/homework/run_adk.py --trace "LoRAとQLoRAの違いは？"

ADK は Pydantic AI の run_sync() のような「1回呼んで結果を受け取る」入口を持たない。
Runner に Session（会話履歴の置き場所）を渡し、run_async() が順に出す Event を読む。
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from google.adk.runners import InMemoryRunner  # noqa: E402
from google.genai import types  # noqa: E402

from study_agent.agent import root_agent  # noqa: E402

APP_NAME = "study_agent"
USER_ID = "student"


async def ask(question: str, agent=root_agent) -> list:
    """質問を1つ投げ、エージェントが出した Event をすべて返す。"""
    runner = InMemoryRunner(agent=agent, app_name=APP_NAME)
    session = await runner.session_service.create_session(app_name=APP_NAME, user_id=USER_ID)
    message = types.Content(role="user", parts=[types.Part(text=question)])
    return [
        event
        async for event in runner.run_async(user_id=USER_ID, session_id=session.id, new_message=message)
    ]


def final_text(events) -> str:
    for event in reversed(events):
        if event.is_final_response() and event.content and event.content.parts:
            return "".join(p.text or "" for p in event.content.parts if not p.thought)
    return ""


def print_trace(events) -> None:
    """Event ごとに、ツール呼び出し・ツールの戻り値・トークン数を表示する。"""
    print("\n--- trace ---")
    requests = input_tokens = output_tokens = 0
    for event in events:
        if event.usage_metadata:  # LLM の応答から作られた Event だけが usage を持つ
            requests += 1
            input_tokens += event.usage_metadata.prompt_token_count or 0
            output_tokens += event.usage_metadata.candidates_token_count or 0
        for call in event.get_function_calls():
            print(f"[tool call]   {call.name}({call.args})")
        for resp in event.get_function_responses():
            print(f"[tool return] {resp.name} -> {str(resp.response)[:120]}…")
    print(f"[usage] requests={requests}, input_tokens={input_tokens}, output_tokens={output_tokens}")


def main() -> None:
    parser = argparse.ArgumentParser(description="ADK 版の学習支援エージェントに質問する")
    parser.add_argument("question")
    parser.add_argument("--trace", action="store_true", help="ツール呼び出しを表示する")
    args = parser.parse_args()

    print(f"[model] {root_agent.model}")
    events = asyncio.run(ask(args.question))
    print(final_text(events))
    if args.trace:
        print_trace(events)


if __name__ == "__main__":
    main()
