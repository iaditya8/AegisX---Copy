import json
import xml.etree.ElementTree as ET
from typing import Any, Dict, List

from src.services.service_confidence_rules import ServiceConfidenceRules


class ServiceNormalizationService:
    """Normalizes raw port and service discovery tool outputs into standardized formats."""

    @staticmethod
    def normalize_naabu(raw_output: str) -> List[Dict[str, Any]]:
        """Parses naabu standard output.
        Expects raw_output to be a JSON string dictionary mapping target -> naabu text output.
        Naabu text output lines are typically: `ip:port`
        """
        results = []
        try:
            target_map = json.loads(raw_output)
            for target, text_output in target_map.items():
                if not text_output:
                    continue
                for line in text_output.strip().split("\n"):
                    line = line.strip()
                    if not line:
                        continue

                    # Basic parsing for naabu output like "1.2.3.4:443" or "example.com:80"
                    parts = line.split(":")
                    if len(parts) >= 2:
                        host_or_ip = ":".join(parts[:-1])
                        port = parts[-1]

                        try:
                            port_num = int(port)
                        except ValueError:
                            continue

                        results.append(
                            {
                                "target": target,
                                "host_or_ip": host_or_ip,
                                "port": port_num,
                                "protocol": "tcp",  # Naabu defaults to tcp
                                "state": "open",
                                "confidence": ServiceConfidenceRules.get_port_confidence(),
                                "evidence": {"raw_line": line},
                            }
                        )
        except Exception:
            pass

        return results

    @staticmethod
    def normalize_nmap(raw_output: str) -> List[Dict[str, Any]]:
        """Parses nmap XML output (-oX).
        Expects raw_output to be a JSON string dictionary mapping target -> nmap XML output.
        """
        results = []
        try:
            target_map = json.loads(raw_output)
            for target, xml_content in target_map.items():
                if not xml_content:
                    continue

                try:
                    root = ET.fromstring(xml_content)

                    for host in root.findall("host"):
                        # Extract addresses
                        addresses = []
                        for addr in host.findall("address"):
                            addr_type = addr.get("addrtype")
                            if addr_type in ("ipv4", "ipv6", "mac"):
                                addresses.append(addr.get("addr"))

                        # Extract ports and services
                        ports_elem = host.find("ports")
                        if ports_elem is not None:
                            for port_elem in ports_elem.findall("port"):
                                protocol = port_elem.get("protocol", "tcp")
                                port_id = port_elem.get("portid")
                                if not port_id:
                                    continue

                                state_elem = port_elem.find("state")
                                state = (
                                    state_elem.get("state")
                                    if state_elem is not None
                                    else "unknown"
                                )

                                service_elem = port_elem.find("service")
                                service_data = {}
                                if service_elem is not None:
                                    service_data = {
                                        "name": service_elem.get("name", "unknown"),
                                        "product": service_elem.get("product"),
                                        "version": service_elem.get("version"),
                                        "extrainfo": service_elem.get("extrainfo"),
                                    }

                                has_version = bool(service_data.get("version"))
                                has_product = bool(service_data.get("product"))
                                has_extrainfo = bool(service_data.get("extrainfo"))

                                confidence = (
                                    ServiceConfidenceRules.get_service_confidence(
                                        has_version=has_version,
                                        has_product=has_product,
                                        has_banner=has_extrainfo,
                                        service_name=service_data.get("name"),
                                    )
                                )

                                results.append(
                                    {
                                        "target": target,
                                        "addresses": addresses,
                                        "port": int(port_id),
                                        "protocol": protocol,
                                        "state": state,
                                        "service": service_data.get("name"),
                                        "product": service_data.get("product"),
                                        "version": service_data.get("version"),
                                        "banner": service_data.get("extrainfo"),
                                        "confidence": confidence,
                                        "evidence": {
                                            "xml_node": ET.tostring(
                                                port_elem, encoding="unicode"
                                            )
                                        },
                                    }
                                )
                except ET.ParseError:
                    pass
        except Exception:
            pass

        return results
