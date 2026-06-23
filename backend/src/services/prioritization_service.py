from typing import Any, Dict, List, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.domain.entities.recommendation import PriorityRankingResponse
from src.infrastructure.database.models import Asset, Finding
from src.services.asset_risk_snapshot_service import AssetRiskSnapshotService
from src.services.correlation_snapshot_service import CorrelationSnapshotService
from src.services.priority_factor_registry import PriorityFactorRegistry


class PrioritizationService:
    @classmethod
    async def calculate_asset_priority(
        cls, db: AsyncSession, asset: Asset
    ) -> Tuple[float, List[Dict[str, Any]]]:
        """Calculate the priority score and supporting factors for an asset."""
        risk_snapshot = AssetRiskSnapshotService.get_snapshot(asset.id)
        if (
            risk_snapshot.get("exposure") == "UNKNOWN"
            and risk_snapshot.get("risk_score") == 0
        ):
            risk_snapshot = await AssetRiskSnapshotService.generate_snapshot(
                db, asset.id
            )

        corr_snapshot = CorrelationSnapshotService.get_snapshot(asset.id)
        if corr_snapshot.get("exposure") == "UNKNOWN" and not corr_snapshot.get(
            "ports"
        ):
            corr_snapshot = await CorrelationSnapshotService.generate_snapshot(
                db, asset.id
            )

        score = 0.0
        factors = []

        # 1. critical_finding: if there is at least one critical finding
        q = select(Finding).where(
            Finding.asset_id == asset.id,
            Finding.status.in_(["open", "acknowledged"]),
        )
        res = await db.execute(q)
        findings = res.scalars().all()

        has_critical = any(f.severity.lower() == "critical" for f in findings)
        if has_critical:
            w = PriorityFactorRegistry.get_weight("critical_finding")
            score += w
            factors.append({"factor": "critical_finding_present", "impact": w})

        # 2. high_risk_asset: risk_score >= 80
        risk_score = risk_snapshot.get("risk_score", 0)
        if risk_score >= 80:
            w = PriorityFactorRegistry.get_weight("high_risk_asset")
            score += w
            factors.append({"factor": "high_risk_asset", "impact": w})

        # 3. internet_exposed: exposure == "EXTERNAL"
        exposure = corr_snapshot.get("exposure", "UNKNOWN")
        if exposure.upper() == "EXTERNAL":
            w = PriorityFactorRegistry.get_weight("internet_exposed")
            score += w
            factors.append({"factor": "internet_exposed", "impact": w})

        # 4. rediscovered_finding
        has_rediscovered = False
        for f in findings:
            if f.first_seen is not None and f.last_seen is not None:
                fs = (
                    f.first_seen.replace(tzinfo=None)
                    if hasattr(f.first_seen, "replace")
                    else f.first_seen
                )
                ls = (
                    f.last_seen.replace(tzinfo=None)
                    if hasattr(f.last_seen, "replace")
                    else f.last_seen
                )
                if ls > fs:
                    has_rediscovered = True
                    break
            from src.infrastructure.database.models import FindingHistory

            q_hist = select(FindingHistory).where(
                FindingHistory.finding_id == f.id,
                FindingHistory.change_type == "status_change",
            )
            res_hist = await db.execute(q_hist)
            history = res_hist.scalars().all()
            for h in history:
                if (
                    h.new_value
                    and h.new_value.get("status") == "open"
                    and h.old_value
                    and h.old_value.get("status") == "resolved"
                ):
                    has_rediscovered = True
                    break
            if has_rediscovered:
                break

        if has_rediscovered:
            w = PriorityFactorRegistry.get_weight("rediscovered_finding")
            score += w
            factors.append({"factor": "rediscovered_finding", "impact": w})

        # 5. high_criticality: criticality is HIGH or CRITICAL
        crit = risk_snapshot.get("criticality", "LOW")
        if crit.upper() in ["HIGH", "CRITICAL"]:
            w = PriorityFactorRegistry.get_weight("high_criticality")
            score += w
            factors.append({"factor": "high_criticality", "impact": w})

        return score, factors

    @classmethod
    async def calculate_finding_priority(
        cls, db: AsyncSession, finding: Finding, parent_asset: Asset = None
    ) -> Tuple[float, List[Dict[str, Any]]]:
        """Calculate the priority score and supporting factors for a finding."""
        if not parent_asset:
            parent_asset = await db.get(Asset, finding.asset_id)
        if not parent_asset or parent_asset.deleted_at is not None:
            return 0.0, []

        risk_snapshot = AssetRiskSnapshotService.get_snapshot(parent_asset.id)
        corr_snapshot = CorrelationSnapshotService.get_snapshot(parent_asset.id)

        score = 0.0
        factors = []

        # 1. critical_finding: finding.severity == "critical"
        if finding.severity.lower() == "critical":
            w = PriorityFactorRegistry.get_weight("critical_finding")
            score += w
            factors.append({"factor": "critical_finding_present", "impact": w})

        # 2. high_risk_asset: parent asset risk_score >= 80
        risk_score = risk_snapshot.get("risk_score", 0)
        if risk_score >= 80:
            w = PriorityFactorRegistry.get_weight("high_risk_asset")
            score += w
            factors.append({"factor": "high_risk_asset", "impact": w})

        # 3. internet_exposed: parent asset exposure == "EXTERNAL"
        exposure = corr_snapshot.get("exposure", "UNKNOWN")
        if exposure.upper() == "EXTERNAL":
            w = PriorityFactorRegistry.get_weight("internet_exposed")
            score += w
            factors.append({"factor": "internet_exposed", "impact": w})

        # 4. rediscovered_finding
        is_rediscovered = False
        if finding.first_seen is not None and finding.last_seen is not None:
            fs = (
                finding.first_seen.replace(tzinfo=None)
                if hasattr(finding.first_seen, "replace")
                else finding.first_seen
            )
            ls = (
                finding.last_seen.replace(tzinfo=None)
                if hasattr(finding.last_seen, "replace")
                else finding.last_seen
            )
            if ls > fs:
                is_rediscovered = True
        else:
            from src.infrastructure.database.models import FindingHistory

            q_hist = select(FindingHistory).where(
                FindingHistory.finding_id == finding.id,
                FindingHistory.change_type == "status_change",
            )
            res_hist = await db.execute(q_hist)
            history = res_hist.scalars().all()
            for h in history:
                if (
                    h.new_value
                    and h.new_value.get("status") == "open"
                    and h.old_value
                    and h.old_value.get("status") == "resolved"
                ):
                    is_rediscovered = True
                    break

        if is_rediscovered:
            w = PriorityFactorRegistry.get_weight("rediscovered_finding")
            score += w
            factors.append({"factor": "rediscovered_finding", "impact": w})

        # 5. high_criticality: parent asset criticality is HIGH or CRITICAL
        crit = risk_snapshot.get("criticality", "LOW")
        if crit.upper() in ["HIGH", "CRITICAL"]:
            w = PriorityFactorRegistry.get_weight("high_criticality")
            score += w
            factors.append({"factor": "high_criticality", "impact": w})

        return score, factors

    @classmethod
    def _extract_names(cls, items: List[Any]) -> List[str]:
        names = []
        if not items:
            return names
        for item in items:
            if isinstance(item, str):
                names.append(item)
            elif isinstance(item, dict):
                name = (
                    item.get("name")
                    or item.get("product")
                    or item.get("product_name")
                    or item.get("technology")
                )
                if name:
                    names.append(str(name))
        return list(set(names))

    @classmethod
    async def get_top_assets(
        cls, db: AsyncSession, limit: int = 10
    ) -> List[PriorityRankingResponse]:
        """Rank and return top risky assets."""
        q = select(Asset).where(Asset.deleted_at.is_(None))
        res = await db.execute(q)
        assets = res.scalars().all()

        scored_assets = []
        for asset in assets:
            score, factors = await cls.calculate_asset_priority(db, asset)
            scored_assets.append((asset, score, factors))

        # Sort by score desc, then asset ID (for determinism)
        scored_assets = sorted(
            scored_assets, key=lambda x: (x[1], str(x[0].id)), reverse=True
        )

        rankings = []
        for idx, (asset, score, factors) in enumerate(scored_assets[:limit]):
            rankings.append(
                PriorityRankingResponse(
                    id=str(asset.id),
                    name=asset.host or asset.ip or str(asset.id),
                    score=score,
                    rank=idx + 1,
                    type="asset",
                    details={
                        "host": asset.host,
                        "ip": asset.ip,
                        "factors": factors,
                    },
                )
            )
        return rankings

    @classmethod
    async def get_top_findings(
        cls, db: AsyncSession, limit: int = 20
    ) -> List[PriorityRankingResponse]:
        """Rank and return top findings."""
        q = select(Finding).join(Asset).where(Asset.deleted_at.is_(None))
        res = await db.execute(q)
        findings = res.scalars().all()

        scored_findings = []
        for finding in findings:
            score, factors = await cls.calculate_finding_priority(db, finding)
            scored_findings.append((finding, score, factors))

        scored_findings = sorted(
            scored_findings, key=lambda x: (x[1], str(x[0].id)), reverse=True
        )

        rankings = []
        for idx, (finding, score, factors) in enumerate(scored_findings[:limit]):
            rankings.append(
                PriorityRankingResponse(
                    id=str(finding.id),
                    name=finding.title,
                    score=score,
                    rank=idx + 1,
                    type="finding",
                    details={
                        "severity": finding.severity,
                        "status": finding.status,
                        "asset_id": str(finding.asset_id),
                        "factors": factors,
                    },
                )
            )
        return rankings

    @classmethod
    async def get_top_technologies(
        cls, db: AsyncSession, limit: int = 20
    ) -> List[PriorityRankingResponse]:
        """Rank and return top technologies based on the maximum risk score
        of assets they deploy on.
        """
        q = select(Asset).where(Asset.deleted_at.is_(None))
        res = await db.execute(q)
        assets = res.scalars().all()

        tech_assets: Dict[str, List[Tuple[Asset, float]]] = {}
        for asset in assets:
            score, _ = await cls.calculate_asset_priority(db, asset)
            corr_snapshot = CorrelationSnapshotService.get_snapshot(asset.id)
            techs = cls._extract_names(corr_snapshot.get("technologies", []))
            for tech in techs:
                if tech not in tech_assets:
                    tech_assets[tech] = []
                tech_assets[tech].append((asset, score))

        scored_techs = []
        for tech, asset_list in tech_assets.items():
            max_score = max(score for _, score in asset_list)
            scored_techs.append((tech, max_score, asset_list))

        scored_techs = sorted(scored_techs, key=lambda x: (x[1], x[0]), reverse=True)

        rankings = []
        for idx, (tech, score, asset_list) in enumerate(scored_techs[:limit]):
            rankings.append(
                PriorityRankingResponse(
                    id=tech,
                    name=tech,
                    score=score,
                    rank=idx + 1,
                    type="technology",
                    details={
                        "asset_count": len(asset_list),
                        "asset_ids": [str(a.id) for a, _ in asset_list],
                    },
                )
            )
        return rankings

    @classmethod
    async def get_top_products(
        cls, db: AsyncSession, limit: int = 20
    ) -> List[PriorityRankingResponse]:
        """Rank and return top products."""
        q = select(Asset).where(Asset.deleted_at.is_(None))
        res = await db.execute(q)
        assets = res.scalars().all()

        prod_assets: Dict[str, List[Tuple[Asset, float]]] = {}
        for asset in assets:
            score, _ = await cls.calculate_asset_priority(db, asset)
            corr_snapshot = CorrelationSnapshotService.get_snapshot(asset.id)
            prods = cls._extract_names(corr_snapshot.get("products", []))
            for prod in prods:
                if prod not in prod_assets:
                    prod_assets[prod] = []
                prod_assets[prod].append((asset, score))

        scored_prods = []
        for prod, asset_list in prod_assets.items():
            max_score = max(score for _, score in asset_list)
            scored_prods.append((prod, max_score, asset_list))

        scored_prods = sorted(scored_prods, key=lambda x: (x[1], x[0]), reverse=True)

        rankings = []
        for idx, (prod, score, asset_list) in enumerate(scored_prods[:limit]):
            rankings.append(
                PriorityRankingResponse(
                    id=prod,
                    name=prod,
                    score=score,
                    rank=idx + 1,
                    type="product",
                    details={
                        "asset_count": len(asset_list),
                        "asset_ids": [str(a.id) for a, _ in asset_list],
                    },
                )
            )
        return rankings
