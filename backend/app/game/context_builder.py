"""Build bounded, role-specific context from a saved game-session snapshot."""

from copy import deepcopy
from typing import Any


class ContextBuilder:
    def __init__(
        self,
        *,
        max_history_messages: int = 12,
        max_history_chars: int = 12_000,
    ) -> None:
        if max_history_messages < 1 or max_history_chars < 1:
            raise ValueError('history limits must be positive')
        self.max_history_messages = max_history_messages
        self.max_history_chars = max_history_chars

    def build(
        self,
        *,
        session: dict[str, Any],
        mission: dict[str, Any] | None = None,
        character: dict[str, Any] | None = None,
        paei_profile: dict[str, Any] | None = None,
        difficulty_profile: dict[str, Any] | None = None,
        rules: dict[str, Any] | None = None,
        messages: list[dict[str, Any]] | None = None,
        memory_summary: str | None = None,
        custom_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Return private AI context; callers must not serialize it to frontend."""
        raw_state = session.get('state')
        state = raw_state if isinstance(raw_state, dict) else {}
        mission_data = deepcopy(mission or {})
        character_data = deepcopy(character or {})

        return {
            'session': {
                'id': session.get('id'),
                'mode': session.get('mode'),
                'status': session.get('status'),
                'turn': state.get('turn', 0),
            },
            'mission': mission_data,
            'character': character_data,
            'paei_profile': deepcopy(paei_profile or {}),
            'difficulty_profile': deepcopy(difficulty_profile or {}),
            'rules': deepcopy(rules or {}),
            'interests': self._collect_interests(mission_data, character_data),
            'state': {
                'turn': state.get('turn', 0),
                'contact': state.get('contact', 0),
                'tension': state.get('tension', 0),
                'progress': state.get('progress', 0),
                'critical_errors': state.get('critical_errors', 0),
                'score': state.get('score', 0),
            },
            'memory': memory_summary or '',
            'history': self._bounded_history(messages or []),
            'custom_context': deepcopy(custom_context or {}),
        }

    @staticmethod
    def build_frontend_context(*, game_context: dict[str, Any]) -> dict[str, Any]:
        """Project an explicit public allowlist; never copy private AI fields."""
        session = game_context.get('session') or {}
        mission = game_context.get('mission') or {}
        character = game_context.get('character') or {}
        raw_mission_context = mission.get('context')
        mission_context = raw_mission_context if isinstance(raw_mission_context, dict) else {}

        return {
            'session': {
                key: session.get(key) for key in ('id', 'mode', 'status', 'turn')
            },
            'mission': {
                'id': mission.get('id'),
                'title': mission.get('title'),
                'task': mission.get('task'),
                'public_context': mission_context.get('public_context'),
            },
            'character': {
                key: character.get(key) for key in ('id', 'name', 'role_title')
            },
        }

    def build_evaluator_context(
        self,
        *,
        game_context: dict[str, Any],
        player_message: str,
    ) -> dict[str, Any]:
        return {
            'game': deepcopy(game_context),
            'player_message': player_message,
        }

    def build_opponent_context(
        self,
        *,
        game_context: dict[str, Any],
        evaluation: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            'game': deepcopy(game_context),
            'evaluation': deepcopy(evaluation),
        }

    def _bounded_history(self, messages: list[dict[str, Any]]) -> list[dict[str, str]]:
        eligible = [
            {'role': row['role'], 'content': row['content']}
            for row in messages
            if row.get('role') in ('user', 'assistant')
            and isinstance(row.get('content'), str)
            and row['content']
            and row.get('processing_status', 'completed') == 'completed'
        ]

        selected: list[dict[str, str]] = []
        remaining = self.max_history_chars
        for row in reversed(eligible[-self.max_history_messages:]):
            content = row['content']
            if len(content) > remaining:
                if selected:
                    break
                content = ('…' + content[-(remaining - 1):]) if remaining > 1 else content[-1:]
            selected.append({'role': row['role'], 'content': content})
            remaining -= len(content)
            if remaining == 0:
                break

        return list(reversed(selected))

    @staticmethod
    def _collect_interests(
        mission: dict[str, Any], character: dict[str, Any],
    ) -> list[str]:
        """Use only explicitly stored interests; never infer them from prose."""
        raw_mission_context = mission.get('context')
        mission_context = raw_mission_context if isinstance(raw_mission_context, dict) else {}
        raw_character_behavior = character.get('behavior')
        character_behavior = raw_character_behavior if isinstance(raw_character_behavior, dict) else {}
        sources = (
            mission_context.get('npc_interests'),
            mission_context.get('interests'),
            character_behavior.get('interests'),
        )
        interests: list[str] = []
        for source in sources:
            if isinstance(source, str):
                source = [source]
            if isinstance(source, list):
                for item in source:
                    if isinstance(item, str):
                        interest = item.strip()
                        if interest and interest not in interests:
                            interests.append(interest)
        return interests
