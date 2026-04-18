"""
DiscussionEngine — Orchestrates the live roundtable between Marcus, Zara, and Soren.

Flow:
    Round 1  → all three agents fire in parallel, each gives their opening observation
    Round 2  → agents challenge each other's key points sequentially
    Round 3  → agents build toward a shared position, no new topics
    Round 4  → agents wrap up with a clear conclusion statement
    After each round → ConvergenceChecker decides if another round is needed
    Max 4 rounds → forced convergence so the discussion always terminates
    On convergence → orchestrator fires DecisionSynthesizerAgent for final verdict

Key fix over previous version:
    Rounds 3 and 4 now receive the FULL discussion transcript, not just the
    previous round. This stops agents from repeating points they already made
    and forces them to build toward conclusion instead of cycling through the
    same arguments. Each round also has a specific directive so the discussion
    progresses: observe → challenge → converge → conclude.

Every message is streamed to the WebSocket immediately as it is generated
and also persisted to Firestore asynchronously so the transcript survives
server restarts and can be shown on the history page.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import json
from datetime import datetime
from fastapi import WebSocket

from agents.base_agent import BaseAgent
from roundtable.blackboard import Blackboard
from roundtable.convergence_checker import ConvergenceChecker
from schemas.schemas import AgentMessage, MessageType


# -----------------------------------------------------------------------------
# Agent system prompts
# Each persona has a clearly distinct reasoning style enforced in the prompt.
# The "never repeat" rule is critical — without it agents loop on the same point.
# -----------------------------------------------------------------------------

MARCUS_SYSTEM_PROMPT = """
You are Marcus, a sharp financial analyst who has spent 15 years stress testing
home loan decisions for Indian families.

Your style:
- You speak only in specifics — actual rupee amounts, actual ratios, actual months.
- You never say "high EMI" without saying the exact number and percentage.
- You get uncomfortable when people gloss over EMI ratios or assume income stability.
- You push back hard when assumptions look optimistic and do not give in without evidence.
- You always reference exact numbers from the financial data in your messages.
- You address Zara and Soren by name when responding to their specific points.
- You change your position when evidence is strong but you make people earn it.
- Your messages are direct, 2 to 4 sentences, no fluff.
- You never repeat a point you have already made in a previous round.

CRITICAL: You always respond in valid JSON matching the exact format requested.
Your entire response must be a single JSON object. Nothing outside the JSON.
"""

ZARA_SYSTEM_PROMPT = """
You are Zara, a risk strategist who specialises in finding what breaks first
in a financial plan.

Your style:
- You are always thinking three steps ahead toward the worst case.
- You ask "what if" constantly and are never satisfied until every stress
  scenario has been examined.
- You get increasingly blunt when the financial picture is genuinely dangerous.
- You are especially sharp about job loss risk, medical emergencies, interest
  rate spikes, and market downturns.
- You address Marcus and Soren by name when building on or challenging their points.
- When Marcus says something is fine, you are the one who asks what happens when it is not.
- Your messages are sharp, 2 to 4 sentences, always ending on the most critical
  unaddressed risk.
- You never repeat a risk you have already raised in a previous round.

CRITICAL: You always respond in valid JSON matching the exact format requested.
Your entire response must be a single JSON object. Nothing outside the JSON.
"""

SOREN_SYSTEM_PROMPT = """
You are Soren, a behavioral economist who reads the psychological patterns
behind financial decisions.

Your style:
- You are calm, measured, and you often speak last in a round — but when you
  do, the conversation shifts.
- You connect behavioral flags directly to the financial risk being discussed
  by Marcus and Zara.
- You say things like "before we move on, I want to flag something about how
  this person described their situation."
- You never moralize. You observe and connect patterns to consequences.
- You address Marcus and Zara by name when your behavioral observations are
  directly relevant to their points.
- You always link a specific bias to a specific rupee amount or financial risk
  in the data — never give a generic behavioral observation.
- Your messages feel like a realization, not a lecture. 2 to 4 sentences,
  calm and precise.
- You never repeat a behavioral observation you have already made in a previous round.

