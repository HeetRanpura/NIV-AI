"""
Orchestrator — Central execution controller for the NIV AI pipeline.

This is the only class that main.py calls into from the AI layer.
It exposes three public methods:

    analyze()               — runs the full analysis pipeline for a new session
    run_roundtable()        — runs the live roundtable and streams to WebSocket
    continue_conversation() — handles follow-up turns after initial analysis

All Firestore writes are fire-and-forget using asyncio.create_task so they
never block the WebSocket stream or the API response.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import asyncio
import json
from fastapi import WebSocket

from roundtable.blackboard import Blackboard
from roundtable.discussion_engine import DiscussionEngine
from agents.ai_reasoning.behavioral_analysis import BehavioralAnalysisAgent
from agents.ai_reasoning.decision_synthesizer import DecisionSynthesizerAgent
from agents.context_interaction.conversation import ConversationAgent
from agents.context_interaction.context_continuity import ContextContinuityAgent
from agents.presentation.presentation import PresentationAgent
from agents.validation.validation import ValidationAgent
from schemas.schemas import (
    UserInput,
    BehavioralIntake,
    VerdictOutput,
    ConversationOutput,
    AnalysisResponse,
    IndiaCostBreakdown,
    FinancialRealityOutput,
    AllScenariosOutput,
    RiskScoreOutput,
)


class Orchestrator:

    def __init__(self):
        # Initialise all agents once at startup so they are reused across sessions
        self.behavioral_agent = BehavioralAnalysisAgent()
        self.synthesizer_agent = DecisionSynthesizerAgent()
        self.conversation_agent = ConversationAgent()
        self.context_agent = ContextContinuityAgent()
        self.presentation_agent = PresentationAgent()
        self.validation_agent = ValidationAgent()
        self.discussion_engine = DiscussionEngine()

        # One blackboard per active session keyed by session_id.
        # The blackboard is the single source of truth for all agent outputs
        # within a session and lives in memory for the duration of the session.
        self._blackboards: dict[str, Blackboard] = {}

        # Context states track the conversation history across turns
        self._context_states: dict = {}

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    def _get_or_create_blackboard(self, session_id: str) -> Blackboard:
        """Return the existing blackboard for this session or create a new one."""
        if session_id not in self._blackboards:
            self._blackboards[session_id] = Blackboard(session_id)
        return self._blackboards[session_id]

    async def _persist_verdict(self, session_id: str, verdict_dict: dict):
        """
        Save the final verdict to Firestore in the background.
        Called via asyncio.create_task so it never blocks the WebSocket stream.
        Failure is logged but never surfaced to the user.
        """
        try:
            from firebase.firestore_ops import save_verdict
            await asyncio.to_thread(save_verdict, session_id, verdict_dict)
        except Exception as e:
            print(f"[Orchestrator] Firestore verdict save failed (non-critical): {e}")

    def _build_analysis_response(self, blackboard: Blackboard) -> AnalysisResponse:
        """
        Build the AnalysisResponse from the current blackboard state.
        If the verdict is not yet available (roundtable not run yet),
        a placeholder verdict is returned so the schema is always valid.
        """
        state = blackboard.state
        return AnalysisResponse(
            session_id=blackboard.session_id,
            financial_reality=state.financial_reality,
            all_scenarios=state.all_scenarios,
            risk_score=state.risk_score,
            behavioral_analysis=state.behavioral_analysis,
            validation=state.validation,
            presentation=state.presentation,
            verdict=state.verdict or VerdictOutput(
                verdict="wait",
                confidence=0,
                primary_reasons=[],
                key_warnings=[],
                safe_price_recommendation=0,
                suggested_actions=[],
                unresolved_conflicts=[],
                final_narrative="Roundtable discussion pending"
            )
        )

    # -------------------------------------------------------------------------
    # Public method 1 — full analysis pipeline
    # -------------------------------------------------------------------------

    async def analyze(
        self,
        session_id: str,
        user_input: UserInput,
        behavioral_intake: BehavioralIntake,
        deterministic_results: dict
    ) -> AnalysisResponse:
        """
        Runs the full AI analysis pipeline for a new session.
        Called by main.py's POST /analyze/{session_id} route.

        Steps:
            1. Load all deterministic results onto the blackboard
            2. Run behavioral analysis and validation in parallel
            3. Run presentation agent to build chart data and warning cards
            4. Update context state for conversation continuity
            5. Return the complete AnalysisResponse
        """
        blackboard = self._get_or_create_blackboard(session_id)

        # Load inputs and deterministic results onto the blackboard
        blackboard.set_user_input(user_input)
        blackboard.set_behavioral_intake(behavioral_intake)

        if deterministic_results.get("india_cost_breakdown"):
            blackboard.set_india_cost_breakdown(
                IndiaCostBreakdown(**deterministic_results["india_cost_breakdown"])
            )

        if deterministic_results.get("financial_reality"):
            blackboard.set_financial_reality(
                FinancialRealityOutput(**deterministic_results["financial_reality"])
            )

        if deterministic_results.get("all_scenarios"):
            blackboard.set_all_scenarios(
                AllScenariosOutput(**deterministic_results["all_scenarios"])
            )

        if deterministic_results.get("risk_score"):
            blackboard.set_risk_score(
                RiskScoreOutput(**deterministic_results["risk_score"])
            )

        # Run behavioral analysis and validation in parallel to save time.
        # Both agents only need the blackboard state that is already populated
        # above so there is no dependency ordering issue.
        behavioral_result, validation_result = await asyncio.gather(
            self.behavioral_agent.analyze(
                behavioral_answers=[a.model_dump() for a in behavioral_intake.answers],
                financial_inputs=user_input.model_dump(),
                india_cost_breakdown=deterministic_results.get("india_cost_breakdown", {})
            ),
            self.validation_agent.validate(
                blackboard.get_state_as_dict()
            )
        )

        blackboard.set_behavioral_analysis(behavioral_result)
        blackboard.set_validation(validation_result)

        # Write behavioral flags and validation conflicts onto the blackboard
        # active_flags list so Marcus, Zara, and Soren can reference them
        for flag in behavioral_result.bias_flags:
            blackboard.add_flag(
                f"{flag.bias_type.value} bias detected: {flag.evidence[:50]}"
            )

        for conflict in validation_result.conflicts:
            blackboard.add_flag(
                f"Conflict: {conflict.description[:50]}"
            )

        # Presentation agent builds all chart data, warning cards, and
        # PDF content from the current blackboard state
        presentation_result = await self.presentation_agent.present(
            blackboard.get_state_as_dict()
        )
        blackboard.set_presentation(presentation_result)

        # Update context state so follow-up conversation turns have history
        context_state = await self.context_agent.update(
            session_id=session_id,
            current_blackboard=blackboard.get_state_as_dict(),
            new_interaction={
                "role": "user",
                "message": "Initial analysis submitted",
                "inputs": user_input.model_dump()
            },
            previous_context=self._context_states.get(session_id)
        )
        self._context_states[session_id] = context_state

        return self._build_analysis_response(blackboard)

    # -------------------------------------------------------------------------
    # Public method 2 — live roundtable WebSocket
    # -------------------------------------------------------------------------

    async def run_roundtable(
        self,
        session_id: str,
        websocket: WebSocket
    ) -> None:
        """
        Runs the live roundtable discussion and streams every message
        to the WebSocket as it is generated.
        Called by main.py's WebSocket /roundtable/{session_id} endpoint.
        analyze() must be called before run_roundtable().

        Flow:
            1. DiscussionEngine runs Marcus, Zara, Soren for up to 4 rounds
            2. DecisionSynthesizerAgent produces the final verdict
            3. verdict_ready event is streamed to the frontend
            4. Verdict is saved to Firestore in the background
        """
        blackboard = self._get_or_create_blackboard(session_id)

        # Guard — analysis must have run first so the blackboard has data
        if not blackboard.state.financial_reality:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": "Analysis must be run before starting the roundtable",
                "recoverable": False
            }))
            return

        # Run the full multi-round discussion — streams messages live
        await self.discussion_engine.run(blackboard, websocket)

        # Once the discussion has converged, fire the synthesizer to produce
        # the final verdict from the complete blackboard state
        verdict = await self.synthesizer_agent.synthesize(
            blackboard.get_state_as_dict()
        )
        blackboard.set_verdict(verdict)

        # Stream verdict to frontend immediately — this must happen before
        # any Firestore write so the user never waits for persistence
        await websocket.send_text(json.dumps({
            "type": "verdict_ready",
            "data": verdict.model_dump()
        }))

        # Save verdict to Firestore in the background — fire and forget
        # so it never blocks or delays the WebSocket response
        asyncio.create_task(
            self._persist_verdict(session_id, verdict.model_dump())
        )

    # -------------------------------------------------------------------------
    # Public method 3 — follow-up conversation turns
    # -------------------------------------------------------------------------

    async def continue_conversation(
        self,
        session_id: str,
        message: str
    ) -> ConversationOutput:
        """
        Handles a follow-up message after the initial analysis.
        Called by main.py's POST /conversation/{session_id} route.
        Parses the user's intent, extracts any updated financial variables,
        and returns instructions for which agents need to rerun.
        """
        blackboard = self._get_or_create_blackboard(session_id)

        # Parse the user message to extract intent and any changed variables
        conversation_output = await self.conversation_agent.parse(
            message=message,
            current_blackboard=blackboard.get_state_as_dict()
        )

        # If the user changed any financial inputs, update the blackboard
        # so subsequent agent calls use the new values
        if conversation_output.extracted_variables:
            current_input = blackboard.state.user_input
            if current_input:
                updated_data = current_input.model_dump()
                updated_data.update(conversation_output.extracted_variables)
                blackboard.set_user_input(UserInput(**updated_data))

        # Update context state so the next turn has this exchange in history
        context_state = await self.context_agent.update(
            session_id=session_id,
            current_blackboard=blackboard.get_state_as_dict(),
            new_interaction={
                "role": "user",
                "message": message
            },
            previous_context=self._context_states.get(session_id)
        )
        self._context_states[session_id] = context_state

        return conversation_output

    # -------------------------------------------------------------------------
    # Session cleanup
    # -------------------------------------------------------------------------

    def clear_session(self, session_id: str):
        """
        Remove all in-memory state for a session.
        Called when a session is completed or has expired.
        """
        if session_id in self._blackboards:
            del self._blackboards[session_id]
        if session_id in self._context_states:
            del self._context_states[session_id]