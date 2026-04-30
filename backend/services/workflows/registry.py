"""Workflow registry — single source of truth for available workflows."""
from __future__ import annotations

from .base import Workflow
from .civil_demand import CivilDemandWorkflow
from .fiscal_consultation import FiscalConsultationWorkflow
from .initial_analysis import InitialAnalysisWorkflow
from .jurisprudence_analysis import JurisprudenceAnalysisWorkflow


REGISTRY: dict[str, type[Workflow]] = {
    InitialAnalysisWorkflow.workflow_type: InitialAnalysisWorkflow,
    CivilDemandWorkflow.workflow_type: CivilDemandWorkflow,
    FiscalConsultationWorkflow.workflow_type: FiscalConsultationWorkflow,
    JurisprudenceAnalysisWorkflow.workflow_type: JurisprudenceAnalysisWorkflow,
}


def get_workflow(workflow_type: str) -> Workflow:
    cls = REGISTRY.get(workflow_type)
    if cls is None:
        raise ValueError(f"Unknown workflow_type: {workflow_type}")
    return cls()
