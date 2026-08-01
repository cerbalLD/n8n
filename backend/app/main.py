from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import content, license

app = FastAPI(
	title="n8n Local Content Backend",
	version="0.1.0",
	description="Local stub service for content access, templates, and license-related requests.",
)

app.add_middleware(
	CORSMiddleware,
	allow_origins=["*"],
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)

app.include_router(content.router)
app.include_router(license.router)


@app.get("/health")
async def health():
	return {"status": "ok"}
