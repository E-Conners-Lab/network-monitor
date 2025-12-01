#!/usr/bin/env python3
"""Initialize database with default admin user."""

import asyncio
import sys
sys.path.insert(0, "/app")

from sqlalchemy import select
from passlib.context import CryptContext

from src.models.base import AsyncSessionLocal
from src.models.user import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def create_admin_user():
    """Create default admin user if not exists."""
    async with AsyncSessionLocal() as session:
        # Check if admin exists
        result = await session.execute(select(User).where(User.username == "admin"))
        if result.scalar_one_or_none():
            print("Admin user already exists")
            return

        # Create admin user
        admin = User(
            username="admin",
            email="admin@localhost",
            hashed_password=pwd_context.hash("admin"),
            is_active=True,
            is_superuser=True,
        )
        session.add(admin)
        await session.commit()
        print("Admin user created successfully")
        print("Username: admin")
        print("Password: admin")
        print("⚠️  Please change the password after first login!")


if __name__ == "__main__":
    asyncio.run(create_admin_user())
