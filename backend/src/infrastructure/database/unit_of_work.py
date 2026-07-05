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
)
from src.core.tenant import get_current_tenant_id


class UnitOfWork:
    def __init__(self):
        self.session_factory = AsyncSessionLocal
        self.session: AsyncSession = None
        
        # Repositories
        self.event_repo: EventRepository = None
        self.resilience_repo: CyberResilienceRepository = None
        self.soc_repo: SOCRepository = None
        self.grc_repo: GRCRepository = None
        self.knowledge_repo: KnowledgeRepository = None
        self.threat_repo: ThreatRepository = None
        self.risk_repo: CyberRiskRepository = None

    async def __aenter__(self):
        self.session = self.session_factory()
        
        # Apply current tenant RLS context to connection
        tenant_id = get_current_tenant_id()
        if tenant_id:
            await self.session.execute(
                sa.text("SELECT set_config('app.current_tenant', :tenant_id, true)"),
                {"tenant_id": str(tenant_id)}
            )
            
        # Instantiate repositories
        self.event_repo = EventRepository(self.session)
        self.resilience_repo = CyberResilienceRepository(self.session)
        self.soc_repo = SOCRepository(self.session)
        self.grc_repo = GRCRepository(self.session)
        self.knowledge_repo = KnowledgeRepository(self.session)
        self.threat_repo = ThreatRepository(self.session)
        self.risk_repo = CyberRiskRepository(self.session)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            await self.rollback()
        await self.session.close()

    async def commit(self):
        await self.session.commit()

    async def rollback(self):
        await self.session.rollback()
