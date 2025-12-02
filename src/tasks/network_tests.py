"""Celery tasks for network validation tests."""

import asyncio
import logging
import os
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from src.tasks import celery_app
from src.config import get_settings
from src.models.device import Device

logger = logging.getLogger(__name__)


def get_async_session():
    """Create async session for database operations."""
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


def run_async(coro):
    """Run async code in sync context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError("Event loop is closed")
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        # Don't close the loop - it may be reused by other tasks
        pass


@celery_app.task(bind=True, time_limit=600)
def run_network_test(self, test_type: str = "full"):
    """
    Run network validation tests.

    Args:
        test_type: "full" or "quick"

    Returns:
        Test results dict
    """
    logger.info(f"Starting network validation test: {test_type}")

    async def _run_test():
        from src.tests.network_validation import run_network_validation

        AsyncSessionLocal = get_async_session()
        async with AsyncSessionLocal() as db:
            # Get all devices from database
            result = await db.execute(select(Device))
            devices = result.scalars().all()

            device_list = [
                {
                    "id": d.id,
                    "name": d.name,
                    "ip_address": d.ip_address,
                    "ssh_port": d.ssh_port,
                    "vendor": d.vendor,
                    "device_type": d.device_type,
                }
                for d in devices
            ]

            # Get credentials from environment
            credentials = {
                "username": os.environ.get("SSH_USERNAME", "admin"),
                "password": os.environ.get("SSH_PASSWORD", ""),
                "enable_password": os.environ.get("SSH_ENABLE_PASSWORD", ""),
            }

            logger.info(f"Running {test_type} test on {len(device_list)} devices")

            # Run the validation
            results = run_network_validation(
                devices=device_list,
                credentials=credentials,
                test_type=test_type,
            )

            return results

    return run_async(_run_test())


@celery_app.task(bind=True, time_limit=300)
def run_device_test(self, device_id: int, test_type: str = "full"):
    """
    Run validation tests on a single device.

    Args:
        device_id: Device ID to test
        test_type: "full" or "quick"

    Returns:
        Test results dict
    """
    logger.info(f"Starting device test for device {device_id}: {test_type}")

    async def _run_test():
        from src.tests.network_validation import run_network_validation

        AsyncSessionLocal = get_async_session()
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Device).where(Device.id == device_id)
            )
            device = result.scalar_one_or_none()

            if not device:
                return {"error": f"Device {device_id} not found"}

            device_list = [
                {
                    "id": device.id,
                    "name": device.name,
                    "ip_address": device.ip_address,
                    "ssh_port": device.ssh_port,
                    "vendor": device.vendor,
                    "device_type": device.device_type,
                }
            ]

            credentials = {
                "username": os.environ.get("SSH_USERNAME", "admin"),
                "password": os.environ.get("SSH_PASSWORD", ""),
                "enable_password": os.environ.get("SSH_ENABLE_PASSWORD", ""),
            }

            results = run_network_validation(
                devices=device_list,
                credentials=credentials,
                test_type=test_type,
            )

            return results

    return run_async(_run_test())
