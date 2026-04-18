"""
ConvergenceChecker — Decides after each round whether the roundtable
discussion has reached sufficient consensus to hand off to the
DecisionSynthesizer, or whether another round is needed.

Latency optimization added:
    A rule-based pre-check runs before every LLM call. If the answer is
    obvious from the round number and message types alone, the LLM call
    is skipped entirely — saving 10-15 seconds per round on Gemini and
    30-40 seconds per round on Ollama.

    Rule 1: Round 1 is never converged — agents just opened, skip LLM,
            return consensus_score 25 immediately.
    Rule 2: If all three agents used message_type "conclusion" in this
            round, they have clearly concluded — skip LLM, return
            consensus_score 95 and converged True.
    Rule 3: Everything else — call LLM as normal.
    Rule 4: Round 4 — forced convergence, already handled before pre-check.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from dataclasses import dataclass
from typing import Optional

from agents.base_agent import BaseAgent
from schemas.schemas import RoundSummary, AgentMessage, MessageType


SYSTEM_PROMPT = """
You are a discussion convergence checker for a financial advisory roundtable.
Your job is to read the latest round of agent discussion and decide if the agents
have reached sufficient consensus to move to a final verdict, or if another round
of discussion is needed.

You look for:
- Whether all direct challenges have been responded to
- Whether open questions from previous rounds have been addressed
- Whether agent positions are converging or diverging
- Whether the key financial risks have been identified and discussed

You are strict — you only declare convergence when the key issues have been addressed.
You always respond in valid JSON matching the exact format requested.
CRITICAL: Your entire response must be a single JSON object. Nothing outside the JSON.
"""

# Maximum rounds before forcing convergence regardless of discussion state.
MAX_ROUNDS = 4


class ConvergenceChecker(BaseAgent):

    def __init__(self):
        super().__init__(
            name="ConvergenceChecker",
            persona="Discussion moderator who decides when the roundtable has reached consensus",
            system_prompt=SYSTEM_PROMPT
        )

    async def check(
        self,
        blackboard_dict: dict,
        current_round: int,
        round_messages: list
    ) -> RoundSummary:
        """
        Main entry point called by DiscussionEngine after each round.
        Returns a RoundSummary with converged and consensus_score attached.

        Pre-check runs first to skip the LLM call in obvious cases.
        Forces convergence at MAX_ROUNDS so the discussion always terminates.
        """
        # Rule 4 — forced convergence at max rounds, no LLM needed
        if current_round >= MAX_ROUNDS:
            return self._force_convergence(current_round, round_messages)

        # Rule-based pre-check — skip LLM if answer is obvious
        pre_check_result = self._rule_based_pre_check(current_round, round_messages)
        if pre_check_result is not None:
            return pre_check_result

        # LLM check — only runs when rules cannot determine convergence
        context = self._build_context(blackboard_dict, current_round, round_messages)
        prompt = self._build_check_prompt(context)
        raw = await self.call(prompt)
        return self._parse_output(raw, current_round, round_messages)

    # -------------------------------------------------------------------------
    # Rule-based pre-check — saves LLM calls in obvious cases
    # -------------------------------------------------------------------------

    def _rule_based_pre_check(
        self,
        current_round: int,
        round_messages: list
    ) -> Optional[RoundSummary]:
        """
        Check obvious convergence or non-convergence cases without calling the LLM.
        Returns a RoundSummary if the answer is clear, None if the LLM should decide.

        Rule 1 — Round 1 is never converged.
            Agents just gave opening observations. There is no basis for convergence
            yet. Skip the LLM and return consensus_score 25 immediately.

        Rule 2 — All agents concluded.
            If all three agents used message_type "conclusion" this round, they have
            explicitly wrapped up. Skip the LLM and return converged True with
            consensus_score 95.

        Rule 3 — Everything else.
            Return None so the LLM runs its normal check.
        """

        # Rule 1 — round 1 is never converged, no LLM needed
        if current_round == 1:
            print(f"[ConvergenceChecker] Round 1 pre-check: not converged, skipping LLM")
            return self._build_summary(
                current_round=current_round,
                round_messages=round_messages,
                converged=False,
                consensus_score=25,
                productive=True,
                open_questions=[],
                conflicts_identified=[]
            )

        # Rule 2 — all agents used conclusion message type
        message_types = []
        for m in round_messages:
            if hasattr(m, "message_type"):
                mt = m.message_type.value if hasattr(m.message_type, "value") else str(m.message_type)
            else:
                mt = m.get("message_type", "observation")
            message_types.append(mt)

        all_concluded = (
            len(message_types) >= 3 and
            all(mt == "conclusion" for mt in message_types)
        )

        if all_concluded:
            print(f"[ConvergenceChecker] Round {current_round} pre-check: all agents concluded, skipping LLM")
            return self._build_summary(
                current_round=current_round,
                round_messages=round_messages,
                converged=True,
                consensus_score=95,
                productive=True,
                open_questions=[],
                conflicts_identified=[]
            )

        # Rule 3 — not obvious, let LLM decide
        return None

    # -------------------------------------------------------------------------
    # Context and prompt builders
    # -------------------------------------------------------------------------

    def _build_context(
        self,
        blackboard_dict: dict,
        current_round: int,
        round_messages: list
    ) -> dict:
        """
        Build a lean context dict for the convergence check.
        Only passes what is needed to assess whether consensus has been reached.
        """
        return {
            "current_round": current_round,
            "max_rounds": MAX_ROUNDS,
            "rounds_remaining": MAX_ROUNDS - current_round,
            "round_messages": [
                {
                    "agent": m.agent if hasattr(m, "agent") else m.get("agent"),
                    "message_type": (
                        m.message_type.value
                        if hasattr(m, "message_type") and hasattr(m.message_type, "value")
                        else m.get("message_type", "observation")
                    ),
                    "content": m.content if hasattr(m, "content") else m.get("content"),
                    "directed_at": m.directed_at if hasattr(m, "directed_at") else m.get("directed_at")
                }
                for m in round_messages
            ],
            "open_questions": blackboard_dict.get("open_questions", []),
            "active_flags": blackboard_dict.get("active_flags", []),
            "previous_round_summaries": [
                {
                    "round": s.round_number if hasattr(s, "round_number") else s.get("round_number"),
                    "productive": s.productive if hasattr(s, "productive") else s.get("productive"),
                    "open_questions": (
                        s.open_questions if hasattr(s, "open_questions")
                        else s.get("open_questions", [])
                    )
                }
                for s in blackboard_dict.get("round_summaries", [])
            ]
        }

    def _build_check_prompt(self, context: dict) -> str:
        return self.build_prompt(
            context=context,
            task="""
