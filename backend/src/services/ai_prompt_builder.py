import json
from typing import Any, Dict


class AIPromptBuilder:
    @classmethod
    def build_asset_prompt(cls, context: Dict[str, Any]) -> str:
        """Construct the prompt for explaining asset risks."""
        return (
            "You are an expert Cybersecurity AI Assistant. "
            "Analyze the provided asset context and "
            "generate a security posture explanation.\n"
            "Return a JSON object conforming exactly to the following structure:\n"
            "{\n"
            '  "summary": "High-level summary of the asset\'s posture.",\n'
            '  "risk_analysis": "Detailed analysis of the asset\'s risks.",\n'
            '  "priority_reasons": ["Reason 1", "Reason 2"]\n'
            "}\n\n"
            "CRITICAL REQUIREMENT: Output raw JSON only. "
            "Do not include markdown code block formatting\n"
            "(e.g., do not wrap in ```json or ```), "
            "conversational text, or prefixes.\n\n"
            "CRITICAL CONSTRAINT: You must act strictly as an explanation layer "
            "for the deterministic recommendations provided in the context under "
            "the 'recommendations' key. Do not generate, suggest, or speculate "
            "on any custom remediation actions, priorities, or posturing adjustments "
            "that are not explicitly present in the recommendations context. "
            "Your priority reasons and risk analysis must strictly align with the "
            "deterministic recommendation priorities and supporting factors.\n\n"
            f"Context:\n{json.dumps(context, indent=2)}"
        )

    @classmethod
    def build_finding_prompt(cls, context: Dict[str, Any]) -> str:
        """Construct the prompt for explaining finding impact and remediation."""
        return (
            "You are an expert Cybersecurity AI Assistant. "
            "Analyze the provided finding context and "
            "explain its impact and remediation guidance.\n"
            "Return a JSON object conforming exactly to the following structure:\n"
            "{\n"
            '  "summary": "High-level summary of the finding.",\n'
            '  "impact": "Potential impact of this finding.",\n'
            '  "priority": "Mitigation priority level '
            '(e.g., Immediate, High, Medium, Low).",\n'
            '  "investigation_guidance": "Step-by-step guidance '
            'on how to investigate and remediate this finding."\n'
            "}\n\n"
            "CRITICAL REQUIREMENT: Output raw JSON only. "
            "Do not include markdown code block formatting\n"
            "(e.g., do not wrap in ```json or ```), "
            "conversational text, or prefixes.\n\n"
            "CRITICAL CONSTRAINT: You must act strictly as an explanation layer "
            "for the deterministic recommendations provided in the context under "
            "the 'recommendations' key. Do not suggest or generate custom "
            "remediation actions or prioritize them differently. Align your summary, "
            "impact, priority, and investigation guidance strictly with the "
            "deterministic recommendations and guidance provided in the context.\n\n"
            f"Context:\n{json.dumps(context, indent=2)}"
        )

    @classmethod
    def build_executive_prompt(cls, context: Dict[str, Any]) -> str:
        """Construct prompt for organization-wide executive summary."""
        return (
            "You are an expert Cybersecurity AI Assistant. "
            "Analyze the organization-wide context and "
            "generate a high-level executive posture report.\n"
            "Return a JSON object conforming exactly to the following structure:\n"
            "{\n"
            '  "executive_summary": "High-level organizational '
            'security posture summary.",\n'
            '  "top_risks": ["Top Risk 1", "Top Risk 2"],\n'
            '  "notable_changes": ["Notable posturing change 1", "Notable change 2"]\n'
            "}\n\n"
            "CRITICAL REQUIREMENT: Output raw JSON only. "
            "Do not include markdown code block formatting\n"
            "(e.g., do not wrap in ```json or ```), "
            "conversational text, or prefixes.\n\n"
            "CRITICAL CONSTRAINT: You must base your analysis, risks, and changes "
            "strictly on the deterministic priority rankings provided in the context "
            "under the 'priorities' key. Do not generate, suggest, or speculate "
            "on any risk ratings, priority metrics, or rankings that are not "
            "explicitly present in the context priorities.\n\n"
            f"Context:\n{json.dumps(context, indent=2)}"
        )
