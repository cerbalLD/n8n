from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Request

router = APIRouter(prefix="/v1", tags=["license-sdk"])


async def _read_json(request: Request) -> dict[str, Any] | None:
	try:
		body = await request.json()
	except Exception:
		return None

	return body if isinstance(body, dict) else None


def _license_stub(path: str, method: str, body: dict[str, Any] | None) -> dict[str, Any]:
	now = datetime.now(timezone.utc)
	expires_at = (now + timedelta(days=365)).replace(microsecond=0).isoformat().replace("+00:00", "Z")

	return {
		"status": "ok",
		"path": path,
		"method": method,
		"access": {
			"allowed": True,
			"hasAccess": True,
			"requiresPayment": False,
			"reason": None,
		},
		"license": {
			"planId": "local-stub",
			"planName": "Local Stub",
			"consumerId": "local-development",
			"environment": "development",
			"expiresAt": expires_at,
		},
		"data": {
			"managementToken": "local-stub-management-token",
			"activationKey": body.get("activationKey") if body else None,
		},
	}


@router.api_route("", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
async def license_sdk_path(request: Request, path: str = ""):
	body = await _read_json(request)
	return _license_stub(path, request.method, body)
