import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple

from sqlalchemy.future import select
from src.infrastructure.database.models import (
    Asset,
    Finding,
    ThreatIntelIOC,
    PurpleTeamValidation,
    CorrelationRule,
    CorrelationRuleMatch,
)
from src.services.correlation_rule_engine import CorrelationRuleEngine
from src.services.correlation_aggregator_service import CorrelationAggregatorService
from src.services.workflow_event_service import WorkflowEventService
from src.core.tenant import require_current_tenant_id


class CorrelationEventConsumer:
    @classmethod
    async def build_context(cls, db, asset_id: uuid.UUID) -> Dict[str, Any]:
        """Build a comprehensive signal context for an asset to evaluate rules."""
        context = {
            "finding.cve_match": [],
            "asset.exposure_level": 0.5,
            "purple_team.validation_status": "PASSED",
            "threat.ioc_cves": []
        }

        # 1. Load Asset
        q_asset = select(Asset).filter(Asset.id == asset_id)
        res_asset = await db.execute(q_asset)
        asset = res_asset.scalar_one_or_none()
        if asset:
            if asset.metadata_json:
                context["asset.exposure_level"] = float(asset.metadata_json.get("exposure_level", 0.5))

        # 2. Load Findings & CVEs
        q_findings = select(Finding).filter(Finding.asset_id == asset_id, Finding.status == "open")
        res_findings = await db.execute(q_findings)
        findings = res_findings.scalars().all()
        cves = []
        for f in findings:
            if f.metadata_json and "cves" in f.metadata_json:
                cves.extend(f.metadata_json["cves"])
        context["finding.cve_match"] = list(set(cves))

        # 3. Load active Threat Intel IOCs
        try:
            # Check if ThreatIntelIOC is mapped in DB (if the table exists in models.py)
            # Legacy ThreatIntelIOC might be stored or we can check the db
            q_ioc = select(ThreatIntelIOC).filter(ThreatIntelIOC.is_deleted == False)
            res_ioc = await db.execute(q_ioc)
            iocs = res_ioc.scalars().all()
            ioc_cves = []
            for ioc in iocs:
                if ioc.tags:
                    for tag in ioc.tags:
                        if tag.upper().startswith("CVE-"):
                            ioc_cves.append(tag)
            context["threat.ioc_cves"] = list(set(ioc_cves))
        except Exception:
            pass

        # 4. Load validations & check for failures
        try:
            q_val = select(PurpleTeamValidation).order_by(PurpleTeamValidation.created_at.desc())
            res_val = await db.execute(q_val)
            validations = res_val.scalars().all()
            # If any validation failed, set status
            if any(v.validation_status == "FAILED" for v in validations):
                context["purple_team.validation_status"] = "FAILED"
        except Exception:
            pass

        return context

    @classmethod
    async def consume_event(cls, db, event_type: str, payload: dict) -> None:
        """Process a domain event and run the correlation pipeline."""
        tenant_id = require_current_tenant_id()

        # 1. Resolve Asset ID from the incoming event payload
        asset_id_str = payload.get("asset_id")
        if not asset_id_str:
            # Fallback if finding_id or alert_id is provided
            finding_id_str = payload.get("finding_id")
            if finding_id_str:
                q_find = select(Finding).filter(Finding.id == uuid.UUID(finding_id_str))
                res_find = await db.execute(q_find)
                finding = res_find.scalar_one_or_none()
                if finding:
                    asset_id_str = str(finding.asset_id)

        if not asset_id_str:
            return

        asset_id = uuid.UUID(asset_id_str)

        # 2. Build Context
        context = await cls.build_context(db, asset_id)

        # 3. Fetch Active Rules
        q_rules = select(CorrelationRule).filter(
            CorrelationRule.tenant_id == tenant_id,
            CorrelationRule.status == "active"
        )
        res_rules = await db.execute(q_rules)
        rules = list(res_rules.scalars().all())

        # 4. Evaluate Rules
        matched_rules = CorrelationRuleEngine.evaluate_rules(rules, context)
        if not matched_rules:
            return

        # 5. Extract Contributing Signals
        signals: List[Tuple[str, uuid.UUID]] = []
        finding_id_str = payload.get("finding_id")
        if finding_id_str:
            signals.append(("finding", uuid.UUID(finding_id_str)))
        alert_id_str = payload.get("alert_id")
        if alert_id_str:
            signals.append(("alert", uuid.UUID(alert_id_str)))
        ioc_id_str = payload.get("ioc_id")
        if ioc_id_str:
            signals.append(("ioc", uuid.UUID(ioc_id_str)))
        validation_id_str = payload.get("validation_id")
        if validation_id_str:
            signals.append(("validation", uuid.UUID(validation_id_str)))

        # Default fallback to add at least one signal context
        if not signals and finding_id_str is None and alert_id_str is None:
            # Add all open findings for the asset
            q_findings = select(Finding).filter(Finding.asset_id == asset_id, Finding.status == "open")
            res_findings = await db.execute(q_findings)
            open_findings = res_findings.scalars().all()
            for f in open_findings:
                signals.append(("finding", f.id))

        if not signals:
            return

        # 6. Aggregate & Upsert Correlation Cluster
        cluster = await CorrelationAggregatorService.aggregate_and_upsert(
            db=db,
            asset_id=asset_id,
            signals=signals
        )

        # 7. Persist Rule Matches
        for rule in matched_rules:
            # Check if this rule match already exists for the cluster
            q_match = select(CorrelationRuleMatch).filter(
                CorrelationRuleMatch.rule_id == rule.id,
                CorrelationRuleMatch.cluster_id == cluster.id,
                CorrelationRuleMatch.rule_version_used == rule.rule_version
            )
            res_match = await db.execute(q_match)
            if not res_match.scalar_one_or_none():
                match_record = CorrelationRuleMatch(
                    id=uuid.uuid4(),
                    tenant_id=tenant_id,
                    rule_id=rule.id,
                    rule_version_used=rule.rule_version,
                    cluster_id=cluster.id,
                    confidence=1.0,  # default max confidence
                    evidence_json={
                        "context_snapshot": context,
                        "matched_signals": [f"{s[0]}:{str(s[1])}" for s in signals]
                    },
                    matched_at=datetime.now(timezone.utc)
                )
                db.add(match_record)

        # 8. Emit Outbox Event (Atomic, transaction-neutral)
        await WorkflowEventService.emit_event(
            db=db,
            event_type="correlation.cluster_created",
            correlation_id=cluster.id,
            payload={
                "cluster_id": str(cluster.id),
                "asset_id": str(asset_id),
                "unified_score": cluster.unified_score,
                "status": cluster.status,
            }
        )

        # 9. Automate Incident bridge if score crosses critical threshold (e.g. >= 8.0)
        if cluster.unified_score >= 8.0 and not cluster.associated_incident_id:
            from src.services.correlation_incident_bridge import CorrelationIncidentBridge
            await CorrelationIncidentBridge.escalate_cluster(
                db=db,
                cluster_id=cluster.id,
                title=f"Critical Security Incident on Asset: {str(asset_id)[:8]}",
                description=f"Unified score {cluster.unified_score:.2f} crossed escalation threshold. Correlated signals: {[s[0] for s in signals]}"
            )

        await db.flush()
