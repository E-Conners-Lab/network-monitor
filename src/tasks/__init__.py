"""Celery tasks for background processing."""

from celery import Celery

from src.config import get_settings

settings = get_settings()

celery_app = Celery(
    "network_monitor",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "src.tasks.polling",
        "src.tasks.remediation",
        "src.tasks.routing",
        "src.tasks.network_tests",
        "src.tasks.config_backup",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 minutes max per task
    worker_prefetch_multiplier=1,  # Fair task distribution
)

# Beat schedule for periodic tasks
celery_app.conf.beat_schedule = {
    "poll-devices-every-30-seconds": {
        "task": "src.tasks.polling.poll_all_devices",
        "schedule": settings.polling_interval_seconds,
    },
    "sync-netbox-every-5-minutes": {
        "task": "src.tasks.polling.sync_netbox_devices",
        "schedule": 300.0,
    },
    "cleanup-old-metrics-daily": {
        "task": "src.tasks.polling.cleanup_old_metrics",
        "schedule": 86400.0,  # 24 hours
        "kwargs": {"days_to_keep": 30},
    },
    "poll-routing-every-5-minutes": {
        "task": "src.tasks.routing.poll_routing_protocols",
        "schedule": 300.0,  # BGP/OSPF polling every 5 minutes (SSH is slow)
    },
    "backup-configs-daily": {
        "task": "tasks.scheduled_config_backup",
        "schedule": 86400.0,  # 24 hours - daily config backup
    },
}
