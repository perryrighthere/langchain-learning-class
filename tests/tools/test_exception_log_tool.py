"""Tests for the Week 6 exception-log tool."""

from __future__ import annotations

from compliance_bot.schemas.tools import (
    ExceptionLogLookupInput,
    ExceptionLogRecord,
)
from compliance_bot.tools.exception_log_tool import lookup_exception_log


def _records() -> list[ExceptionLogRecord]:
    return [
        ExceptionLogRecord(
            exception_id="exc-vendor-001",
            jurisdiction="eu",
            policy_scope="vendor",
            status="open",
            owner="compliance-ops",
            summary="Vendor onboarding exception requires legal review before approval.",
        ),
        ExceptionLogRecord(
            exception_id="exc-expense-002",
            jurisdiction="us",
            policy_scope="expense",
            status="closed",
            owner="finance-controls",
            summary="Travel expense exception was resolved after director approval.",
        ),
    ]


def test_exception_log_lookup_flags_open_exception_for_review() -> None:
    result = lookup_exception_log(
        _records(),
        ExceptionLogLookupInput(
            question="Can we approve a vendor exception in the EU?",
            jurisdiction="EU",
            policy_scope=["vendor"],
        ),
    )

    assert result.resolved is False
    assert result.requires_human_review is True
    assert [record.exception_id for record in result.matching_records] == ["exc-vendor-001"]


def test_exception_log_lookup_stays_resolved_for_closed_records() -> None:
    result = lookup_exception_log(
        _records(),
        ExceptionLogLookupInput(
            question="Was there an expense exception for travel receipts?",
            jurisdiction="US",
            policy_scope=["expense"],
        ),
    )

    assert result.resolved is True
    assert result.requires_human_review is False
    assert [record.exception_id for record in result.matching_records] == ["exc-expense-002"]
