import asyncio
import uuid
import sys
import os

# Add parent path to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.tenant import set_current_tenant_id
from src.infrastructure.database.unit_of_work import UnitOfWork
from src.services.cyber_resilience_service import CyberResilienceService
from src.domain.entities.cyber_resilience import ServiceCriticality

async def test():
    # Set default tenant
    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000000")
    set_current_tenant_id(tenant_id)
    
    async with UnitOfWork() as uow:
        print("UOW initialized.")
        print(f"Session new objects before sync: {list(uow.session.new)}")
        
        try:
            rec = await CyberResilienceService.create_or_sync_resilience(
                title="Test Backup 999",
                description="Debug DR plan.",
                service_name="Test Provider",
                service_criticality=ServiceCriticality.HIGH,
                uow=uow
            )
            print("create_or_sync_resilience completed.")
            print(f"Session new: {[x.__class__.__name__ for x in uow.session.new]}")
            print(f"Session dirty: {[x.__class__.__name__ for x in uow.session.dirty]}")
            
            print("Executing commit...")
            await uow.commit()
            print("Commit succeeded!")
        except Exception as e:
            print(f"Commit failed with exception: {type(e)}: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())
