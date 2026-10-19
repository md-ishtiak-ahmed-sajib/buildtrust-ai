"""Compose feature routers while preserving the public upgrade URLs."""

from fastapi import APIRouter
from .price_api import create_router as price_router
from .measurement_api import create_router as measurement_router
from .estimate_api import create_router as estimate_router
from .copilot_api import create_router as copilot_router


def create_router(context):
    router = APIRouter()
    for create in (price_router, measurement_router, estimate_router, copilot_router):
        router.include_router(create(context))
    return router
