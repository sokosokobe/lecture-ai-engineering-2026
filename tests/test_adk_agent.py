"""第3回 宿題（発展a）: ADK 版エージェントの配線テスト（APIキー不要）。

ADK には Pydantic AI の TestModel にあたる偽モデルがないので、BaseLlm を継承して作る。
1回目の呼び出しでは登録されたツールを全部呼び、2回目でダミーの回答を返す。
google-adk が入っていない環境（uv sync --group adk をしていない）ではスキップする。
"""

import asyncio
import importlib.util
import sys
from pathlib import Path
from typing import AsyncGenerator

import pytest

pytest.importorskip("google.adk")

from google.adk.models import BaseLlm, LlmRequest, LlmResponse  # noqa: E402
from google.genai import types  # noqa: E402

HOMEWORK = Path(__file__).resolve().parent.parent / "lectures" / "03" / "homework"
sys.path.insert(0, str(HOMEWORK))
spec = importlib.util.spec_from_file_location("run_adk", HOMEWORK / "run_adk.py")
run_adk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run_adk)

from study_agent.agent import root_agent  # noqa: E402

TOOLS = {"search_glossary", "get_lecture_summary", "make_quiz"}
ARGS = {"search_glossary": {"query": "LoRA"}, "get_lecture_summary": {"lecture": 2}, "make_quiz": {"lecture": 2}}


class FakeLlm(BaseLlm):
    model: str = "fake"
    requests: list = []

    async def generate_content_async(self, llm_request: LlmRequest, stream: bool = False) -> AsyncGenerator[LlmResponse, None]:
        self.requests.append(llm_request)
        if len(self.requests) == 1:
            parts = [types.Part(function_call=types.FunctionCall(name=n, args=ARGS[n])) for n in llm_request.tools_dict]
        else:
            parts = [types.Part(text="ダミーの回答")]
        yield LlmResponse(content=types.Content(role="model", parts=parts))


def _run(question: str):
    fake = FakeLlm(requests=[])
    agent = root_agent.model_copy(update={"model": fake})
    return fake, asyncio.run(run_adk.ask(question, agent=agent))


def test_tools_are_offered_called_and_returned():
    fake, events = _run("LoRAとは？")
    assert set(fake.requests[0].tools_dict) == TOOLS
    called = {c.name for e in events for c in e.get_function_calls()}
    returned = {r.name for e in events for r in e.get_function_responses()}
    assert called == returned == TOOLS
    assert run_adk.final_text(events) == "ダミーの回答"


def test_instructions_and_tool_results_reach_the_model():
    fake, _ = _run("LoRAとは？")
    system = fake.requests[0].config.system_instruction
    assert "search_glossary で用語集を確認する" in str(system)
    # 2回目のリクエストの会話履歴に、ツールの戻り値（用語集の定義）が入っている
    history = str(fake.requests[1].contents)
    assert "低ランク行列" in history