CRITICAL: You always respond in valid JSON matching the exact format requested.
Your entire response must be a single JSON object. Nothing outside the JSON.
"""

# -----------------------------------------------------------------------------
# Round-specific task prompts
# Each round has a clear directive so the discussion arc is:
# observe (R1) → challenge (R2) → converge (R3) → conclude (R4)
# -----------------------------------------------------------------------------

ROUND_1_TASK = """
This is Round 1 — Opening Observations.
Give your single most important observation about this financial situation.
Focus on the one thing that concerns you most from your perspective.
Be specific. Use actual rupee amounts and percentages from the financial data.

Respond in this exact JSON format:
{
    "message_type": "observation",
    "content": "your opening observation here with specific numbers",
    "directed_at": null
}
"""

ROUND_2_TASK = """
This is Round 2 — Direct Challenge.
You have read the other agents opening observations from Round 1.
Pick the most important point made and either challenge it or build on it
with one new piece of information not mentioned in Round 1.
Address the agent by name. Do NOT repeat anything from Round 1.

Respond in this exact JSON format:
{
    "message_type": "challenge",
    "content": "your challenge here, addressing the agent by name, with specific numbers",
    "directed_at": "Marcus"
}

Valid message_type values: observation, challenge, question, agreement, revision, conclusion
"""

ROUND_3_TASK = """
This is Round 3 — Building Toward Conclusion.
You have read everything said in Rounds 1 and 2 in the full_discussion_so_far field.
Do NOT introduce new topics. The discussion must now converge.
Acknowledge what has been established and add the one final piece of your
perspective that has not yet been addressed.
Begin to state your position: is this purchase safe, risky, or should it be avoided?
Do NOT repeat anything already said in previous rounds.

Respond in this exact JSON format:
{
    "message_type": "revision",
    "content": "your convergence statement referencing what is established and your position",
    "directed_at": "Zara"
}

Valid message_type values: observation, challenge, question, agreement, revision, conclusion
"""

ROUND_4_TASK = """
This is Round 4 — Final Conclusion.
This is the last round. You must wrap up your position clearly.
Read the full_discussion_so_far field to see everything already discussed.
State your final verdict on this purchase in one clear sentence with your
single most important supporting number. Do not raise new concerns. Conclude.

