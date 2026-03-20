"""Week 6/7 LangGraph workflow modules."""

from compliance_bot.graph.state import ComplianceAgentState

__all__ = [
    "ComplianceAgentState",
    "build_week5_workflow",
    "build_week6_workflow",
    "build_week7_workflow",
    "run_week5_comparison",
    "run_week6_comparison",
    "run_week5_query",
    "run_week6_query",
    "run_week7_query",
]


def __getattr__(name: str):
    if name in {"run_week5_comparison", "run_week6_comparison"}:
        from compliance_bot.graph.comparison import (
            run_week5_comparison,
            run_week6_comparison,
        )

        exports = {
            "run_week5_comparison": run_week5_comparison,
            "run_week6_comparison": run_week6_comparison,
        }
        return exports[name]
    if name in {
        "build_week5_workflow",
        "build_week6_workflow",
        "build_week7_workflow",
        "run_week5_query",
        "run_week6_query",
        "run_week7_query",
    }:
        from compliance_bot.graph.workflow import (
            build_week5_workflow,
            build_week6_workflow,
            build_week7_workflow,
            run_week5_query,
            run_week6_query,
            run_week7_query,
        )

        exports = {
            "build_week5_workflow": build_week5_workflow,
            "build_week6_workflow": build_week6_workflow,
            "build_week7_workflow": build_week7_workflow,
            "run_week5_query": run_week5_query,
            "run_week6_query": run_week6_query,
            "run_week7_query": run_week7_query,
        }
        return exports[name]
    raise AttributeError(name)