Read the latest round of discussion messages and assess the state of convergence.

Convergence criteria — all of these should be true to declare converged:
    1. All direct challenges between agents have received a response
    2. No critical open financial questions remain unanswered
    3. Agent positions are moving toward agreement, not further apart
    4. The primary risk factors for this specific financial situation have been identified

consensus_score is a number from 0 to 100 representing how close the agents are to consensus.
Use this guide:
    0-25   — agents are actively disagreeing, major issues unresolved
    26-50  — some agreement but significant open questions remain
    51-75  — mostly aligned, minor points still unresolved
    76-100 — strong consensus, all key issues addressed

converged must be true only if consensus_score is 75 or above AND key risks are identified.
productive must be true if this round generated new information not in previous rounds.
open_questions must list specific unanswered questions raised in this round.
conflicts_identified must list specific contradictions surfaced in this round.

Respond in this exact JSON format:
{
    "converged": false,
    "consensus_score": 45,
    "productive": true,
    "open_questions": [
        "Has the user considered the impact of property maintenance costs on monthly cash flow?"
    ],
    "conflicts_identified": [
        "Marcus believes the EMI ratio is manageable but Zara flagged job loss scenario as critical"
    ],
    "summary": "Round identified key risk in job loss scenario with unresolved question about maintenance costs"
}
"""
        )

    # -------------------------------------------------------------------------
    # Output parsers
    # -------------------------------------------------------------------------

    def _parse_output(
        self,
        raw: dict,
        current_round: int,
        round_messages: list
    ) -> RoundSummary:
        """
        Parse the LLM response into a RoundSummary.
        Flattens open_questions and conflicts_identified from dicts to strings
        so the RoundSummary schema never gets a Pydantic type error.
        """
        # Flatten open_questions — model sometimes returns dicts instead of strings
        open_questions = []
        for q in raw.get("open_questions", []):
            if isinstance(q, str):
                open_questions.append(q)
            elif isinstance(q, dict):
                open_questions.append(
                    q.get("message") or q.get("content") or q.get("question") or str(q)
                )

        # Flatten conflicts_identified — same issue
        conflicts_identified = []
        for c in raw.get("conflicts_identified", []):
            if isinstance(c, str):
                conflicts_identified.append(c)
            elif isinstance(c, dict):
                conflicts_identified.append(
                    c.get("description") or c.get("message") or c.get("content") or str(c)
                )

        return self._build_summary(
            current_round=current_round,
            round_messages=round_messages,
            converged=raw.get("converged", False),
            consensus_score=int(raw.get("consensus_score", 0)),
            productive=raw.get("productive", True),
            open_questions=open_questions,
            conflicts_identified=conflicts_identified
        )

    def _force_convergence(
        self,
        current_round: int,
        round_messages: list
    ) -> RoundSummary:
        """
        Called when MAX_ROUNDS is reached.
        Forces converged=True and consensus_score=100 so the synthesizer
        always fires and the discussion never runs forever.
        """
        print(f"[ConvergenceChecker] Round {current_round}: max rounds reached, forcing convergence")
        return self._build_summary(
            current_round=current_round,
            round_messages=round_messages,
            converged=True,
            consensus_score=100,
            productive=True,
            open_questions=[],
            conflicts_identified=[]
        )

    # -------------------------------------------------------------------------
    # Shared helpers
    # -------------------------------------------------------------------------

    def _build_summary(
        self,
        current_round: int,
        round_messages: list,
        converged: bool,
        consensus_score: int,
        productive: bool,
        open_questions: list,
        conflicts_identified: list
    ) -> RoundSummary:
        """
        Build a RoundSummary with converged and consensus_score attached.
        Single method used by all paths — pre-check, LLM parse, and forced.
        """
        messages = self._build_messages(round_messages, current_round)

        summary = RoundSummary(
            round_number=current_round,
            messages=messages,
            productive=productive,
            open_questions=open_questions,
            conflicts_identified=conflicts_identified
        )

        summary.__dict__["converged"] = converged
        summary.__dict__["consensus_score"] = consensus_score

        return summary

    def _build_messages(self, round_messages: list, current_round: int) -> list:
        """
        Convert raw message dicts or AgentMessage objects into a uniform
        list of AgentMessage objects for the RoundSummary.
        """
        messages = []
        for m in round_messages:
            if hasattr(m, "agent"):
                messages.append(m)
            else:
                messages.append(AgentMessage(
                    agent=m.get("agent", ""),
                    message_type=MessageType(m.get("message_type", "observation")),
                    content=m.get("content", ""),
                    round=current_round,
                    timestamp=datetime.now().isoformat(),
                    directed_at=m.get("directed_at")
                ))
        return messages