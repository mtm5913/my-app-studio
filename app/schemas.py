"""Explicit input and public output contracts exclude server-controlled fields."""

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SignupInput(BaseModel):
    """Only these two properties may arrive from a public signup."""

    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=3, max_length=32, strict=True)
    password: str = Field(min_length=15, max_length=128, strict=True)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        """One normalized identity; keep email ownership out of this small exercise."""
        normalized = value.strip().lower()
        if not re.fullmatch(r"[a-z0-9_]{3,32}", normalized):
            raise ValueError(
                "Use 3–32 letters, numbers, or underscores for your username."
            )
        return normalized


class LoginInput(BaseModel):
    """Bound credentials before performing an expensive password verification."""

    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=1, max_length=32, strict=True)
    password: str = Field(min_length=1, max_length=128, strict=True)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        """Use the same identity normalization as signup."""
        return value.strip().lower()


class PublicUser(BaseModel):
    """Never return a password hash or a session identifier."""

    id: str
    username: str
    role: str
