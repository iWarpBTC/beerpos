from http import HTTPStatus

from fastapi import Depends, Request
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException
from starlette.responses import HTMLResponse

from lnbits.core.models import User
from lnbits.decorators import check_user_exists
from lnbits.settings import settings

from . import beerpos_ext, beerpos_renderer
from .crud import get_beerpos

templates = Jinja2Templates(directory="templates")


@beerpos_ext.get("/", response_class=HTMLResponse)
async def index(request: Request, user: User = Depends(check_user_exists)):
    return beerpos_renderer().TemplateResponse(
        "beerpos/index.html", {"request": request, "user": user.dict()}
    )


@beerpos_ext.get("/{beerpos_id}")
async def beerpos(request: Request, beerpos_id):
    beerpos = await get_beerpos(beerpos_id)
    if not beerpos:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="BeerPoS does not exist."
        )

    return beerpos_renderer().TemplateResponse(
        "beerpos/beerpos.html",
        {
            "request": request,
            "beerpos": beerpos,
            "web_manifest": f"/beerpos/manifest/{beerpos_id}.webmanifest",
        },
    )


@beerpos_ext.get("/manifest/{beerpos_id}.webmanifest")
async def manifest(beerpos_id: str):
    beerpos = await get_beerpos(beerpos_id)
    if not beerpos:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="BeerPoS does not exist."
        )

    return {
        "short_name": settings.lnbits_site_title,
        "name": beerpos.name + " - " + settings.lnbits_site_title,
        "icons": [
            {
                "src": settings.lnbits_custom_logo
                if settings.lnbits_custom_logo
                else "https://cdn.jsdelivr.net/gh/lnbits/lnbits@0.3.0/docs/logos/lnbits.png",
                "type": "image/png",
                "sizes": "900x900",
            }
        ],
        "start_url": "/beerpos/" + beerpos_id,
        "background_color": "#1F2234",
        "description": "Bitcoin Lightning BeerPoS",
        "display": "standalone",
        "scope": "/beerpos/" + beerpos_id,
        "theme_color": "#1F2234",
        "shortcuts": [
            {
                "name": beerpos.name + " - " + settings.lnbits_site_title,
                "short_name": beerpos.name,
                "description": beerpos.name + " - " + settings.lnbits_site_title,
                "url": "/beerpos/" + beerpos_id,
            }
        ],
    }
