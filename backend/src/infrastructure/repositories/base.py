from typing import Generic, TypeVar, Type, Optional, List
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from src.infrastructure.database.models import Base

from sqlalchemy import inspect

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    def __init__(self, session: AsyncSession, model_class: Type[ModelType]):
        self.session = session
        self.model_class = model_class

    def _get_tenant_id(self) -> uuid.UUID:
        from src.core.tenant import require_current_tenant_id
        return require_current_tenant_id()

    def _tenant_filter(self):
        return self.model_class.tenant_id == self._get_tenant_id()

    def _tenant_filter_for(self, model_class):
        return model_class.tenant_id == self._get_tenant_id()

    async def get(self, id: uuid.UUID) -> Optional[ModelType]:
        # Dynamically retrieve primary key column via mapper inspection
        mapper = inspect(self.model_class)
        pk_column = mapper.primary_key[0]
        query = select(self.model_class).filter(pk_column == id)
        if hasattr(self.model_class, "tenant_id"):
            query = query.filter(self._tenant_filter())
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list(self) -> List[ModelType]:
        query = select(self.model_class)
        if hasattr(self.model_class, "tenant_id"):
            query = query.filter(self._tenant_filter())
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def save(self, entity: ModelType) -> None:
        if hasattr(entity, "tenant_id"):
            from src.core.tenant import TenantMismatchError
            expected_tid = self._get_tenant_id()
            if entity.tenant_id is None:
                entity.tenant_id = expected_tid
            elif entity.tenant_id != expected_tid:
                raise TenantMismatchError(
                    f"Entity tenant_id {entity.tenant_id} does not match current context {expected_tid}"
                )
        if hasattr(entity, "is_deleted") and getattr(entity, "is_deleted", None) is None:
            entity.is_deleted = False
        self.session.add(entity)

    async def delete(self, id: uuid.UUID) -> None:
        entity = await self.get(id)  # get() already applies tenant filter
        if entity:
            await self.session.delete(entity)
