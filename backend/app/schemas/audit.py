from typing import Literal

from pydantic import BaseModel


class VerifyChainOk(BaseModel):
    status: Literal["ok"]


class VerifyChainBroken(BaseModel):
    broken_at: int
