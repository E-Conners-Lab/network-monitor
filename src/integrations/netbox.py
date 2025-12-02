"""NetBox integration for device inventory management."""

import logging
from dataclasses import dataclass
from typing import Optional

import pynetbox
from pynetbox.core.response import Record

from src.config import get_settings
from src.models.device import DeviceType

logger = logging.getLogger(__name__)


# Map NetBox device roles to our DeviceType enum
ROLE_TO_DEVICE_TYPE = {
    "router": DeviceType.ROUTER,
    "core": DeviceType.ROUTER,  # Core routers
    "pe": DeviceType.ROUTER,  # Provider Edge routers
    "gateway": DeviceType.ROUTER,  # Gateway routers
    "aggregation": DeviceType.ROUTER,  # Aggregation routers
    "switch": DeviceType.SWITCH,
    "firewall": DeviceType.FIREWALL,
    "access-point": DeviceType.ACCESS_POINT,
    "ap": DeviceType.ACCESS_POINT,
}


@dataclass
class NetBoxDevice:
    """Device data from NetBox."""

    netbox_id: int
    name: str
    hostname: str
    ip_address: str
    device_type: DeviceType
    vendor: str
    model: Optional[str]
    platform: Optional[str]
    site: Optional[str]
    location: Optional[str]
    status: str
    tags: list[str]


class NetBoxClient:
    """Client for interacting with NetBox API."""

    def __init__(self, url: str = None, token: str = None):
        """
        Initialize NetBox client.

        Args:
            url: NetBox URL (defaults to settings)
            token: NetBox API token (defaults to settings)
        """
        settings = get_settings()
        self.url = url or settings.netbox_url
        self.token = token or settings.netbox_token

        if not self.token:
            logger.warning("NetBox token not configured")
            self._api = None
        else:
            self._api = pynetbox.api(self.url, token=self.token)

    @property
    def is_configured(self) -> bool:
        """Check if NetBox client is properly configured."""
        return self._api is not None and bool(self.token)

    def test_connection(self) -> dict:
        """Test connection to NetBox."""
        if not self.is_configured:
            return {"success": False, "error": "NetBox not configured (missing token)"}

        try:
            # Try to get API status
            status = self._api.status()
            return {
                "success": True,
                "netbox_version": status.get("netbox-version"),
                "django_version": status.get("django-version"),
            }
        except Exception as e:
            logger.error(f"NetBox connection error: {e}")
            return {"success": False, "error": str(e)}

    def get_devices(
        self,
        site: str = None,
        role: str = None,
        status: str = "active",
        tag: str = None,
    ) -> list[NetBoxDevice]:
        """
        Get devices from NetBox.

        Args:
            site: Filter by site name
            role: Filter by device role
            status: Filter by status (active, planned, staged, etc.)
            tag: Filter by tag

        Returns:
            List of NetBoxDevice objects
        """
        if not self.is_configured:
            logger.warning("NetBox not configured, returning empty device list")
            return []

        try:
            # Build filter params
            params = {}
            if site:
                params["site"] = site
            if role:
                params["role"] = role
            if status:
                params["status"] = status
            if tag:
                params["tag"] = tag

            devices = self._api.dcim.devices.filter(**params)
            return [self._convert_device(d) for d in devices if self._has_primary_ip(d)]

        except Exception as e:
            logger.error(f"Error fetching devices from NetBox: {e}")
            return []

    def get_device(self, device_id: int) -> Optional[NetBoxDevice]:
        """Get a single device by NetBox ID."""
        if not self.is_configured:
            return None

        try:
            device = self._api.dcim.devices.get(device_id)
            if device and self._has_primary_ip(device):
                return self._convert_device(device)
            return None
        except Exception as e:
            logger.error(f"Error fetching device {device_id} from NetBox: {e}")
            return None

    def get_device_by_name(self, name: str) -> Optional[NetBoxDevice]:
        """Get a device by name."""
        if not self.is_configured:
            return None

        try:
            device = self._api.dcim.devices.get(name=name)
            if device and self._has_primary_ip(device):
                return self._convert_device(device)
            return None
        except Exception as e:
            logger.error(f"Error fetching device '{name}' from NetBox: {e}")
            return None

    def get_device_credentials(self, device_id: int) -> Optional[dict]:
        """
        Get device credentials from NetBox secrets.

        Note: Requires NetBox secrets plugin to be installed.

        Args:
            device_id: NetBox device ID

        Returns:
            Dict with username, password, enable_password, snmp_community
        """
        if not self.is_configured:
            return None

        try:
            # Try to get secrets associated with the device
            # This requires the netbox-secrets plugin
            secrets = self._api.secrets.secrets.filter(device_id=device_id)

            credentials = {}
            for secret in secrets:
                role = secret.role.slug if secret.role else ""
                if role == "username":
                    credentials["username"] = secret.plaintext
                elif role == "password":
                    credentials["password"] = secret.plaintext
                elif role == "enable-password":
                    credentials["enable_password"] = secret.plaintext
                elif role == "snmp-community":
                    credentials["snmp_community"] = secret.plaintext

            return credentials if credentials else None

        except AttributeError:
            # Secrets plugin not installed
            logger.debug("NetBox secrets plugin not available")
            return None
        except Exception as e:
            logger.error(f"Error fetching credentials for device {device_id}: {e}")
            return None

    def _has_primary_ip(self, device: Record) -> bool:
        """Check if device has a primary IP address."""
        return device.primary_ip4 is not None or device.primary_ip is not None

    def _convert_device(self, device: Record) -> NetBoxDevice:
        """Convert NetBox device record to NetBoxDevice dataclass."""
        # Get primary IP address
        ip_address = None
        if device.primary_ip4:
            ip_address = str(device.primary_ip4.address).split("/")[0]
        elif device.primary_ip:
            ip_address = str(device.primary_ip.address).split("/")[0]

        # Determine device type from role
        device_type = DeviceType.OTHER
        if device.role:
            role_slug = device.role.slug.lower()
            device_type = ROLE_TO_DEVICE_TYPE.get(role_slug, DeviceType.OTHER)

        # Get vendor from manufacturer
        vendor = "unknown"
        if device.device_type and device.device_type.manufacturer:
            vendor = device.device_type.manufacturer.slug

        # Get model
        model = None
        if device.device_type:
            model = device.device_type.model

        # Get platform
        platform = None
        if device.platform:
            platform = device.platform.slug

        # Get site and location
        site = device.site.slug if device.site else None
        location = None
        if device.location:
            location = device.location.name

        # Get tags
        tags = [tag.slug for tag in device.tags] if device.tags else []

        return NetBoxDevice(
            netbox_id=device.id,
            name=device.name,
            hostname=device.name,  # Use name as hostname if not specified
            ip_address=ip_address,
            device_type=device_type,
            vendor=vendor,
            model=model,
            platform=platform,
            site=site,
            location=location,
            status=device.status.value if device.status else "unknown",
            tags=tags,
        )


