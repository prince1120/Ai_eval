import uuid
from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        organization_id: uuid.UUID,
        email: str,
        hashed_password: str,
        role: str = "evaluator",
        full_name: Optional[str] = None,
    ) -> User:
        user = User(
            organization_id=organization_id,
            email=email,
            hashed_password=hashed_password,
            role=role,
            full_name=full_name,
        )
        self.session.add(user)
        await self.session.flush()
        return user

    async def get_by_id(
        self, user_id: uuid.UUID, organization_id: Optional[uuid.UUID] = None
    ) -> Optional[User]:
        query = select(User).where(User.id == user_id)
        if organization_id:
            query = query.where(User.organization_id == organization_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[User]:
        result = await self.session.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()

    async def list_by_organization(self, organization_id: uuid.UUID) -> List[User]:
        result = await self.session.execute(
            select(User).where(User.organization_id == organization_id).order_by(User.created_at)
        )
        return list(result.scalars().all())

    async def update(self, user: User) -> User:
        await self.session.flush()
        return user

    async def delete(self, user: User) -> None:
        await self.session.delete(user)
        await self.session.flush()
