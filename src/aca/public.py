import logging

from fastapi import APIRouter

from src.aca.commons import data, project_details

router = APIRouter()


@router.get("/repositories")
def get_repositories_list():
    logging.debug("get_repositories_list")
    repos = [akm for akm in list(data.keys()) if akm not in {"service-version", "app_names"}]
    return {"repositories": repos}


@router.get("/info")
def info():
    logging.info("Repository Selection and Advice Service")
    logging.debug("info")
    return project_details
