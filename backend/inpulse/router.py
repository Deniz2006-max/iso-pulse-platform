from fastapi import APIRouter
from inpulse.leave.endpoints import router as leave_router
from inpulse.celebrations.endpoints import router as celebrations_router
from inpulse.chat.router import router as chat_router
from inpulse.tasks.endpoints import router as tasks_router
from inpulse.notifications.endpoints import router as notifications_router
from inpulse.orientation.endpoints import router as orientation_router
from inpulse.employees.endpoints import router as employees_router

inpulse_router = APIRouter(prefix="/api/v1/hr", tags=["inpulse"])
inpulse_router.include_router(leave_router, prefix="/leave")
inpulse_router.include_router(celebrations_router, prefix="/celebrations")
inpulse_router.include_router(chat_router, prefix="/chat")
inpulse_router.include_router(tasks_router, prefix="/tasks")
inpulse_router.include_router(notifications_router, prefix="/notifications")
inpulse_router.include_router(orientation_router, prefix="/orientation")
inpulse_router.include_router(employees_router, prefix="/employees")
