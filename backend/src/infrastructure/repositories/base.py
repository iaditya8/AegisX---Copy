from typing import Generic, TypeVar, Type, Optional, List
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from src.infrastructure.database.models import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    def __init__(self, session: AsyncSession, model_class: Type[ModelType]):
        self.session = session
        self.model_class = model_class

    async def get(self, id: uuid.UUID) -> Optional[ModelType]:
        result = await self.session.execute(
            select(self.model_class).filter_by(id=id)
        )
        return result.scalar_one_or_none()

    async def list(self) -> List[ModelType]:
        result = await self.session.execute(select(self.model_class))
        return list(result.scalars().all())

    async def save(self, entity: ModelType) -> None:
        self.session.add(entity)

    async def delete(self, id: uuid.UUID) -> None:
        entity = await self.get(id)
        if entity:
            await self.session.delete(entity)
