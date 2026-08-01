from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, Response

router = APIRouter(tags=["content"])

NOW = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

CATEGORIES = [
	{"id": 1, "name": "AI"},
	{"id": 2, "name": "Sales"},
	{"id": 3, "name": "Operations"},
]

NODE_MANUAL_TRIGGER = {
	"id": 1,
	"name": "n8n-nodes-base.manualTrigger",
	"displayName": "Manual Trigger",
	"icon": "fa:mouse-pointer",
	"defaults": {},
	"iconData": {"type": "icon", "icon": "mouse-pointer"},
	"typeVersion": 1,
}

NODE_SET = {
	"id": 2,
	"name": "n8n-nodes-base.set",
	"displayName": "Edit Fields",
	"icon": "fa:pen",
	"defaults": {},
	"iconData": {"type": "icon", "icon": "pen"},
	"typeVersion": 3.4,
}


def _workflow_definition(template_id: str) -> dict[str, Any]:
	return {
		"nodes": [
			{
				"id": "2f7a6ed6-66b6-4cbb-8c34-a248bd65fb8a",
				"name": "When clicking 'Test workflow'",
				"type": "n8n-nodes-base.manualTrigger",
				"typeVersion": 1,
				"position": [0, 0],
				"parameters": {},
			},
			{
				"id": "3d77d59a-9a6d-4300-8f6c-8d4623e15413",
				"name": "Access Granted",
				"type": "n8n-nodes-base.set",
				"typeVersion": 3.4,
				"position": [240, 0],
				"parameters": {
					"mode": "manual",
					"assignments": {
						"assignments": [
							{
								"id": "83e1e83d-f6e5-4d97-a713-1fd2ddafc316",
								"name": "message",
								"value": f"Access granted for template {template_id}",
								"type": "string",
							}
						]
					},
					"options": {},
				},
			},
		],
		"connections": {
			"When clicking 'Test workflow'": {
				"main": [[{"node": "Access Granted", "type": "main", "index": 0}]]
			}
		},
		"settings": {},
		"pinData": {},
	}


def _numeric_id(value: str) -> int:
	match = re.search(r"\d+", value)
	if match:
		return int(match.group(0))

	return 1000 + sum(ord(char) for char in value) % 900000


def _access_payload(content_type: str, content_id: str | int) -> dict[str, Any]:
	return {
		"contentType": content_type,
		"contentId": str(content_id),
		"allowed": True,
		"hasAccess": True,
		"requiresPayment": False,
		"payment": {
			"required": False,
			"status": "not_required",
		},
		"reason": None,
	}


def _template_summary(template_id: str, name: str | None = None) -> dict[str, Any]:
	numeric_id = _numeric_id(template_id)
	return {
		"id": numeric_id,
		"createdAt": NOW,
		"name": name or f"Demo workflow template {numeric_id}",
		"nodes": [NODE_MANUAL_TRIGGER, NODE_SET],
		"totalViews": 0,
		"user": {
			"username": "local",
			"name": "Local Content",
			"avatar": "",
			"verified": True,
		},
		"readyToDemo": True,
		"access": _access_payload("workflow_template", numeric_id),
	}


def _template_full(template_id: str) -> dict[str, Any]:
	summary = _template_summary(template_id)
	workflow = _workflow_definition(str(summary["id"]))

	return {
		**summary,
		"description": (
			"This is a local stub template returned by the backend content service. "
			"Payment and access checks are intentionally bypassed for now."
		),
		"image": [],
		"categories": CATEGORIES[:1],
		"workflowInfo": {
			"nodeCount": len(workflow["nodes"]),
			"nodeTypes": {
				"n8n-nodes-base.manualTrigger": {"count": 1},
				"n8n-nodes-base.set": {"count": 1},
			},
		},
		"workflow": workflow,
	}


def _workflows() -> list[dict[str, Any]]:
	return [
		_template_summary("1001", "Local access check workflow"),
		_template_summary("1002", "Local paid content placeholder"),
	]


def _selected_categories(request: Request) -> list[str]:
	query = request.query_params
	values = []
	values.extend(query.getlist("category"))
	values.extend(query.getlist("category[]"))
	if not values:
		return []
	return [value for raw in values for value in raw.split(",") if value]


def _filtered_workflows(request: Request) -> list[dict[str, Any]]:
	search = request.query_params.get("search", "").strip().lower()
	workflows = _workflows()
	if not search:
		return workflows

	return [workflow for workflow in workflows if search in workflow["name"].lower()]


@router.get("/health")
@router.get("/api/health")
async def health() -> dict[str, str]:
	return {"status": "ok"}


@router.get("/templates/categories")
@router.get("/api/templates/categories")
async def get_template_categories() -> dict[str, list[dict[str, Any]]]:
	return {"categories": CATEGORIES}


@router.get("/templates/collections")
@router.get("/api/templates/collections")
async def get_template_collections(request: Request) -> dict[str, list[dict[str, Any]]]:
	workflows = _filtered_workflows(request)
	collection = {
		"id": 1,
		"name": "Local templates",
		"description": "Templates served by the local backend.",
		"nodes": [NODE_MANUAL_TRIGGER, NODE_SET],
		"workflows": workflows,
		"image": [],
		"categories": CATEGORIES,
		"createdAt": NOW,
		"access": _access_payload("template_collection", 1),
	}
	return {"collections": [collection]}


