from typing import List

from pydantic import BaseModel, Field


class AssetExplanationSchema(BaseModel):
    summary: str = Field(
        ..., description="A high-level summary of the asset's security posture."
    )
    risk_analysis: str = Field(
        ..., description="Detailed analysis of the asset's security risks."
    )
    priority_reasons: List[str] = Field(
        ..., description="Reasons why this asset should be prioritized for mitigation."
    )


class FindingExplanationSchema(BaseModel):
    summary: str = Field(..., description="A high-level summary of the finding.")
    impact: str = Field(
        ..., description="The potential impact of this finding on the organization."
    )
    priority: str = Field(..., description="The mitigation priority for this finding.")
    investigation_guidance: str = Field(
        ..., description="Guidance on how to investigate and remediate this finding."
    )


class ExecutiveSummarySchema(BaseModel):
    executive_summary: str = Field(
        ..., description="High-level organizational security posture summary."
    )
    top_risks: List[str] = Field(
        ..., description="Top risk areas identified across the scope."
    )
    notable_changes: List[str] = Field(
        ..., description="Notable security posture changes since the last analysis."
    )
