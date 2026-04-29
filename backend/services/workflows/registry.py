"""Workflow registry — single source of truth for available workflows."""
from __future__ import annotations

from .base import Workflow
from .initial_analysis import InitialAnalysisWorkflow


REGISTRY: dict[str, type[Workflow]] = {
    InitialAnalysisWorkflow.workflow_type: InitialAnalysisWorkflow,
}


def get_workflow(workflow_type: str) -> Workflow:
    cls = REGISTRY.get(workflow_type)
    if cls is None:
        raise ValueError(f"Unknown workflow_type: {workflow_type}")
    return cls()
