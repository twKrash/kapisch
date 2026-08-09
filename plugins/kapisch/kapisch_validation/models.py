from __future__ import annotations

from dataclasses import dataclass

from .errors import ValidationError


@dataclass(frozen=True)
class Node:
    id: str
    sequence: int
    kind: str
    status: str
    depends_on: tuple[str, ...]
    paths: tuple[str, ...]
    review_scope: dict[str, object] | None
    raw: dict[str, object]


@dataclass(frozen=True)
class Manifest:
    version: int
    task_id: str
    base_revision: str
    policies: dict[str, object]
    nodes: tuple[Node, ...]
    path: str
    source_plan: str = ""


@dataclass(frozen=True)
class State:
    task_id: str
    current_revision: str
    workflow_status: str
    completed: tuple[str, ...]
    running: tuple[str, ...]
    ready: tuple[str, ...]
    blocked: tuple[str, ...]
    failed: tuple[str, ...]
    next_action: str
    raw: dict[str, object]
    path: str = ""


@dataclass(frozen=True)
class ParseResult:
    manifest: Manifest | None
    errors: tuple[ValidationError, ...]


@dataclass(frozen=True)
class ValidationResult:
    errors: tuple[ValidationError, ...]
