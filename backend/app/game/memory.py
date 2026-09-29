"""Small, evidence-backed ledger kept separately from recent chat messages."""

import json
from copy import deepcopy
from typing import Any


class TurnMemory:
    """Record quoted claims and mutually confirmed agreements after a full turn."""

    MAX_ITEMS = 20
    MAX_DIALOGUE_CHARS = 14_000
    MAX_EXCERPT_CHARS = 360

    @classmethod
    def for_prompt(
        cls,
        summary: dict[str, Any] | None,
        older_messages: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Keep older dialogue available after it leaves the short history window."""
        source = summary if isinstance(summary, dict) else {}
        facts = cls._items(source.get('revealed_facts'))
        agreements = cls._items(source.get('agreements'))
        result: dict[str, Any] = {
            'revealed_facts': facts,
            'agreements': agreements,
            'earlier_dialogue': [],
        }
        if isinstance(source.get('goal_state'), dict):
            result['goal_state'] = deepcopy(source['goal_state'])
        # Reserve space for dialogue while retaining the most recent structured facts.
        while cls._length(result) > 6_000:
            if len(facts) >= len(agreements) and facts:
                facts.pop(0)
            elif agreements:
                agreements.pop(0)
            else:
                break

        for row in reversed(older_messages):
            role = row.get('role')
            content = row.get('content')
            if role not in ('user', 'assistant') or not isinstance(content, str):
                continue
            excerpt = cls._excerpt(content)
            if not excerpt:
                continue
            entry = {
                'speaker': 'player' if role == 'user' else 'opponent',
                'text': excerpt,
            }
            proposed = [entry, *result['earlier_dialogue']]
            if cls._length({**result, 'earlier_dialogue': proposed}) > cls.MAX_DIALOGUE_CHARS:
                break
            result['earlier_dialogue'] = proposed
        return result

    @classmethod
    def _excerpt(cls, content: str) -> str:
        text = content.strip()
        if len(text) <= cls.MAX_EXCERPT_CHARS:
            return text
        return text[:240].rstrip() + ' … ' + text[-110:].lstrip()

    @staticmethod
    def _length(value: dict[str, Any]) -> int:
        return len(json.dumps(value, ensure_ascii=False, default=str))

    @classmethod
    def update(
        cls,
        *,
        state: dict[str, Any],
        player_message: str,
        opponent_message: str,
        evaluation: dict[str, Any],
        sequence_number: int,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        updated = deepcopy(state)
        raw = updated.get('memory')
        ledger = deepcopy(raw) if isinstance(raw, dict) else {}
        facts = cls._items(ledger.get('facts'))
        agreements = cls._items(ledger.get('agreements'))

        if evaluation.get('schema_version') == 'ai10-v1':
            features = (evaluation.get('observations') or {}).get('features') or []
            for feature in features:
                if not isinstance(feature, dict):
                    continue
                quote = feature.get('evidence')
                if not isinstance(quote, str) or quote not in player_message:
                    continue
                quote = quote.strip()[:500]
                if not quote:
                    continue
                if feature.get('code') == 'fact_statement':
                    cls._append(facts, {'text': quote, 'source': 'player_claim'})
                elif feature.get('code') == 'agreement_fixation' and cls._confirms(opponent_message):
                    cls._append(agreements, {'text': quote, 'source': 'mutual_confirmation'})

        ledger = {'facts': facts[-cls.MAX_ITEMS:], 'agreements': agreements[-cls.MAX_ITEMS:]}
        updated['memory'] = ledger
        summary = {
            'revealed_facts': ledger['facts'],
            'agreements': ledger['agreements'],
            'summarized_through_sequence': sequence_number,
        }
        return updated, summary

    @staticmethod
    def _items(value: Any) -> list[dict[str, str]]:
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, dict)
                and isinstance(item.get('text'), str)
                and isinstance(item.get('source'), str)]

    @staticmethod
    def _append(items: list[dict[str, str]], item: dict[str, str]) -> None:
        if item not in items:
            items.append(item)

    @staticmethod
    def _confirms(message: str) -> bool:
        normalized = message.strip().casefold()
        return normalized.startswith((
            'согласен', 'согласна', 'согласны', 'договорились', 'подтверждаю',
        ))
