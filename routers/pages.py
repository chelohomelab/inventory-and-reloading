from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from fastapi import Request
from config import templates

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "user": request.state.user})


@router.get("/index.html", response_class=HTMLResponse)
async def index_explicit(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "user": request.state.user})


@router.get("/firearm-detail.html", response_class=HTMLResponse)
async def firearm_detail(request: Request):
    return templates.TemplateResponse("firearm-detail.html", {"request": request, "user": request.state.user})


@router.get("/ammo-detail.html", response_class=HTMLResponse)
async def ammo_detail(request: Request):
    return templates.TemplateResponse("ammo-detail.html", {"request": request, "user": request.state.user})


@router.get("/tc-barrel-detail.html", response_class=HTMLResponse)
async def tc_barrel_detail(request: Request):
    return templates.TemplateResponse("tc-barrel-detail.html", {"request": request, "user": request.state.user})
