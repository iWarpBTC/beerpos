import asyncio

from fastapi import APIRouter

from lnbits.db import Database
from lnbits.helpers import template_renderer
from lnbits.tasks import catch_everything_and_restart

db = Database("ext_beerpos")

beerpos_ext: APIRouter = APIRouter(prefix="/beerpos", tags=["BeerPoS"])
scheduled_tasks: list[asyncio.Task] = []

beerpos_static_files = [
    {
        "path": "/beerpos/static",
        "name": "beerpos_static",
    }
]


def beerpos_renderer():
    return template_renderer(["beerpos/templates"])


from .tasks import wait_for_paid_invoices
from .views import *  # noqa
from .views_api import *  # noqa


def beerpos_start():
    loop = asyncio.get_event_loop()
    task = loop.create_task(catch_everything_and_restart(wait_for_paid_invoices))
    scheduled_tasks.append(task)
