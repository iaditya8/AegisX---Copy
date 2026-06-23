from typing import List


class DiscoveryNormalizationService:
    @staticmethod
    def normalize(tool_name: str, raw_output: str) -> List[dict]:
        """Normalize raw output of discovery tools into standardized format."""
        normalized_assets = []
        if not raw_output:
            return normalized_assets

        tool_clean = tool_name.lower().replace("plugin", "")

        # Default confidence map
        CONFIDENCE_MAP = {
            "subfinder": 0.9,
            "amass": 0.85,
            "assetfinder": 0.75,
            "theharvester": 0.7,
        }
        base_confidence = CONFIDENCE_MAP.get(tool_clean, 0.5)

        lines = raw_output.splitlines()

        if tool_clean == "theharvester":
            section = None
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                if "[*] Emails found" in line:
                    section = "emails"
                    continue
                elif "[*] Hosts found" in line:
                    section = "hosts"
                    continue
                elif "[*] IPs found" in line:
                    section = "ips"
                    continue
                elif (
                    line.startswith("[*]")
                    or line.startswith("[-]")
                    or line.startswith("[+]")
                ):
                    section = None
                    continue

                if section == "emails":
                    if "@" in line:
                        normalized_assets.append(
                            {
                                "asset_type": "email",
                                "value": line.lower(),
                                "source_plugin": tool_name,
                                "confidence": 0.6,  # email confidence
                                "metadata": {"raw_value": line},
                            }
                        )
                elif section == "hosts":
                    if ":" in line:
                        parts = line.split(":", 1)
                        host_val = parts[0].strip()
                        ip_val = parts[1].strip()
                        if host_val:
                            normalized_assets.append(
                                {
                                    "asset_type": "hostname",
                                    "value": host_val.lower(),
                                    "source_plugin": tool_name,
                                    "confidence": 0.8,
                                    "metadata": {"raw_value": line},
                                }
                            )
                        if ip_val:
                            normalized_assets.append(
                                {
                                    "asset_type": "ip",
                                    "value": ip_val,
                                    "source_plugin": tool_name,
                                    "confidence": 0.9,
                                    "metadata": {"raw_value": line},
                                }
                            )
                    else:
                        normalized_assets.append(
                            {
                                "asset_type": "hostname",
                                "value": line.lower(),
                                "source_plugin": tool_name,
                                "confidence": 0.8,
                                "metadata": {"raw_value": line},
                            }
                        )
                elif section == "ips":
                    normalized_assets.append(
                        {
                            "asset_type": "ip",
                            "value": line,
                            "source_plugin": tool_name,
                            "confidence": 0.9,
                            "metadata": {"raw_value": line},
                        }
                    )
        else:
            # subfinder, amass, assetfinder: plain subdomains one per line
            for line in lines:
                val = line.strip()
                if not val:
                    continue
                # Determine type: subdomain vs domain vs hostname
                # Simple rule: if it contains multiple dots, it's subdomain, else domain
                asset_type = "subdomain"
                if val.count(".") == 1:
                    asset_type = "domain"
                elif val.count(".") == 0:
                    asset_type = "hostname"

                normalized_assets.append(
                    {
                        "asset_type": asset_type,
                        "value": val.lower(),
                        "source_plugin": tool_name,
                        "confidence": base_confidence,
                        "metadata": {"raw_value": val},
                    }
                )

        return normalized_assets
