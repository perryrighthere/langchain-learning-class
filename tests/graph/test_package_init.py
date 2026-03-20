"""Import behavior tests for compliance_bot.graph package."""

from __future__ import annotations


def test_graph_package_exposes_exports_without_eager_workflow_import() -> None:
    import compliance_bot.graph as graph_pkg

    assert graph_pkg.ComplianceAgentState is not None
    assert callable(graph_pkg.run_week6_query)
    assert callable(graph_pkg.build_week6_workflow)
