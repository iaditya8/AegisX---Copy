import json
from typing import Any, Dict, List

from src.services.finding_severity_rules import FindingSeverityRules


class FindingNormalizationService:
    @staticmethod
    def normalize_nuclei(raw_output: str) -> List[Dict[str, Any]]:
        """Parse raw output of nuclei (newline-separated JSON) and transform it

        into structured finding dictionaries.
        """
        results = []
        if not raw_output:
            return results

        lines = raw_output.strip().split("\n")
        for line in lines:
            line = line.strip()
            if not line:
                continue

            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue

            # Core fields
            template_id = data.get("template-id") or ""
            info = data.get("info", {}) or {}
            name = info.get("name") or template_id or "Unknown Finding"
            raw_severity = info.get("severity") or "info"
            severity = FindingSeverityRules.normalize_severity(raw_severity)
            description = info.get("description") or ""

            # Extraction details
            host = data.get("host") or ""
            matched_at = data.get("matched-at") or ""
            matcher_name = data.get("matcher-name") or ""

            # Standardize matcher value which can be string, int or list
            raw_m_value = data.get("matcher-value") or data.get("matcher-status")
            if raw_m_value is None:
                matcher_value = ""
            elif isinstance(raw_m_value, list):
                matcher_value = ",".join(str(x) for x in raw_m_value)
            else:
                matcher_value = str(raw_m_value)

            curl_command = data.get("curl-command") or ""
            raw_req = data.get("request") or ""
            raw_res = data.get("response") or ""
            evidence_type = data.get("type") or "vulnerability"

            # Build metadata_json as required for findings table
            # Change 7: CVE enrichment hook
            cves = info.get("classification", {}).get("cve-id", [])
            if isinstance(cves, str):
                cves = [cves]
            elif not isinstance(cves, list):
                cves = []

            cvss = info.get("classification", {}).get("cvss-score")
            if cvss is not None:
                try:
                    cvss = float(cvss)
                except ValueError:
                    cvss = None

            epss = info.get("classification", {}).get("epss-score")
            if epss is not None:
                try:
                    epss = float(epss)
                except ValueError:
                    epss = None

            metadata_json = {
                "cves": cves,
                "cvss": cvss,
                "epss": epss,
                "host": host,
                "matched_at": matched_at,
                "curl_command": curl_command,
            }

            # Standard structured output as requested
            results.append(
                {
                    "finding": {
                        "title": name,
                        "description": description,
                        "severity": severity,
                        "template_id": template_id,
                        "template_name": name,
                        "source_plugin": "NucleiPlugin",
                        "metadata_json": {
                            "cves": cves,
                            "cvss": cvss,
                            "epss": epss,
                        },
                    },
                    "evidence": {
                        "evidence_type": evidence_type,
                        "raw_request": raw_req,
                        "raw_response": raw_res,
                        "matched_at": matched_at,
                        "matcher_name": matcher_name,
                        "matcher_value": matcher_value,
                        "metadata_json": metadata_json,
                    },
                }
            )

        return results
