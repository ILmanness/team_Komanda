from typing import Any


class ContextBuilder:

    
    def build(
        self,
        *,
        session: dict[str, Any],
        mission: dict[str, Any] | None = None,
        character: dict[str, Any] | None = None,
        paei_profile: dict[str, Any] | None = None,
        difficulty_profile: dict[str, Any] | None = None,
        messages: list[dict[str, Any]] | None = None,
        memory_summary: str | None = None,
        custom_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        state = session.get("state") or {}

        context = {
            "session": {
                "id": session.get("id"),
                "mode": session.get("mode"),
                "status": session.get("status"),
                "turn": state.get("turn", 0),
            },

            "mission": mission or {},

            "character": character or {},

            "paei_profile": paei_profile or {},

            "difficulty_profile": difficulty_profile or {},

            "state": {
                "turn": state.get("turn", 0),
                "contact": state.get("contact", 0),
                "tension": state.get("tension", 0),
                "progress": state.get("progress", 0),
                "critical_errors": state.get("critical_errors", 0),
                "score": state.get("score", 0),
            },

            "memory": memory_summary or "",

            "history": messages or [],

            "custom_context": custom_context or {},
        }

        return context

    def build_evaluator_context(
        self,
        *,
        game_context: dict[str, Any],
        player_message: str,
    ) -> dict[str, Any]:

        return {
            "game": game_context,
            "player_message": player_message,
        }

    def build_opponent_context(
        self,
        *,
        game_context: dict[str, Any],
        evaluation: dict[str, Any],
    ) -> dict[str, Any]:

        return {
            "game": game_context,
            "evaluation": evaluation,
        }