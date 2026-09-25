from typing import Any


class Scoring:


    def calculate(
        self,
        *,
        state: dict[str, Any],
        evaluation: dict[str, Any] | None = None,
    ) -> dict[str, Any]:


        contact = self._to_int(
            state.get("contact", 0)
        )

        progress = self._to_int(
            state.get("progress", 0)
        )

        tension = self._to_int(
            state.get("tension", 0)
        )

        critical_errors = self._to_int(
            state.get("critical_errors", 0)
        )

        quality = 0.0

        if evaluation:
            try:
                quality = float(
                    evaluation.get("quality", 0.0)
                )
            except (TypeError, ValueError):
                quality = 0.0

        quality = max(
            0.0,
            min(1.0, quality),
        )

        # Базовые очки
        base_score = (
            progress * 2
            + contact
            + int(quality * 20)
        )

        # Штраф за напряжение
        tension_penalty = tension // 5

        # Штраф за критические ошибки
        critical_error_penalty = (
            critical_errors * 15
        )

        total_score = max(
            0,
            base_score
            - tension_penalty
            - critical_error_penalty,
        )

        return {
            "score": total_score,
            "base_score": base_score,
            "tension_penalty": tension_penalty,
            "critical_error_penalty": critical_error_penalty,
            "quality_bonus": int(
                quality * 20
            ),
        }

    def calculate_final(
        self,
        *,
        state: dict[str, Any],
    ) -> dict[str, Any]:

        contact = self._to_int(
            state.get("contact", 0)
        )

        progress = self._to_int(
            state.get("progress", 0)
        )

        tension = self._to_int(
            state.get("tension", 0)
        )

        critical_errors = self._to_int(
            state.get("critical_errors", 0)
        )

        score = (
            progress * 2
            + contact
            - tension // 5
            - critical_errors * 15
        )

        score = max(0, score)

        return {
            "score": score,
            "progress": progress,
            "contact": contact,
            "tension": tension,
            "critical_errors": critical_errors,
        }

    @staticmethod
    def _to_int(value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0