class NetBoxSyncService:
    """Service for syncing devices between NetBox and our database."""

    def __init__(self, netbox_client: NetBoxClient = None):
        self.client = netbox_client or NetBoxClient()

    async def sync_devices(self, db_session, site: str = None) -> dict:
        """
        Sync devices from NetBox to our database.

        Args:
            db_session: SQLAlchemy async session
            site: Optional site filter

        Returns:
            Dict with sync results (created, updated, errors)
        """
        from sqlalchemy import select
        from src.models.device import Device

        if not self.client.is_configured:
            return {"success": False, "error": "NetBox not configured"}

        results = {
            "success": True,
            "created": 0,
            "updated": 0,
            "skipped": 0,
            "errors": [],
        }

        try:
            netbox_devices = self.client.get_devices(site=site)
            logger.info(f"Found {len(netbox_devices)} devices in NetBox")

            for nb_device in netbox_devices:
                try:
                    # Check if device already exists by netbox_id
                    stmt = select(Device).where(Device.netbox_id == nb_device.netbox_id)
                    result = await db_session.execute(stmt)
                    existing = result.scalar_one_or_none()

                    if existing:
                        # Update existing device
                        existing.name = nb_device.name
                        existing.hostname = nb_device.hostname
                        existing.ip_address = nb_device.ip_address
                        existing.device_type = nb_device.device_type
                        existing.vendor = nb_device.vendor
                        existing.model = nb_device.model
                        existing.location = nb_device.location
                        existing.is_active = nb_device.status == "active"
                        results["updated"] += 1
                    else:
                        # Check if device exists by name
                        stmt = select(Device).where(Device.name == nb_device.name)
                        result = await db_session.execute(stmt)
                        existing_by_name = result.scalar_one_or_none()

                        if existing_by_name:
                            # Update with netbox_id
                            existing_by_name.netbox_id = nb_device.netbox_id
                            existing_by_name.ip_address = nb_device.ip_address
                            existing_by_name.device_type = nb_device.device_type
                            results["updated"] += 1
                        else:
                            # Create new device
                            new_device = Device(
                                name=nb_device.name,
                                hostname=nb_device.hostname,
                                ip_address=nb_device.ip_address,
                                device_type=nb_device.device_type,
                                vendor=nb_device.vendor,
                                model=nb_device.model,
                                location=nb_device.location,
                                netbox_id=nb_device.netbox_id,
                                is_active=nb_device.status == "active",
                                tags={"netbox_tags": nb_device.tags},
                            )
                            db_session.add(new_device)
                            results["created"] += 1

                except Exception as e:
                    logger.error(f"Error syncing device {nb_device.name}: {e}")
                    results["errors"].append(f"{nb_device.name}: {str(e)}")

            await db_session.commit()
            logger.info(
                f"NetBox sync complete: {results['created']} created, "
                f"{results['updated']} updated, {len(results['errors'])} errors"
            )

        except Exception as e:
            logger.error(f"NetBox sync failed: {e}")
            results["success"] = False
            results["errors"].append(str(e))

        return results
