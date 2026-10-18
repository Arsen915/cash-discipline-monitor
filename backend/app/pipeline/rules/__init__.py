"""Правила выявления нарушений. Каждое правило — отдельный модуль, их легко добавлять."""

from __future__ import annotations

from .base import Event, EvidenceRef, Rule, RuleContext
from .camera import CameraObstructionRule
from .catalog import CATALOG, ViolationType, catalog_as_dict
from .intrusion import UnauthorizedPersonRule
from .objects import MobilePhoneRule, PersonalBelongingsRule
from .workplace import CashUnattendedRule, WorkplaceAbandonedRule, WorkplaceLeftRule


def default_rules() -> list[Rule]:
    return [
        CameraObstructionRule(),
        WorkplaceAbandonedRule(),
        WorkplaceLeftRule(),
        CashUnattendedRule(),
        UnauthorizedPersonRule(),
        MobilePhoneRule(),
        PersonalBelongingsRule(),
    ]


__all__ = [
    "CATALOG",
    "Event",
    "EvidenceRef",
    "Rule",
    "RuleContext",
    "ViolationType",
    "catalog_as_dict",
    "default_rules",
]
