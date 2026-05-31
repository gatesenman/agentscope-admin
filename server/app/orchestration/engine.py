"""Execution engine for multi-agent orchestration patterns.

Members are LLM personas (instruction + model config). The engine calls the
model directly through AgentScope's ``get_model`` so a single credential can
drive an entire team, and streams SSE events the frontend renders as a live
transcript:

  {"type": "member_started", "member": "...", "role": "..."}
  {"type": "text_delta", "member": "...", "delta": "..."}
  {"type": "member_finished", "member": "...", "text": "..."}
  {"type": "finished", "output": "..."}
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any, AsyncGenerator

from ..settings import get_settings

_settings = get_settings()


def _event(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"


def _resp_text(content: Any) -> str:
    out: list[str] = []
    for block in content or []:
        if isinstance(block, dict):
            if block.get("type") == "text":
                out.append(block.get("text", ""))
        elif getattr(block, "type", None) == "text":
            out.append(getattr(block, "text", ""))
    return "".join(out)


async def _complete(
    user_id: str,
    cfg: dict[str, Any],
    system: str,
    prompt: str,
) -> str:
    """Single-shot, non-streaming model call."""
    from agentscope.app.storage import ChatModelConfig, RedisStorage
    from agentscope.app._service._model import get_model
    from agentscope.message import Msg

    messages = []
    if system:
        messages.append(
            Msg(name="system", role="system", content=[{"type": "text", "text": system}]),
        )
    messages.append(
        Msg(name="user", role="user", content=[{"type": "text", "text": prompt}]),
    )
    model_cfg = ChatModelConfig(
        type=cfg.get("type", ""),
        credential_id=cfg.get("credential_id", ""),
        model=cfg.get("model", ""),
        parameters=cfg.get("parameters", {}) or {},
    )
    async with RedisStorage(
        host=_settings.redis_host,
        port=_settings.redis_port,
        db=_settings.redis_db,
        password=_settings.redis_password,
    ) as storage:
        model = await get_model(user_id, model_cfg, storage)
        model.stream = False
        result = await model(messages=messages)
        if hasattr(result, "content"):
            return _resp_text(result.content)
        full = ""
        async for resp in result:  # pragma: no cover - defensive
            full = _resp_text(resp.content)
        return full


class OrchestrationEngine:
    """Runs one orchestration definition against a single user query."""

    def __init__(self, pattern: str, config: dict[str, Any], user_id: str = "admin"):
        self.pattern = pattern or "sequential"
        self.config = config or {}
        self.user_id = user_id
        self.members: list[dict[str, Any]] = self.config.get("members") or []
        self.coordinator: dict[str, Any] = self.config.get("coordinator") or {}
        self.max_rounds: int = int(self.config.get("max_rounds") or 4)

    def _member_cfg(self, member: dict[str, Any]) -> dict[str, Any]:
        """A member falls back to the coordinator's credential/model when it
        does not define its own, so a team can share one credential."""
        return {
            "type": member.get("type") or self.coordinator.get("type", ""),
            "credential_id": member.get("credential_id")
            or self.coordinator.get("credential_id", ""),
            "model": member.get("model") or self.coordinator.get("model", ""),
            "parameters": member.get("parameters") or {},
        }

    async def _run_member(self, member: dict[str, Any], task: str) -> str:
        system = member.get("instruction", "") or "You are a helpful assistant."
        return (await _complete(self.user_id, self._member_cfg(member), system, task)).strip()

    # ----- patterns ------------------------------------------------------- #
    async def run(self, query: str) -> AsyncGenerator[str, None]:
        if not self.members:
            yield _event({"type": "finished", "output": "(no members configured)"})
            return
        try:
            if self.pattern == "parallel":
                async for ev in self._run_parallel(query):
                    yield ev
            elif self.pattern == "aggregation":
                async for ev in self._run_aggregation(query):
                    yield ev
            elif self.pattern == "router":
                async for ev in self._run_router(query):
                    yield ev
            elif self.pattern == "supervisor":
                async for ev in self._run_supervisor(query):
                    yield ev
            elif self.pattern == "handoff":
                async for ev in self._run_handoff(query):
                    yield ev
            else:
                async for ev in self._run_sequential(query):
                    yield ev
        except Exception as exc:  # pragma: no cover - surfaced to the client
            yield _event({"type": "error", "message": str(exc)})

    async def _run_sequential(self, query: str) -> AsyncGenerator[str, None]:
        carry = query
        last = ""
        for m in self.members:
            yield _event({"type": "member_started", "member": m.get("name", ""), "role": m.get("role", "")})
            task = (
                f"用户问题：\n{query}\n\n上一步结果：\n{carry}\n\n请完成你的职责。"
                if carry != query
                else query
            )
            out = await self._run_member(m, task)
            last = out
            carry = out
            yield _event({"type": "member_finished", "member": m.get("name", ""), "text": out})
        yield _event({"type": "finished", "output": last})

    async def _run_parallel(self, query: str) -> AsyncGenerator[str, None]:
        for m in self.members:
            yield _event({"type": "member_started", "member": m.get("name", ""), "role": m.get("role", "")})
        results = await asyncio.gather(
            *[self._run_member(m, query) for m in self.members],
        )
        for m, out in zip(self.members, results):
            yield _event({"type": "member_finished", "member": m.get("name", ""), "text": out})
        combined = "\n\n".join(
            f"### {m.get('name', '')}\n{out}" for m, out in zip(self.members, results)
        )
        yield _event({"type": "finished", "output": combined})

    async def _run_aggregation(self, query: str) -> AsyncGenerator[str, None]:
        for m in self.members:
            yield _event({"type": "member_started", "member": m.get("name", ""), "role": m.get("role", "")})
        results = await asyncio.gather(
            *[self._run_member(m, query) for m in self.members],
        )
        for m, out in zip(self.members, results):
            yield _event({"type": "member_finished", "member": m.get("name", ""), "text": out})
        joined = "\n\n".join(
            f"[{m.get('name', '')}]\n{out}" for m, out in zip(self.members, results)
        )
        yield _event({"type": "member_started", "member": "聚合器", "role": "aggregator"})
        system = (
            self.coordinator.get("instruction")
            or "你是聚合器。综合多位专家的回答，去重并消解冲突，输出一个连贯、完整的最终答案。"
        )
        prompt = f"用户问题：\n{query}\n\n各成员回答：\n{joined}\n\n最终答案："
        final = (await _complete(self.user_id, self.coordinator, system, prompt)).strip()
        yield _event({"type": "member_finished", "member": "聚合器", "text": final})
        yield _event({"type": "finished", "output": final})

    async def _run_router(self, query: str) -> AsyncGenerator[str, None]:
        names = [m.get("name", "") for m in self.members]
        descriptions = "\n".join(
            f"- {m.get('name', '')}: {m.get('instruction', '')}" for m in self.members
        )
        yield _event({"type": "member_started", "member": "路由器", "role": "router"})
        system = (
            "你是路由器。从候选成员中选择最适合处理该问题的一个，"
            "只回复其名称，不要任何多余文字。"
        )
        prompt = f"候选成员：\n{descriptions}\n\n用户问题：\n{query}\n\n选择："
        choice = (await _complete(self.user_id, self.coordinator, system, prompt)).strip()
        chosen = self._match_member(choice, names) or self.members[0]
        yield _event({"type": "member_finished", "member": "路由器", "text": f"选择了「{chosen.get('name', '')}」"})

        yield _event({"type": "member_started", "member": chosen.get("name", ""), "role": chosen.get("role", "")})
        out = await self._run_member(chosen, query)
        yield _event({"type": "member_finished", "member": chosen.get("name", ""), "text": out})
        yield _event({"type": "finished", "output": out})

    async def _run_supervisor(self, query: str) -> AsyncGenerator[str, None]:
        names = [m.get("name", "") for m in self.members]
        roster = "\n".join(
            f"- {m.get('name', '')}: {m.get('instruction', '')}" for m in self.members
        )
        transcript: list[str] = []
        for _ in range(self.max_rounds):
            yield _event({"type": "member_started", "member": "主管", "role": "supervisor"})
            system = (
                self.coordinator.get("instruction")
                or "你是主管，负责调度下属完成用户任务。"
            )
            history = "\n\n".join(transcript) if transcript else "（暂无）"
            prompt = (
                f"下属成员：\n{roster}\n\n用户任务：\n{query}\n\n"
                f"已有进展：\n{history}\n\n"
                "如果任务已可作答，请回复 `FINAL: <最终答案>`；"
                "否则回复 `DELEGATE: <成员名称> | <交给该成员的具体子任务>`。"
            )
            decision = (await _complete(self.user_id, self.coordinator, system, prompt)).strip()
            if decision.upper().startswith("FINAL"):
                final = decision.split(":", 1)[1].strip() if ":" in decision else decision
                yield _event({"type": "member_finished", "member": "主管", "text": f"结束：{final}"})
                yield _event({"type": "finished", "output": final})
                return
            target, subtask = self._parse_delegation(decision)
            chosen = self._match_member(target, names) or self.members[0]
            yield _event({"type": "member_finished", "member": "主管", "text": f"委派「{chosen.get('name', '')}」：{subtask}"})

            yield _event({"type": "member_started", "member": chosen.get("name", ""), "role": chosen.get("role", "")})
            out = await self._run_member(chosen, subtask or query)
            transcript.append(f"{chosen.get('name', '')}: {out}")
            yield _event({"type": "member_finished", "member": chosen.get("name", ""), "text": out})

        # Reached the round budget: summarise what we have.
        summary = "\n\n".join(transcript)
        final = await _complete(
            self.user_id,
            self.coordinator,
            "综合下属的工作，给出最终答案。",
            f"用户任务：\n{query}\n\n下属工作：\n{summary}\n\n最终答案：",
        )
        yield _event({"type": "finished", "output": final.strip()})

    async def _run_handoff(self, query: str) -> AsyncGenerator[str, None]:
        names = [m.get("name", "") for m in self.members]
        roster = "\n".join(f"- {n}" for n in names)
        current = self.members[0]
        task = query
        last = ""
        for _ in range(self.max_rounds):
            yield _event({"type": "member_started", "member": current.get("name", ""), "role": current.get("role", "")})
            system = (
                (current.get("instruction", "") or "")
                + "\n\n如果该任务超出你的职责，请在回答末尾追加一行 "
                "`HANDOFF: <同事名称>` 把任务转交给更合适的同事；"
                "如果你已完成，请追加一行 `DONE`。\n可选同事：\n"
                + roster
            )
            out = await self._run_member({**current, "instruction": system}, task)
            last = out
            yield _event({"type": "member_finished", "member": current.get("name", ""), "text": out})
            handoff = self._find_handoff(out)
            if handoff is None:
                break
            nxt = self._match_member(handoff, names)
            if nxt is None or nxt.get("id") == current.get("id"):
                break
            current = nxt
            task = f"用户问题：\n{query}\n\n同事 {names} 的交接内容：\n{out}"
        clean = re.sub(r"\n?(HANDOFF:.*|DONE)\s*$", "", last).strip()
        yield _event({"type": "finished", "output": clean})

    # ----- helpers -------------------------------------------------------- #
    def _match_member(self, text: str, names: list[str]) -> dict[str, Any] | None:
        """Find the member whose name best matches ``text`` (LLM free text)."""
        if not text:
            return None
        low = text.lower()
        # Exact / containment match first.
        for m in self.members:
            name = (m.get("name", "") or "").lower()
            if name and (name == low or name in low or low in name):
                return m
        return None

    def _parse_delegation(self, decision: str) -> tuple[str, str]:
        body = decision.split(":", 1)[1] if ":" in decision else decision
        if "|" in body:
            target, subtask = body.split("|", 1)
            return target.strip(), subtask.strip()
        return body.strip(), ""

    @staticmethod
    def _find_handoff(text: str) -> str | None:
        match = re.search(r"HANDOFF:\s*([^\n]+)", text or "")
        return match.group(1).strip() if match else None
