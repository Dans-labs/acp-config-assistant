import json
import logging
import os
import sys

# Add the src directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from contextlib import asynccontextmanager
from typing import Annotated

import emoji
import jmespath
import uvicorn
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from keycloak import KeycloakOpenID, KeycloakAuthenticationError
from starlette import status
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.cors import CORSMiddleware

from src.aca import protected, public
from src.aca.commons import data, app_settings, installed_repos_configs, project_details
from akmi_utils import commons as a_commons

api_keys = [app_settings.ACP_CONFIG_ASSISTANT_SERVICE_API_KEY]
security = HTTPBearer()

APP_NAME = os.environ.get("APP_NAME", "ACP Config Assistant Service")
EXPOSE_PORT = os.environ.get("EXPOSE_PORT", 2810)
OTLP_GRPC_ENDPOINT = os.environ.get("OTLP_GRPC_ENDPOINT", "http://localhost:4317")


def auth_header(
    request: Request,
    auth_cred: Annotated[HTTPAuthorizationCredentials, Depends(security)],
):
    if not auth_cred or auth_cred.credentials not in api_keys:
        auth_env_name = request.headers.get("auth-env-name", "local")
        keycloak_env = app_settings.get(f"keycloak_{auth_env_name}")
        if not keycloak_env:
            logging.error("Keycloak environment not found")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Forbidden"
            )

        keycloak_openid = KeycloakOpenID(
            server_url=keycloak_env.URL,
            client_id=keycloak_env.CLIENT_ID,
            realm_name=keycloak_env.REALMS,
        )
        try:
            keycloak_openid.userinfo(auth_cred.credentials)
            logging.info("Keycloak authentication successful")
        except KeycloakAuthenticationError:
            logging.error("Keycloak authentication failed")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Forbidden"
            )
        except Exception as e:
            logging.error(f"Unexpected error during Keycloak authentication: {e}")

@asynccontextmanager
async def lifespan(application: FastAPI):
    logging.info("start up")
    installed_repos_configs()
    print(f"Available repositories configurations: {sorted(list(data.keys()))}")
    logging.info(f"Available repositories configurations: {sorted(list(data.keys()))}")
    logging.info(emoji.emojize(":thumbs_up:"))
    with open(app_settings.repo_file_types) as file:
        file_types = json.load(file)
    values = jmespath.search("[*].value", file_types)
    data.update({"file-types": values})
    yield


build_date = os.environ.get("BUILD_DATE", "unknown")
app = FastAPI(
    title=project_details['title'],
    description=project_details['description'],
    version=f"{project_details['version']} (Build Date: {build_date})",
    lifespan=lifespan
)

LOG_FILE = app_settings.LOG_FILE
log_config = uvicorn.config.LOGGING_CONFIG
logging.basicConfig(
    filename=app_settings.LOG_FILE, level=app_settings.LOG_LEVEL, format=app_settings.LOG_FORMAT
)

if app_settings.otlp_enable is False:
    logging.info("Logging configured without OTLP")
else:
    logging.info("OTLP enabled")
    a_commons.set_otlp(app, APP_NAME, OTLP_GRPC_ENDPOINT, LOG_FILE, log_config)


@app.exception_handler(StarletteHTTPException)
async def custom_404_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        return JSONResponse(status_code=404, content={"message": "Endpoint not found"})
    return JSONResponse(status_code=exc.status_code, content={"message": exc.detail})


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(public.router, tags=["Public"], prefix="")

app.include_router(
    protected.router, tags=["Protected"], prefix="", dependencies=[Depends(auth_header)]
)


if __name__ == "__main__":
    logging.info(f"RAS: Starting the app __main__ with OTLP: {app_settings.otlp_enable}")
    uvicorn.run(app, host="0.0.0.0", port=EXPOSE_PORT, log_config=log_config)