@router.get("/templates/search")
@router.get("/api/templates/search")
async def search_templates(request: Request) -> dict[str, Any]:
	page = int(request.query_params.get("page", "1"))
	limit = int(request.query_params.get("limit", "20"))
	selected_categories = _selected_categories(request)
	workflows = _filtered_workflows(request)

	if selected_categories:
		valid_category_ids = {str(category["id"]) for category in CATEGORIES}
		if not any(category in valid_category_ids for category in selected_categories):
			workflows = []

	start = max(page - 1, 0) * limit
	end = start + limit

	return {
		"totalWorkflows": len(workflows),
		"workflows": workflows[start:end],
		"filters": [],
	}


@router.get("/templates/collections/{collection_id}")
@router.get("/api/templates/collections/{collection_id}")
async def get_template_collection(collection_id: str) -> dict[str, Any]:
	return {
		"collection": {
			"id": _numeric_id(collection_id),
			"name": "Local templates",
			"description": "Templates served by the local backend.",
			"nodes": [NODE_MANUAL_TRIGGER, NODE_SET],
			"workflows": _workflows(),
			"image": [],
			"categories": CATEGORIES,
			"createdAt": NOW,
			"access": _access_payload("template_collection", collection_id),
		}
	}


@router.get("/templates/workflows/{template_id}")
@router.get("/api/templates/workflows/{template_id}")
async def get_template_workflow(template_id: str) -> dict[str, Any]:
	return {"workflow": _template_full(template_id)}


@router.get("/workflows/templates/{template_id}")
@router.get("/api/workflows/templates/{template_id}")
async def get_workflow_template(template_id: str) -> dict[str, Any]:
	template = _template_full(template_id)
	return {
		"id": template["id"],
		"name": template["name"],
		"workflow": template["workflow"],
		"access": _access_payload("workflow_template", template["id"]),
	}


@router.get("/content/access/{content_type}/{content_id}")
@router.get("/api/content/access/{content_type}/{content_id}")
async def get_content_access(content_type: str, content_id: str) -> dict[str, Any]:
	return _access_payload(content_type, content_id)


@router.post("/content/access/check")
@router.post("/api/content/access/check")
async def check_content_access(request: Request) -> dict[str, Any]:
	try:
		body = await request.json()
	except Exception:
		body = {}
	if not isinstance(body, dict):
		body = {}

	content_type = str(body.get("contentType", body.get("type", "content")))
	content_id = str(body.get("contentId", body.get("id", "unknown")))
	return _access_payload(content_type, content_id)


@router.get("/pricing")
async def pricing_page() -> HTMLResponse:
	return _page("Pricing", "Plans are stubbed locally. Access is granted for all content.")


@router.get("/integrations")
async def integrations_page() -> HTMLResponse:
	return _page("Integrations", "Integration content is available in local stub mode.")


@router.get("/careers")
async def careers_page() -> HTMLResponse:
	return _page("Careers", "Careers content placeholder served by the local backend.")


@router.get("/workflows")
@router.get("/workflows/{path:path}")
async def workflows_page(path: str = "") -> HTMLResponse:
	title = "Workflow Templates"
	message = "Workflow pages are served locally. API data is available under /api/templates/*."
	if path:
		message = f"Workflow page placeholder for {path}."
	return _page(title, message)


@router.get("/blog/rss")
async def blog_rss() -> Response:
	rss = f"""<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0">
	<channel>
		<title>Local n8n Blog</title>
		<link>http://localhost/blog/rss</link>
		<description>Local placeholder RSS feed</description>
		<item>
			<title>Local content service is running</title>
			<link>http://localhost/workflows</link>
			<description>Payment and access checks are stubbed for local development.</description>
			<pubDate>{datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")}</pubDate>
		</item>
	</channel>
</rss>"""
	return Response(content=rss, media_type="application/rss+xml")


@router.get("/api/versions/{current_version}")
async def get_versions(current_version: str) -> list[dict[str, Any]]:
	return [
		{
			"name": current_version,
			"nodes": [],
			"createdAt": NOW,
			"description": "Current local version",
			"documentationUrl": "",
			"hasBreakingChange": False,
			"hasSecurityFix": False,
			"hasSecurityIssue": False,
			"securityIssueFixVersion": "",
		}
	]


@router.get("/api/whats-new")
async def get_whats_new() -> dict[str, Any]:
	return {
		"title": "",
		"calloutText": "",
		"footer": "",
		"items": [],
		"createdAt": NOW,
		"updatedAt": None,
	}


@router.get("/api/banners")
async def get_banners() -> list[dict[str, Any]]:
	return []


def _page(title: str, message: str) -> HTMLResponse:
	html = f"""<!doctype html>
<html lang="en">
	<head>
		<meta charset="utf-8" />
		<meta name="viewport" content="width=device-width, initial-scale=1" />
		<title>{title}</title>
	</head>
	<body>
		<h1>{title}</h1>
		<p>{message}</p>
	</body>
</html>"""
	return HTMLResponse(html)
