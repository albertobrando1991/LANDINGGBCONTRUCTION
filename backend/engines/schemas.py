from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


Severity = Literal["low", "medium", "high"]
FindingCategory = Literal[
    "light",
    "circulation",
    "plumbing",
    "structure",
    "layout",
    "norm",
    "measurement",
    "render",
    "other",
]
FloorplanMode = Literal["optimized_existing_state", "clean_defined_project", "verification_only"]


class ProfessionalFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: FindingCategory
    severity: Severity
    title: str
    evidence: str
    recommendation: str
    confidence: float = Field(ge=0, le=1)
    verification_required: bool = True
    disclaimer: str = "Da validare con tecnico abilitato e sopralluogo prima di qualsiasi intervento."


class OptimizationAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    priority: int = Field(ge=1, le=5)
    title: str
    rationale: str
    constraints: List[str] = Field(default_factory=list)
    expected_effect: str
    risk_note: str


class Floorplan2DBrief(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: FloorplanMode
    title: str
    drawing_intent: str
    constraints_respected: List[str] = Field(default_factory=list)
    drafting_requirements: List[str] = Field(default_factory=list)
    legend_items: List[str] = Field(default_factory=list)
    change_summary: List[str] = Field(default_factory=list)
    approval_checklist: List[str] = Field(default_factory=list)
    disclaimer: str


class RenderFidelityContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reference_required: bool = True
    reference_type: Literal["optimized_2d_plan", "clean_2d_plan", "uploaded_plan"] = "optimized_2d_plan"
    must_preserve: List[str] = Field(default_factory=list)
    must_not_add: List[str] = Field(default_factory=list)
    allowed_views: List[str] = Field(default_factory=list)
    negative_prompt: str
    fidelity_notes: List[str] = Field(default_factory=list)


class ProfessionalFloorplanPackage(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_name: Literal["gb-professional-floorplan-v1"] = Field(
        default="gb-professional-floorplan-v1",
        alias="schema",
    )
    mode: FloorplanMode
    plan_type: str
    confidence: float = Field(ge=0, le=1)
    summary: str
    technical_findings: List[ProfessionalFinding] = Field(default_factory=list)
    optimization_strategy: List[OptimizationAction] = Field(default_factory=list)
    floorplan_2d: Floorplan2DBrief
    render_contract: RenderFidelityContract
    unverifiable_elements: List[str] = Field(default_factory=list)
    quality: Dict[str, Any] = Field(default_factory=dict)
