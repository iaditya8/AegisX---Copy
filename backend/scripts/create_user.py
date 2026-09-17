import asyncio
import os
import sys

# Add the current directory to sys.path to allow imports from src
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.core.security import hash_password
from src.infrastructure.database.models import User
from src.infrastructure.database.session import AsyncSessionLocal


async def create_user_cli(username: str, password: str, role: str):
    async with AsyncSessionLocal() as db:
        from sqlalchemy import select
        from src.core.tenant import set_current_tenant_id
        from src.infrastructure.database.models import Tenant
        import uuid

        # Check and use existing tenant if present, otherwise create System Tenant
        tenant_result = await db.execute(select(Tenant))
        tenant = tenant_result.scalars().first()
        if not tenant:
            default_tenant_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
            tenant = Tenant(id=default_tenant_id, name="System Tenant")
            db.add(tenant)
            await db.commit()
            print("System Tenant created.")
        else:
            default_tenant_id = tenant.id
            print(f"Using existing tenant: '{tenant.name}' ({tenant.id})")

        # Set tenant ID context
        set_current_tenant_id(default_tenant_id)

        result = await db.execute(select(User).where(User.username == username))
        existing_user = result.scalars().first()
        if existing_user:
            print(f"User '{username}' already exists.")
            return

        user = User(
            username=username,
            role=role,
            password_hash=hash_password(password),
            display_name=username.capitalize(),
            tenant_id=default_tenant_id,
        )
        db.add(user)
        await db.commit()
        print(f"Successfully created user '{username}' with role '{role}'.")


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python create_user.py <username> <password> <role>")
        sys.exit(1)

    username = sys.argv[1]
    password = sys.argv[2]
    role = sys.argv[3]

    if role not in ("admin", "operator", "reader"):
        print("Error: role must be 'admin', 'operator', or 'reader'")
        sys.exit(1)

    asyncio.run(create_user_cli(username, password, role))
