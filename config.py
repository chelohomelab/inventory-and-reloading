from fastapi.templating import Jinja2Templates

UPLOAD_DIR = "static/uploads"
templates = Jinja2Templates(directory="templates")
