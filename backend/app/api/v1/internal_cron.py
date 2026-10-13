"""Lets an outside scheduler trigger the background jobs.

Use this when the host puts the service to sleep while idle (so an in-process timer
can't run), or if you simply prefer a managed cron: call it every few minutes from
cron-job.org, a Render Cron Job, or a GitHub Actions schedule:

    curl -X POST https://<your-backend>/api/v1/internal/cron/run -H "X-Cron-Secret: <CRON_SECRET>"

Each job only runs when it is actually due, so calling this often is harmless. The
endpoint answers 404 unless CRON_SECRET is set.
"""

import hmac

from fastapi import APIRouter, Header, HTTPException, Query, status

from app.core.config import get_settings
from app.services.scheduler import JOBS, run_jobs

router = APIRouter(prefix="/api/v1/internal/cron", tags=["internal"])


@router.post("/run")
async def run(
    x_cron_secret: str | None = Header(default=None),
    jobs: str | None = Query(None, description="Comma-separated job names; default = every job that is due"),
    force: bool = Query(False, description="Run even if not due yet"),
):
    expected = get_settings().cron_secret
    if not expected or not x_cron_secret or not hmac.compare_digest(x_cron_secret, expected):
        # 404, not 401: don't advertise that the endpoint exists.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    names = [j.strip() for j in jobs.split(",") if j.strip()] if jobs else None
    unknown = [n for n in (names or []) if n not in {j.name for j in JOBS}]
    if unknown:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Unknown job(s): {', '.join(unknown)}")
    return {"jobs": await run_jobs(names, force=force)}
