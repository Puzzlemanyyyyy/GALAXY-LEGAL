"""Smoke tests for the workflow registry (no LLM calls)."""
from services.workflows import REGISTRY, get_workflow


EXPECTED = {"initial_analysis", "civil_demand", "fiscal_consultation", "jurisprudence_analysis"}


def test_registry_contains_phase2b_workflows():
    assert EXPECTED.issubset(set(REGISTRY.keys()))


def test_each_workflow_has_steps_and_assembler():
    for name in EXPECTED:
        wf = get_workflow(name)
        assert wf.steps, f"{name} has no steps"
        # Every step has a schema and a prompt builder callable.
        for step in wf.steps:
            assert step.name
            assert callable(step.user_prompt_builder)
            assert isinstance(step.output_schema, dict)
            assert step.output_schema.get("type") == "object"


def test_get_workflow_unknown():
    import pytest
    with pytest.raises(ValueError):
        get_workflow("does_not_exist")
