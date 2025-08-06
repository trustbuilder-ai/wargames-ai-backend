"""
This module defines the evaluation status and result models used in the backend.
It includes the EvalStatus enumeration for different evaluation states
and the EvalResult model for encapsulating the evaluation outcome.
"""

from enum import StrEnum
from typing import Optional
from pydantic import BaseModel


class EvalStatus(StrEnum):
    NOT_EVALUATED = "NOT_EVALUATED"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    ERRORED = "ERRORED"


class EvalResult(BaseModel):
    # this is what's sent to the user and wrapped in the openai
    # evaluation.
    reason: Optional[str] = None
    status: EvalStatus
    challenge_id: Optional[int] = None