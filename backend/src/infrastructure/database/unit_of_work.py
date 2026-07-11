import uuid
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from src.infrastructure.database.session import AsyncSessionLocal
from src.infrastructure.repositories import (
    EventRepository,
    CyberResilienceRepository,
    SOCRepository,
    GRCRepository,
    KnowledgeRepository,
    ThreatRepository,
    CyberRiskRepository,
    GraphRepository,
    IncidentRepository,
    RiskAcceptanceRepository,
    RemediationRepository,
    HuntRepository,
    FabricRepository,
    PostureRepository,
    DecisionRepository,
    ProgramRepository,
    PurpleTeamRepository,
    CorrelationRepository,
)
from src.core.tenant import get_current_tenant_id


class UnitOfWork:
    def __init__(self, *, require_tenant: bool = True):
        self.session_factory = AsyncSessionLocal
        self.session: AsyncSession = None
        self._require_tenant = require_tenant
        
        # Repositories
        self.event_repo: EventRepository = None
        self.resilience_repo: CyberResilienceRepository = None
        self.soc_repo: SOCRepository = None
        self.grc_repo: GRCRepository = None
        self.knowledge_repo: KnowledgeRepository = None
        self.threat_repo: ThreatRepository = None
        self.risk_repo: CyberRiskRepository = None
        self.graph_repo: GraphRepository = None
        self.incident_repo: IncidentRepository = None
        self.risk_acceptance_repo: RiskAcceptanceRepository = None
        self.remediation_repo: RemediationRepository = None
        self.hunt_repo: HuntRepository = None
        self.fabric_repo: FabricRepository = None
        self.posture_repo: PostureRepository = None
        self.decision_repo: DecisionRepository = None
        self.program_repo: ProgramRepository = None
        self.purple_team_repo: PurpleTeamRepository = None
        self.correlation_repo: CorrelationRepository = None

    async def __aenter__(self):
        self.session = self.session_factory()
        
        # Apply current tenant RLS context to connection
        tenant_id = get_current_tenant_id()
        if tenant_id:
            bind = self.session.bind
            if bind and getattr(bind.dialect, "name", "") == "postgresql":
                await self.session.execute(
                    sa.text("SELECT set_config('app.current_tenant', :tenant_id, true)"),
                    {"tenant_id": str(tenant_id)}
                )
        elif self._require_tenant:
            from src.core.tenant import TenantContextError
            raise TenantContextError(
                "UnitOfWork requires tenant context. Use UnitOfWork(require_tenant=False) for system-level operations."
            )
            
        # Instantiate repositories
        self.event_repo = EventRepository(self.session)
        self.resilience_repo = CyberResilienceRepository(self.session)
        self.soc_repo = SOCRepository(self.session)
        self.grc_repo = GRCRepository(self.session)
        self.knowledge_repo = KnowledgeRepository(self.session)
        self.threat_repo = ThreatRepository(self.session)
        self.risk_repo = CyberRiskRepository(self.session)
        self.graph_repo = GraphRepository(self.session)
        self.incident_repo = IncidentRepository(self.session)
        self.risk_acceptance_repo = RiskAcceptanceRepository(self.session)
        self.remediation_repo = RemediationRepository(self.session)
        self.hunt_repo = HuntRepository(self.session)
        self.fabric_repo = FabricRepository(self.session)
        self.posture_repo = PostureRepository(self.session)
        self.decision_repo = DecisionRepository(self.session)
        self.program_repo = ProgramRepository(self.session)
        self.purple_team_repo = PurpleTeamRepository(self.session)
        self.correlation_repo = CorrelationRepository(self.session)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            await self.rollback()
        await self.session.close()

    async def commit(self):
        pending_events = []
        if self.session:
            for obj in self.session.new:
                if obj.__class__.__name__ == "WorkflowEvent":
                    pending_events.append((obj.event_type, obj.payload, obj.tenant_id))

        await self.session.commit()

        for event_type, payload, tenant_id in pending_events:
            if event_type in ("finding.discovered", "alert.created", "threat.ioc_added", "validation.failed"):
                try:
                    from src.infrastructure.celery.worker import correlation_event_task
                    correlation_event_task.delay(event_type, payload, str(tenant_id))
                except Exception:
                    pass

    async def rollback(self):
        await self.session.rollback()
