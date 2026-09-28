from copy import deepcopy
from typing import Any, ClassVar

from app.game.evaluator_contract import TurnEvaluation


class GameEngine:


    MIN_VALUE = 0
    MAX_VALUE = 100

    # Draft scoring_and_game_state.md §10.1; resistance is stored as tension.
    ACTION_DELTAS: ClassVar[dict[str, tuple[int, int, int, int, int]]] = {
        'strong_positive': (8, -8, 12, 12, 0),
        'positive': (5, -5, 8, 8, 0),
        'neutral': (0, 0, 2, 0, 0),
        'negative': (-6, 6, 0, -7, 0),
        'critical_error': (-15, 12, -5, -15, 1),
        'recovery_action': (15, -10, 5, 5, 0),
    }

    def apply_evaluation(
        self,
        *,
        state: dict[str, Any],
        evaluation: dict[str, Any],
    ) -> dict[str, Any]:

        if evaluation.get('schema_version') == 'ai10-v1':
            return self._apply_structured(state=state, evaluation=evaluation)

        new_state = deepcopy(state)

        effects = evaluation.get("effects") or {}

        contact_change = self._to_int(
            effects.get("contact", 0)
        )

        tension_change = self._to_int(
            effects.get("tension", 0)
        )

        progress_change = self._to_int(
            effects.get("progress", 0)
        )

        new_state["contact"] = self._bounded_update(
            new_state.get("contact", 0),
            contact_change,
        )

        new_state["tension"] = self._bounded_update(
            new_state.get("tension", 0),
            tension_change,
        )

        new_state["progress"] = self._bounded_update(
            new_state.get("progress", 0),
            progress_change,
        )

        if evaluation.get("critical_error", False):
            new_state["critical_errors"] = (
                self._to_int(
                    new_state.get("critical_errors", 0)
                )
                + 1
            )

        new_state["turn"] = (
            self._to_int(
                new_state.get("turn", 0)
            )
            + 1
        )

        return new_state

    def _apply_structured(
        self,
        *,
        state: dict[str, Any],
        evaluation: dict[str, Any],
    ) -> dict[str, Any]:
        """Only the engine turns a validated event into numerical changes."""
        result = TurnEvaluation.model_validate(evaluation)
        contact, tension, progress, quality, critical = self.ACTION_DELTAS[
            result.proposed_event.action_type
        ]
        if result.intent == 'unknown' and not result.observations.features:
            contact = tension = progress = quality = critical = 0
        new_state = deepcopy(state)
        for key, change in (
            ('contact', contact),
            ('tension', tension),
            ('progress', progress),
        ):
            new_state[key] = self._bounded_update(new_state.get(key, 0), change)
        new_state['negotiation_quality'] = self._bounded_update(
            new_state.get('negotiation_quality', 50), quality,
        )
        new_state['critical_errors'] = self._to_int(
            new_state.get('critical_errors', 0)
        ) + critical
        new_state['turn'] = self._to_int(new_state.get('turn', 0)) + 1
        history = new_state.get('profile_fit_history')
        if not isinstance(history, list):
            history = []
        new_state['profile_fit_history'] = [
            *history,
            result.profile_fit.model_dump(),
        ]
        return new_state

    def check_end_conditions(
        self,
        *,
        state: dict[str, Any],
        max_turns: int = 20,
    ) -> dict[str, Any]:

        turn = self._to_int(
            state.get("turn", 0)
        )

        progress = self._to_int(
            state.get("progress", 0)
        )

        critical_errors = self._to_int(
            state.get("critical_errors", 0)
        )

        if progress >= 100:
            return {
                "finished": True,
                "reason": "success",
            }

        if critical_errors >= 3:
            return {
                "finished": True,
                "reason": "critical_errors",
            }

        if turn >= max_turns:
            return {
                "finished": True,
                "reason": "max_turns",
            }

        return {
            "finished": False,
            "reason": None,
        }

    def build_final_result(
        self,
        *,
        state: dict[str, Any],
        reason: str,
    ) -> dict[str, Any]:

        progress = self._to_int(
            state.get("progress", 0)
        )

        critical_errors = self._to_int(
            state.get("critical_errors", 0)
        )

        if reason == "success":
            result = "success"
        elif reason == "critical_errors":
            result = "failure"
        elif reason == "max_turns":
            result = (
                "success"
                if progress >= 50
                else "failure"
            )
        else:
            result = "finished"

        return {
            "result": result,
            "reason": reason,
            "progress": progress,
            "contact": self._to_int(
                state.get("contact", 0)
            ),
            "tension": self._to_int(
                state.get("tension", 0)
            ),
            "critical_errors": critical_errors,
            "turns": self._to_int(
                state.get("turn", 0)
            ),
        }

    @classmethod
    def _bounded_update(
        cls,
        current: Any,
        change: int,
    ) -> int:
        current = cls._to_int(current)

        return max(
            cls.MIN_VALUE,
            min(
                cls.MAX_VALUE,
                current + change,
            ),
        )

    @staticmethod
    def _to_int(value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0
