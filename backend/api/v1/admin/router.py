from fastapi import APIRouter, Depends

from api.v1.admin import audit, stats, users
from dependencies.providers import require_admin

# Router-level guard: a route added later is protected whether or not its author
# remembers to ask for it. FastAPI caches the result within a request, so routes that
# additionally declare FreshAdminDep do not re-run the database read.
router = APIRouter(
    prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)]
)
router.include_router(users.router)
router.include_router(audit.router)
router.include_router(stats.router)
