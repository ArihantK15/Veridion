from fastapi import APIRouter, HTTPException, Request, Response

from app_server.admin import _administered_installation_ids, _repo_installation_id
from app_server.auth import get_current_session
from app_server.db import get_recent_history

dashboard_router = APIRouter()


@dashboard_router.get("/app/{org}/{repo}")
async def get_dashboard(org: str, repo: str, request: Request):
    # Session + ownership check first, before any repo lookup - an unauthenticated
    # caller should not learn whether a given org/repo has scan history at all.
    session = await get_current_session(request)
    if session is None:
        raise HTTPException(status_code=401, detail="login required")

    pool = request.app.state.db_pool
    installation_id = await _repo_installation_id(pool, org, repo)

    administered_ids = await _administered_installation_ids(session["github_access_token"])
    if installation_id not in administered_ids:
        raise HTTPException(status_code=403, detail="you do not administer this installation")

    repo_full_name = f"{org}/{repo}"
    history = await get_recent_history(pool, installation_id, repo_full_name)
    return {"repo_full_name": repo_full_name, "history": history}


@dashboard_router.get("/v1/health/{org}/{repo}")
async def get_public_health(org: str, repo: str, request: Request, response: Response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    repo_full_name = f"{org}/{repo}"
    rows = await request.app.state.db_pool.fetch(
        """
        SELECT DISTINCT ON (endpoint_method, endpoint_path)
            endpoint_method, endpoint_path, reachable, status_code, latency_ms, checked_at
        FROM endpoint_health
        WHERE repo_full_name = $1
        ORDER BY endpoint_method, endpoint_path, checked_at DESC, id DESC
        """,
        repo_full_name,
    )
    if not rows:
        raise HTTPException(
            status_code=404,
            detail="no health data for this repo",
            headers={"Access-Control-Allow-Origin": "*"},
        )

    return {
        "repo_full_name": repo_full_name,
        "endpoints": [
            {
                "method": row["endpoint_method"],
                "path": row["endpoint_path"],
                "reachable": row["reachable"],
                "status_code": row["status_code"],
                "latency_ms": float(row["latency_ms"]) if row["latency_ms"] is not None else None,
                "checked_at": row["checked_at"].isoformat(),
            }
            for row in rows
        ],
    }
