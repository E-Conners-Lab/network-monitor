"""WebSocket endpoint for real-time updates."""

import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


class ConnectionManager:
    """Manage WebSocket connections."""

    def __init__(self):
        self.active_connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        """Accept and track a new WebSocket connection."""
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        self.active_connections.discard(websocket)

    async def broadcast(self, message: dict):
        """Send a message to all connected clients."""
        if not self.active_connections:
            return

        message_text = json.dumps(message)
        disconnected = set()

        for connection in self.active_connections:
            try:
                await connection.send_text(message_text)
            except Exception:
                disconnected.add(connection)

        # Clean up disconnected clients
        self.active_connections -= disconnected

    async def send_to_client(self, websocket: WebSocket, message: dict):
        """Send a message to a specific client."""
        try:
            await websocket.send_text(json.dumps(message))
        except Exception:
            self.disconnect(websocket)


# Global connection manager
manager = ConnectionManager()


@router.websocket("/events")
async def websocket_events(websocket: WebSocket):
    """
    WebSocket endpoint for real-time events.

    Events include:
    - device_status: Device reachability changes
    - metric_update: New metric data
    - alert_created: New alert
    - alert_resolved: Alert resolved
    - remediation_started: Remediation action started
    - remediation_completed: Remediation action completed
    """
    await manager.connect(websocket)

    try:
        # Send initial connection confirmation
        await manager.send_to_client(
            websocket,
            {
                "type": "connected",
                "message": "Connected to Network Monitor events",
            },
        )

        # Keep connection alive and handle incoming messages
        while True:
            try:
                data = await asyncio.wait_for(
                    websocket.receive_text(), timeout=30.0
                )
                # Handle ping/pong for keepalive
                message = json.loads(data)
                if message.get("type") == "ping":
                    await manager.send_to_client(websocket, {"type": "pong"})
                elif message.get("type") == "subscribe":
                    # Handle subscription to specific device or event type
                    await manager.send_to_client(
                        websocket,
                        {
                            "type": "subscribed",
                            "channel": message.get("channel"),
                        },
                    )
            except TimeoutError:
                # Send keepalive ping
                await manager.send_to_client(websocket, {"type": "ping"})
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)


# Helper functions for broadcasting events (to be called from monitoring tasks)
async def broadcast_device_status(device_id: int, device_name: str, is_reachable: bool):
    """Broadcast device status change."""
    await manager.broadcast(
        {
            "type": "device_status",
            "device_id": device_id,
            "device_name": device_name,
            "is_reachable": is_reachable,
        }
    )


async def broadcast_metric(device_id: int, metric_type: str, value: float, unit: str = None):
    """Broadcast new metric data."""
    await manager.broadcast(
        {
            "type": "metric_update",
            "device_id": device_id,
            "metric_type": metric_type,
            "value": value,
            "unit": unit,
        }
    )


async def broadcast_alert(alert_id: int, device_id: int, severity: str, title: str):
    """Broadcast new alert."""
    await manager.broadcast(
        {
            "type": "alert_created",
            "alert_id": alert_id,
            "device_id": device_id,
            "severity": severity,
            "title": title,
        }
    )


async def broadcast_remediation(
    remediation_id: int, device_id: int, playbook: str, status: str
):
    """Broadcast remediation event."""
    await manager.broadcast(
        {
            "type": f"remediation_{status}",
            "remediation_id": remediation_id,
            "device_id": device_id,
            "playbook": playbook,
        }
    )