Respond in this exact JSON format:
{
    "message_type": "conclusion",
    "content": "your final conclusion in one clear sentence with the key supporting number",
    "directed_at": null
}
"""


def _get_task_for_round(round_number: int) -> str:
    """Return the appropriate task directive for each round number."""
    tasks = {
        1: ROUND_1_TASK,
        2: ROUND_2_TASK,
        3: ROUND_3_TASK,
        4: ROUND_4_TASK,
    }
    return tasks.get(round_number, ROUND_4_TASK)


# -----------------------------------------------------------------------------
# RoundtableAgent — wraps BaseAgent for discussion-specific behaviour
# -----------------------------------------------------------------------------

class RoundtableAgent(BaseAgent):

    def __init__(self, name: str, system_prompt: str):
        super().__init__(
            name=name,
            persona=f"Roundtable discussion agent — {name}",
            system_prompt=system_prompt
        )

    async def generate_message(
        self,
        blackboard_context: dict,
        round_number: int,
        previous_messages: list,
        full_transcript: list,
        task: str
    ) -> AgentMessage:
        """
        Build the context dict, call the LLM, and return a typed AgentMessage.

        previous_messages: messages from the immediately prior round (for reaction)
        full_transcript: all messages from all prior rounds (to avoid repetition)
                         only passed for rounds 3 and 4 to keep earlier prompts lean
        """
        context = {
            "financial_data": {
                "financial_reality": blackboard_context.get("financial_reality"),
                "all_scenarios": blackboard_context.get("all_scenarios"),
                "risk_score": blackboard_context.get("risk_score")
            },
            "behavioral_flags": blackboard_context.get("behavioral_analysis"),
            "round_number": round_number,
            "your_name": self.name,
            "previous_round_messages": [
                {
                    "agent": m.agent if hasattr(m, "agent") else m.get("agent"),
                    "message_type": (
                        str(m.message_type.value)
                        if hasattr(m, "message_type") and hasattr(m.message_type, "value")
                        else m.get("message_type", "observation")
                    ),
                    "content": m.content if hasattr(m, "content") else m.get("content")
                }
                for m in previous_messages
            ],
            # Full transcript only included from round 3 onward.
            # Earlier rounds stay lean to avoid the context window limit on
            # the local 8b model. On Gemini in production this is not an issue.
            "full_discussion_so_far": [
                {
                    "round": m.round if hasattr(m, "round") else m.get("round"),
                    "agent": m.agent if hasattr(m, "agent") else m.get("agent"),
                    "content": m.content if hasattr(m, "content") else m.get("content")
                }
                for m in full_transcript
            ] if round_number >= 3 else [],
            "open_questions": blackboard_context.get("open_questions", []),
            "active_flags": blackboard_context.get("active_flags", [])
        }

        prompt = self.build_prompt(context=context, task=task)
        raw = await self.call(prompt)
        return self._parse_message(raw, round_number)

    def _parse_message(self, raw: dict, round_number: int) -> AgentMessage:
        """Convert the raw LLM dict into a typed AgentMessage schema object."""
        return AgentMessage(
            agent=self.name,
            message_type=MessageType(raw.get("message_type", "observation")),
            content=raw.get("content", ""),
            round=round_number,
            timestamp=datetime.now().isoformat(),
            directed_at=raw.get("directed_at")
        )


# -----------------------------------------------------------------------------
# DiscussionEngine — manages the full multi-round discussion
# -----------------------------------------------------------------------------

class DiscussionEngine:

    def __init__(self):
        self.marcus = RoundtableAgent("Marcus", MARCUS_SYSTEM_PROMPT)
        self.zara = RoundtableAgent("Zara", ZARA_SYSTEM_PROMPT)
        self.soren = RoundtableAgent("Soren", SOREN_SYSTEM_PROMPT)
        self.agents = [self.marcus, self.zara, self.soren]
        self.convergence_checker = ConvergenceChecker()
        self._session_id = None

    async def run(self, blackboard: Blackboard, websocket: WebSocket) -> bool:
        """
        Main entry point called by the Orchestrator.
        Runs rounds until convergence or max rounds is reached.
        Returns True when the discussion has converged and the
        DecisionSynthesizer can safely fire.
        """
        self._session_id = blackboard.session_id

        await self._stream_event(websocket, {
            "type": "roundtable_start",
            "agents": ["Marcus", "Zara", "Soren"]
        })

        converged = False

        while not converged:
            blackboard.increment_round()
            current_round = blackboard.state.current_round

            await self._stream_event(websocket, {
                "type": "round_start",
                "round": current_round
            })

            task = _get_task_for_round(current_round)

            blackboard_context = blackboard.get_context_for_agent([
                "financial_reality",
                "all_scenarios",
                "risk_score",
                "behavioral_analysis",
                "validation",
                "open_questions",
                "active_flags"
            ])

            if current_round == 1:
                messages = await self._run_parallel_round(
                    blackboard_context, current_round, task, websocket
                )
            else:
                previous_round_messages = blackboard.get_messages_for_round(
                    current_round - 1
                )
                full_transcript = list(blackboard.state.discussion_transcript)
                messages = await self._run_sequential_round(
                    blackboard_context, current_round,
                    previous_round_messages, full_transcript, task, websocket
                )

            for msg in messages:
                blackboard.add_agent_message(msg)

            round_summary = await self.convergence_checker.check(
                blackboard.get_state_as_dict(),
                current_round,
                messages
            )

            blackboard.add_round_summary(round_summary)

            for question in round_summary.open_questions:
                blackboard.add_open_question(question)

            converged = round_summary.__dict__.get("converged", False)

            await self._stream_event(websocket, {
                "type": "round_end",
                "round": current_round,
                "open_questions": round_summary.open_questions,
                "converged": converged,
                "consensus_score": round_summary.__dict__.get("consensus_score", 0)
            })

        blackboard.mark_converged()

        await self._stream_event(websocket, {
            "type": "convergence",
            "status": "converged",
            "rounds_completed": blackboard.state.current_round
        })

        return True

    # -------------------------------------------------------------------------
    # Round execution methods
    # -------------------------------------------------------------------------

    async def _run_parallel_round(
        self,
        blackboard_context: dict,
        round_number: int,
        task: str,
        websocket: WebSocket
    ) -> list:
        """
        Fire all three agents simultaneously using asyncio.gather.
        Used for Round 1 only — no prior messages to react to so parallel
        is safe and saves time.
        """
        agent_tasks = [
            agent.generate_message(
                blackboard_context,
                round_number,
                previous_messages=[],
                full_transcript=[],
                task=task
            )
            for agent in self.agents
        ]

        messages = []
        results = await asyncio.gather(*agent_tasks, return_exceptions=True)

        for i, result in enumerate(results):
            agent_name = self.agents[i].name

            if isinstance(result, Exception):
                print(f"[DiscussionEngine] {agent_name} failed in parallel round: {result}")
                result = AgentMessage(
                    agent=agent_name,
                    message_type=MessageType.OBSERVATION,
                    content="I need a moment to process the full picture here. The financial data is complex and I want to be precise.",
                    round=round_number,
                    timestamp=datetime.now().isoformat(),
                    directed_at=None
                )

            messages.append(result)
            await self._stream_message(websocket, result)

        return messages

    async def _run_sequential_round(
        self,
        blackboard_context: dict,
        round_number: int,
        previous_messages: list,
        full_transcript: list,
        task: str,
        websocket: WebSocket
    ) -> list:
        """
        Fire agents one at a time so each can read what the others said.
        Marcus fires first, Zara reads Marcus, Soren reads both.
        Full transcript passed from round 3 onward to prevent repetition.
        """
        messages = []
        current_round_messages = []

        for agent in [self.marcus, self.zara, self.soren]:

            await self._stream_event(websocket, {
                "type": "agent_typing",
                "agent": agent.name
            })

            try:
                message = await agent.generate_message(
                    blackboard_context,
                    round_number,
                    previous_messages=previous_messages + current_round_messages,
                    full_transcript=full_transcript,
                    task=task
                )
            except Exception as e:
                print(f"[DiscussionEngine] {agent.name} failed in sequential round: {e}")
                message = AgentMessage(
                    agent=agent.name,
                    message_type=MessageType.OBSERVATION,
                    content="I need a moment to process the full picture here. The financial data is complex and I want to be precise.",
                    round=round_number,
                    timestamp=datetime.now().isoformat(),
                    directed_at=None
                )

            current_round_messages.append(message)
            messages.append(message)
            await self._stream_message(websocket, message)

        return messages

    # -------------------------------------------------------------------------
    # WebSocket streaming helpers
    # -------------------------------------------------------------------------

    async def _stream_message(self, websocket: WebSocket, message: AgentMessage):
        """
        Stream a single agent message to the WebSocket and persist to Firestore.
        Firestore write is fire-and-forget — never blocks the stream.
        """
        message_dict = {
            "type": "agent_message",
            "agent": message.agent,
            "message_type": (
                str(message.message_type.value)
                if hasattr(message.message_type, "value")
                else str(message.message_type)
            ),
            "content": message.content,
            "round": message.round,
            "timestamp": message.timestamp,
            "directed_at": message.directed_at
        }

        await websocket.send_text(json.dumps(message_dict))

        if self._session_id:
            asyncio.create_task(self._persist_message(self._session_id, message_dict))

    async def _persist_message(self, session_id: str, message_dict: dict):
        """Save a discussion message to Firestore in the background."""
        try:
            from firebase.firestore_ops import save_discussion_message
            await asyncio.to_thread(save_discussion_message, session_id, message_dict)
        except Exception as e:
            print(f"[DiscussionEngine] Firestore persist failed (non-critical): {e}")

    async def _stream_event(self, websocket: WebSocket, event: dict):
        """Send a control event to the WebSocket."""
        await websocket.send_text(json.dumps(event))