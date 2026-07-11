import hashlib
import uuid
from datetime import datetime, timezone
from typing import List, Tuple, Dict, Any

from sqlalchemy.future import select
from src.infrastructure.database.models import (
    Asset,
    Finding,
    RiskAcceptance,
    CorrelationCluster,
    CorrelationClusterSignal,
)
from src.services.unified_security_intelligence_fabric_service import UnifiedSecurityIntelligenceFabricService


class CorrelationAggregatorService:
    @classmethod
    def compute_fingerprint(cls, asset_id: uuid.UUID, signals: List[Tuple[str, uuid.UUID]]) -> str:
        """Compute SHA-256 fingerprint for a combination of asset and sorted signals."""
        sorted_signals = sorted(signals, key=lambda x: (x[0], str(x[1])))
        raw_str = f"{str(asset_id)}:" + ",".join(f"{sig_type}:{str(sig_id)}" for sig_type, sig_id in sorted_signals)
        return hashlib.sha256(raw_str.encode("utf-8")).hexdigest()

    @classmethod
    async def calculate_score(
        cls,
        db,
        asset_id: uuid.UUID,
        findings: List[Finding],
        signals: List[Tuple[str, uuid.UUID]]
    ) -> Tuple[float, Dict[str, float]]:
        """
        Calculate unified priority score:
        S = w_asset * C_asset + w_finding * max(CVSS) + w_fabric * F_confidence - w_risk * R_accepted
        """
        # 1. Asset Criticality (0 to 10)
        q_asset = select(Asset).filter(Asset.id == asset_id)
        res_asset = await db.execute(q_asset)
        asset = res_asset.scalar_one_or_none()
        c_asset = 5.0  # default
        if asset and asset.metadata_json:
            c_asset = float(asset.metadata_json.get("criticality", 5.0))

        # 2. Max CVSS (0 to 10)
        max_cvss = 0.0
        for f in findings:
            cvss = f.metadata_json.get("cvss") if f.metadata_json else None
            if cvss is not None:
                max_cvss = max(max_cvss, float(cvss))
            else:
                # Severity fallback
                sev_map = {"critical": 10.0, "high": 8.0, "medium": 5.0, "low": 2.0}
                max_cvss = max(max_cvss, sev_map.get(str(f.severity).lower(), 0.0))

        # 3. Fabric Confidence (0 to 1)
        f_confidence = 0.5  # default fallback
        try:
            nodes = UnifiedSecurityIntelligenceFabricService.get_all_fabric_nodes()
            if asset and asset.scope_id:
                matching_nodes = [n for n in nodes if n.scope_id == asset.scope_id]
                if matching_nodes:
                    f_confidence = max(float(n.confidence_weights.get("current_confidence", 0.5)) for n in matching_nodes)
        except Exception:
            pass

        # 4. Risk Acceptance Deduction (0 to 5)
        r_accepted = 0.0
        now = datetime.now(timezone.utc)
        q_ra = select(RiskAcceptance).filter(
            RiskAcceptance.asset_id == asset_id,
            RiskAcceptance.status == "APPROVED",
            RiskAcceptance.is_deleted == False
        )
        res_ra = await db.execute(q_ra)
        ra_list = res_ra.scalars().all()
        for ra in ra_list:
            if ra.expiration_date is None or ra.expiration_date > now:
                r_accepted += 1.5  # Deduct 1.5 per active risk acceptance
        r_accepted = min(r_accepted, 5.0)

        # Domain Weights
        w_asset = 0.3
        w_finding = 0.4
        w_fabric = 0.2
        w_risk = 0.1

        # Calculate final score
        raw_score = (w_asset * c_asset) + (w_finding * max_cvss) + (w_fabric * f_confidence) - (w_risk * r_accepted)
        final_score = max(0.0, min(10.0, raw_score))

        breakdown = {
            "asset_contribution": w_asset * c_asset,
            "finding_contribution": w_finding * max_cvss,
            "fabric_contribution": w_fabric * f_confidence,
            "risk_adjustment": -(w_risk * r_accepted)
        }

        return final_score, breakdown

    @classmethod
    async def aggregate_and_upsert(
        cls,
        db,
        asset_id: uuid.UUID,
        signals: List[Tuple[str, uuid.UUID]]
    ) -> CorrelationCluster:
        """Create or update a CorrelationCluster with aggregated score and breakdown."""
        from src.core.tenant import require_current_tenant_id
        tenant_id = require_current_tenant_id()

        # Load all findings for this asset
        q_find = select(Finding).filter(Finding.asset_id == asset_id, Finding.status == "open")
        res_find = await db.execute(q_find)
        findings = list(res_find.scalars().all())

        fingerprint = cls.compute_fingerprint(asset_id, signals)

        # Check existing cluster by fingerprint
        q_cluster = select(CorrelationCluster).filter(
            CorrelationCluster.tenant_id == tenant_id,
            CorrelationCluster.fingerprint == fingerprint
        )
        res_cluster = await db.execute(q_cluster)
        cluster = res_cluster.scalar_one_or_none()

        unified_score, breakdown = await cls.calculate_score(db, asset_id, findings, signals)

        is_new = False
        if not cluster:
            cluster = CorrelationCluster(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                asset_id=asset_id,
                fingerprint=fingerprint,
                status="open"
            )
            is_new = True
            db.add(cluster)
            # Need to flush to obtain cluster id
            await db.flush()

        old_score = cluster.unified_score
        cluster.unified_score = unified_score
        cluster.score_breakdown_json = breakdown
        cluster.updated_at = datetime.now(timezone.utc)

        # Stage polymorphic signals
        for sig_type, sig_id in signals:
            # Check unique constraint
            q_sig = select(CorrelationClusterSignal).filter(
                CorrelationClusterSignal.cluster_id == cluster.id,
                CorrelationClusterSignal.signal_type == sig_type,
                CorrelationClusterSignal.signal_id == sig_id
            )
            res_sig = await db.execute(q_sig)
            if not res_sig.scalar_one_or_none():
                signal_record = CorrelationClusterSignal(
                    id=uuid.uuid4(),
                    tenant_id=tenant_id,
                    cluster_id=cluster.id,
                    signal_type=sig_type,
                    signal_id=sig_id,
                    added_at=datetime.now(timezone.utc)
                )
                db.add(signal_record)

        # Write history trail
        from src.services.correlation_repository_helper import append_history_helper
        if is_new:
            await append_history_helper(db, cluster.id, "cluster_created", {"score": unified_score})
        elif unified_score > old_score:
            await append_history_helper(db, cluster.id, "score_increased", {"old_score": old_score, "new_score": unified_score})

        await db.flush()
        return cluster
