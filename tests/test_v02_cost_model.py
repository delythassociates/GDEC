"""
Tests for Cost Model and topological prediction (v0.2).
"""

from gdec.core.cost_model import CostModel


def test_topological_cost_model():
    model = CostModel()

    # Low density (isolated elements) -> higher DOFs per element
    dofs_isolated = model.predict_additional_dofs(marked_count=2, total_elements=200)
    # High density (clustered elements sharing edges) -> lower DOFs per element
    dofs_clustered = model.predict_additional_dofs(marked_count=100, total_elements=200)

    rate_isolated = dofs_isolated / 2.0
    rate_clustered = dofs_clustered / 100.0

    assert rate_isolated > rate_clustered

    # Update with observed data and verify error tracking
    model.update(iteration=1, marked_count=2, observed_delta=12, observed_time=0.01, total_elements=200)
    assert len(model.history) == 1
    assert model.history[0].prediction_error >= 0
    assert model.mean_absolute_error_pct >= 0.0
