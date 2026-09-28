"""Small, evidence-backed ledger kept separately from recent chat messages."""

from copy import deepcopy
from typing import Any


class TurnMemory:
    """Record quoted claims and mutually confirmed agreements after a full turn."""

    MAX_ITEMS = 20

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
