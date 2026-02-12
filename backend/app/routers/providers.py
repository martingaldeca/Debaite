import os

from fastapi import APIRouter
from litellm import completion
from pydantic import BaseModel

router = APIRouter(prefix="/providers", tags=["providers"])


class CheckStatusRequest(BaseModel):
    provider: str
    api_key: str
    model: str


class CheckStatusResponse(BaseModel):
    status: str
    latency: float
    message: str


@router.post("/check_status", response_model=CheckStatusResponse)
async def check_provider_status(request: CheckStatusRequest):
    try:
        # Simple test prompt
        messages = [{"role": "user", "content": "say ok"}]

        start_time = os.times().elapsed
        completion(
            model=request.model,
            messages=messages,
            api_key=request.api_key,
            max_tokens=5,
        )
        end_time = os.times().elapsed

        return CheckStatusResponse(
            status="verified",
            latency=end_time - start_time,
            message="Provider verified successfully",
        )
    except Exception as e:
        # Provide a friendly error message based on the exception if possible
        return CheckStatusResponse(status="failed", latency=0, message=str(e))
