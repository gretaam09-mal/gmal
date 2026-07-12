"""F9's plain email naming affected memos, and F1's invite emails, share
this one interface. Mirrors the fixture-provider pattern used for
AI-touching services: every environment but a hypothetical future live
one uses StubEmailProvider, which just records what would have been
sent — see the confirmed F9 scope decision (fixture sweep, stub email).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class EmailMessage:
    to: str
    subject: str
    body: str


class EmailProvider(Protocol):
    def send(self, message: EmailMessage) -> None: ...


@dataclass
class StubEmailProvider:
    sent: list[EmailMessage] = field(default_factory=list)

    def send(self, message: EmailMessage) -> None:
        self.sent.append(message)
