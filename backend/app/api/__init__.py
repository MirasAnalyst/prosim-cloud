from fastapi import APIRouter

from app.api.routes import projects, flowsheets, simulation, agent, compounds, chat

api_router = APIRouter(prefix="/api")
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(flowsheets.router, prefix="/projects", tags=["flowsheets"])
api_router.include_router(chat.router, prefix="/projects", tags=["chat"])
api_router.include_router(simulation.router, prefix="/simulation", tags=["simulation"])
api_router.include_router(agent.router, prefix="/agent", tags=["agent"])
api_router.include_router(compounds.router, prefix="/compounds", tags=["compounds"])
