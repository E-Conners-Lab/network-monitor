"""API endpoints for network validation tests."""

from enum import Enum
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.api.auth import get_current_user
from src.tasks.network_tests import run_network_test, run_device_test

router = APIRouter(prefix="/tests", tags=["tests"])


class TestType(str, Enum):
    """Test type enumeration."""
    FULL = "full"
    QUICK = "quick"


class TestRequest(BaseModel):
    """Request to run tests."""
    test_type: TestType = TestType.FULL


class TestResponse(BaseModel):
    """Response from test initiation."""
    task_id: str
    status: str
    message: str


class TestResultResponse(BaseModel):
    """Test result response."""
    task_id: str
    status: str
    result: Optional[dict] = None


@router.post("/run", response_model=TestResponse)
async def start_network_test(
    request: TestRequest,
    current_user=Depends(get_current_user),
):
    """
    Start a network validation test.

    - **test_type**: "full" for complete validation, "quick" for health check only
    """
    task = run_network_test.delay(test_type=request.test_type.value)

    return TestResponse(
        task_id=task.id,
        status="queued",
        message=f"{request.test_type.value.title()} network test queued",
    )


@router.post("/run/full", response_model=TestResponse)
async def start_full_test(current_user=Depends(get_current_user)):
    """Start a full network validation test."""
    task = run_network_test.delay(test_type="full")

    return TestResponse(
        task_id=task.id,
        status="queued",
        message="Full network validation test queued",
    )


@router.post("/run/quick", response_model=TestResponse)
async def start_quick_test(current_user=Depends(get_current_user)):
    """Start a quick health check test."""
    task = run_network_test.delay(test_type="quick")

    return TestResponse(
        task_id=task.id,
        status="queued",
        message="Quick health check test queued",
    )


@router.post("/devices/{device_id}/run", response_model=TestResponse)
async def start_device_test(
    device_id: int,
    request: TestRequest = TestRequest(),
    current_user=Depends(get_current_user),
):
    """Start validation tests on a single device."""
    task = run_device_test.delay(device_id=device_id, test_type=request.test_type.value)

    return TestResponse(
        task_id=task.id,
        status="queued",
        message=f"Device test queued for device {device_id}",
    )


@router.get("/status/{task_id}", response_model=TestResultResponse)
async def get_test_status(
    task_id: str,
    current_user=Depends(get_current_user),
):
    """Get the status and result of a test task."""
    from celery.result import AsyncResult

    result = AsyncResult(task_id)

    if result.state == "PENDING":
        return TestResultResponse(
            task_id=task_id,
            status="pending",
            result=None,
        )
    elif result.state == "STARTED":
        return TestResultResponse(
            task_id=task_id,
            status="running",
            result=None,
        )
    elif result.state == "SUCCESS":
        return TestResultResponse(
            task_id=task_id,
            status="completed",
            result=result.result,
        )
    elif result.state == "FAILURE":
        return TestResultResponse(
            task_id=task_id,
            status="failed",
            result={"error": str(result.result)},
        )
    else:
        return TestResultResponse(
            task_id=task_id,
            status=result.state.lower(),
            result=None,
        )
