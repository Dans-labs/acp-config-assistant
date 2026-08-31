import logging

from fastapi import APIRouter

from src.aca.commons import data, project_details

router = APIRouter()


@router.get("/repositories", summary="List available repository configurations")
def get_repositories_list():
    """
    Return the names of all loaded repository assistant configurations.

    Reads the in-memory configuration store and returns the list of repository
    names that have been successfully loaded at startup or after a refresh.
    Internal entries such as service metadata are excluded from the result.
    """
    logging.debug("get_repositories_list")
    repos = [akm for akm in list(data.keys()) if akm not in {"service-version", "app_names"}]
    return {"repositories": repos}


@router.get("/info", summary="Service information")
def info():
    """
    Return general information about the ACP Config Assistant Service.

    Provides the service title, version and other metadata as defined in the
    project configuration. Useful for health dashboards and service discovery.
    """
    logging.info("Repository Selection and Advice Service")
    logging.debug("info")
    return project_details
