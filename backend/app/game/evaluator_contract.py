"""AI-04 Evaluator output contract based on the current MVP scoring rules."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ActionType = Literal[
    'strong_positive',
    'positive',
    'neutral',
    'negative',
    'critical_error',
    'recovery_action',
]

CriticalFlag = Literal[
    'HARD_CONSTRAINT_BREACH',
    'FALSE_FACT_ASSERTION',
    'UNAUTHORIZED_COMMITMENT',
    'PERSONAL_ATTACK',
    'THREAT_OR_COERCION',
    'CONFIDENTIALITY_BREACH',
    'MANDATORY_STEP_SKIPPED',
]


class ObservedFeature(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    code: str = Field(min_length=1, max_length=80, pattern=r'^[a-z][a-z0-9_]*$')
    evidence: str = Field(min_length=1, max_length=500)


class Observations(BaseModel):
    """Facts extracted from a player message before action classification."""

    model_config = ConfigDict(extra='forbid', strict=True)

    conversation_progress: Literal['backward', 'neutral', 'forward']
    features: list[ObservedFeature]


class ProfileFit(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    P: int = Field(ge=-2, le=2)
    A: int = Field(ge=-2, le=2)
    E: int = Field(ge=-2, le=2)
    I: int = Field(ge=-2, le=2)


class ProposedEvent(BaseModel):
    """Classification proposed by Evaluator; Game Engine owns state changes."""

    model_config = ConfigDict(extra='forbid', strict=True)

    action_type: ActionType
    critical_flags: list[CriticalFlag]

    @model_validator(mode='after')
    def validate_critical_flags(self):
        if (self.action_type == 'critical_error') != bool(self.critical_flags):
            raise ValueError('critical flags must match critical_error action')
        if len(set(self.critical_flags)) != len(self.critical_flags):
            raise ValueError('critical flags must be unique')
        return self


class Explanation(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)

    reason: str = Field(min_length=1, max_length=500)


class EvaluatorOutput(BaseModel):
    """Versioned observation, PAEI fit, proposed event and explanation."""

    model_config = ConfigDict(extra='forbid', strict=True)

    schema_version: Literal['ai04-v1']
    observations: Observations
    profile_fit: ProfileFit
    proposed_event: ProposedEvent
    explanation: Explanation

    def validate_evidence(self, player_message: str) -> None:
        """Reject observations that do not quote the evaluated player message."""
        if any(feature.evidence not in player_message for feature in self.observations.features):
            raise ValueError('observation evidence must quote the player message')
