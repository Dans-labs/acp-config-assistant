import json
import hashlib
import logging
import os
from typing import Union

import jmespath
import requests
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic_core import ValidationError

from json_logic import jsonLogic

from src.aca.commons import app_settings, data, installed_repos_configs, project_details
from src.aca.models import repository_assistant_config as ras

from src.aca.models.request_advice_model import RepositoryAdviceModel

router = APIRouter()


def _iter_repo_config_paths() -> list[str]:
    return sorted(
        os.path.join(app_settings.repositories_conf_dir, entry)
        for entry in os.listdir(app_settings.repositories_conf_dir)
        if entry.endswith(".json")
    )


def _read_repo_config_file(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def _repo_config_name(repo_conf_json: dict, fallback_path: str | None = None) -> str:
    return (
        repo_conf_json.get("assistant-config-name")
        or repo_conf_json.get("name")
        or (os.path.splitext(os.path.basename(fallback_path))[0] if fallback_path else "")
    )


def _find_repo_config_file(name: str) -> str | None:
    for repo_conf_path in _iter_repo_config_paths():
        repo_conf_json = _read_repo_config_file(repo_conf_path)
        if _repo_config_name(repo_conf_json, repo_conf_path) == name:
            return repo_conf_path
    return None


def _refresh_repo_cache() -> None:
    data.clear()
    installed_repos_configs()


@router.get("/refresh", include_in_schema=False)
async def do_refresh():
    logging.debug("do_refresh")
    logging.debug(f"Before clear: {list(data.keys())}")
    logging.debug("clear the data")
    data.clear()
    logging.debug(f"After clear: {list(data.keys())}")
    installed_repos_configs()
    logging.debug(f"Available repositories configurations: {sorted(list(data.keys()))}")
    repos = [akm for akm in list(data.keys())]
    logging.debug(project_details["version"])
    logging.debug(f"After refresh: {list(data.keys())}")
    return {"repositories": repos}


@router.get("/name/{name}", summary="Get repository configuration by name")
def get_name_from_repositories_list(name: str):
    """
    Retrieve the full assistant configuration for a named repository.

    Looks up the repository identified by `name` in the in-memory configuration
    store and returns its complete assistant data model serialised as JSON.
    Returns 404 if the name is not found.
    """
    logging.debug(f"get_name_from_repositories_list - name: {name}")
    logging.debug(f"{data.keys()}")
    if name in data.keys():
        logging.debug(f"{name} FOUND")
        try:
            return data[name].model_dump_json(by_alias=True, exclude_none=True)
        except Exception as e:
            logging.error(f"{name} does not {e}")
    else:
        logging.debug(f"{name} does not exist")
    raise HTTPException(404, f"{name} not found")


def _resolve_repo_config(name: str) -> ras.RepoAssistantDataModel:
    if name not in data.keys():
        logging.debug(f"{name} does not exist")
        raise HTTPException(404, f"{name} not found")

    return data[name]


def _config_version_hash(config: ras.RepoAssistantDataModel) -> str:
    serialized = json.dumps(
        config.model_dump(by_alias=True, exclude_none=True),
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha1(serialized.encode("utf-8")).hexdigest()


@router.get("/name/{name}/version/{version}", summary="Get repository configuration at a specific version")
def get_name_with_version(name: str, version: str):
    """
    Retrieve a repository assistant configuration pinned to a specific content version.

    The `version` parameter is matched against a SHA-1 hash derived from the
    serialised configuration. The check is prefix-based, so a short version
    prefix (e.g. the first 7 characters) is sufficient. Returns 404 when the
    name is not found or the hash does not match the current configuration.
    """
    repo_config = _resolve_repo_config(name)
    resolved_version = _config_version_hash(repo_config)

    if not resolved_version.startswith(version):
        raise HTTPException(
            status_code=404,
            detail=(
                f"{name} version {version} not found; "
                f"current version is {resolved_version}"
            ),
        )

    return repo_config.model_dump_json(by_alias=True, exclude_none=True)


@router.post("/seek-advice", status_code=200, summary="Get repository recommendations")
async def get_repo_advices(submitted_repo_data: Request):
    """
    Recommend suitable repositories for a dataset based on its metadata attributes.

    Accepts a JSON payload describing the dataset (affiliation, domain, file type,
    etc.), consults an external metadata transformer to resolve the scientific
    domain, and applies rule-based logic to select the best matching repositories
    from the available configuration. Returns a list of repository advice objects.

    The request body must be `application/json` and conform to the
    `RepositoryAdviceModel` schema.
    """
    content_type = submitted_repo_data.headers["Content-Type"]
    if content_type != "application/json":
        raise HTTPException(
            status_code=400, detail=f"Content type {content_type} not supported"
        )

    repo_conf_json = await submitted_repo_data.json()
    try:
        repo_advice = RepositoryAdviceModel.model_validate(repo_conf_json)
    except ValidationError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Repository Configuration {e.with_traceback(e.__traceback__)}",
        )

    logging.debug(f"repo_advice: {repo_advice.model_dump_json(by_alias=True)}")
    transformer_headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {app_settings.DANS_TRANSFORMER_SERVICE_API_KEY}",
    }
    narcis_domain_req = requests.post(
        app_settings.transformer_url,
        headers=transformer_headers,
        data=repo_advice.model_dump_json(),
    )
    if narcis_domain_req.status_code != 200:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve the domain")

    transformed_metadata = narcis_domain_req.json()
    domain = transformed_metadata.get("result", None)
    file_type = repo_advice.file_type
    # Check whether the file type is in the list of datq keys
    if file_type and file_type not in data.get("file-types"):
        raise HTTPException(
            status_code=400, detail=f"The given file type '{file_type}'not found"
        )

    # Read the JSON file
    if file_type:
        with open(app_settings.REPO_FILE_TYPES, mode="r", encoding="utf-8") as json_file:
            file_types_list = json.load(json_file)
            # Use jmespath to search for the label corresponding to the given value
            file_type_label = jmespath.search(
                f"[?value=='{file_type}'].label | [0]", file_types_list
            )
        if not file_type_label:
            raise HTTPException(
                status_code=400, detail=f"The given file type '{file_type}' not found"
            )

    institution_name_req = requests.get(
        f"https://api.ror.org/organizations{repo_advice.affiliation.path}"
    )
    if institution_name_req.status_code != 200:
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve the institution name"
        )

    institution_name = institution_name_req.json().get("name", None)
    rule = {"and": []}

    logging.debug(f"transformed_metadata: {institution_name}")

    if institution_name in app_settings.INSTITUTION_LIST:
        institution_condition = {"==": [{"var": "Institution"}, institution_name]}
    else:
        institution_condition = {"==": [{"var": "Institution"}, "Any"]}
    rule["and"].append(institution_condition)

    logging.debug(f"file_type: {file_type}")
    if file_type:
        file_type_condition = {"==": [{"var": "File Type"}, file_type_label]}
    else:
        file_type_condition = {"==": [{"var": "File Type"}, "Any"]}

    logging.debug(f"domain: {domain}")
    rule["and"].append(file_type_condition)
    if domain in app_settings.DOMAIN_LIST:
        domain_condition = {"==": [{"var": "Domain"}, domain]}
    else:
        domain_condition = {"==": [{"var": "Domain"}, "Any"]}
    rule["and"].append(domain_condition)

    logging.debug(f"rule: {rule}")

    with open(app_settings.repo_available_list, mode="r", encoding="utf-8") as json_file:
        repo_available_list = json.load(json_file)

    results = [
        item["Repository/ Pipeline"]
        for item in repo_available_list
        if jsonLogic(rule, item)
    ]

    logging.debug(f"results: {results}")
    advice = []
    directory_path = app_settings.REPOSITORIES_SCHEMA_DIR
    # List all files in the directory and filter by extension
    filtered_files = [
        file for file in os.listdir(directory_path) if file.endswith(".json")
    ]
    for file in filtered_files:
        with open(os.path.join(directory_path, file), "r") as f:
            advice_schema = json.load(f)
            if advice_schema.get("Dataverse.NL"):
                advice_schema = advice_schema["Dataverse.NL"]
                advice.append(advice_schema)
            else:
                if results:
                    a = advice_schema.get(results[0], None)
                    if a:
                        advice.append(a)

    return {"advice": advice}


@router.post("/upload-repo", status_code=201, summary="Upload a new repository configuration")
async def upload_repository(
    submitted_repo_conf: Request, overwrite: Union[bool, None] = False
):
    """
    Register a new repository assistant configuration.

    Accepts a JSON body that conforms to the `RepoAssistantDataModel` schema,
    validates it, and persists it as a JSON file in the configured repositories
    directory. The in-memory configuration cache is refreshed immediately after
    saving so that the new entry is available without a service restart.

    Set `overwrite=true` to replace an existing configuration with the same
    `assistant-config-name`. By default an HTTP 400 is returned if the name
    already exists.
    """
    content_type = submitted_repo_conf.headers["Content-Type"]
    if not content_type.startswith("application/json"):
        raise HTTPException(
            status_code=400, detail=f"Content type {content_type} not supported"
        )

    repo_conf_json = await submitted_repo_conf.json()
    try:
        repo_assistant = ras.RepoAssistantDataModel.model_validate(repo_conf_json)
        if not overwrite and repo_assistant.assistant_config_name in data.keys():
            raise HTTPException(
                status_code=400,
                detail=f'Repository Configuration "'
                f'{repo_assistant.assistant_config_name}" exist.'
                f'You can use "/upload-repo?overwrite=true"',
            )
        else:
            with open(
                os.path.join(
                    app_settings.repositories_conf_dir,
                    f"{repo_assistant.assistant_config_name}.json",
                ),
                mode="w+",
                encoding="utf-8",
            ) as file:
                json.dump(repo_conf_json, file, indent=2, ensure_ascii=False)
            _refresh_repo_cache()
            return {"saved-conf": repo_assistant.assistant_config_name}
    except ValidationError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Repository Configuration {e.with_traceback(e.__traceback__)}",
        )


@router.delete("/delete-repo/{name}", summary="Delete a repository configuration")
def delete_repository(name: str):
    """
    Remove a repository assistant configuration by name.

    Locates the JSON configuration file for the given `name`, deletes it from
    disk and refreshes the in-memory cache. Returns 404 if no configuration
    with that name exists.
    """
    repo_conf_path = _find_repo_config_file(name)
    if repo_conf_path is None:
        raise HTTPException(status_code=404, detail=f"'{name}' not found.")
    os.remove(repo_conf_path)
    _refresh_repo_cache()
    return {"deleted": name}

@router.get("/list-apps", summary="List available application names")
def list_apps():
    """
    Return a sorted list of registered application names.

    Application names are used to identify which database and bridge-plugin
    context a request belongs to. This endpoint is useful for administrative
    tooling that needs to enumerate all active applications in the platform.
    """
    app_names = data.get("app_names")
    return sorted(app_names)


@router.get("/editor/configs", include_in_schema=False)
def list_editor_configs():
    configs = []
    for repo_conf_path in _iter_repo_config_paths():
        repo_conf_json = _read_repo_config_file(repo_conf_path)
        configs.append(
            {
                "name": _repo_config_name(repo_conf_json, repo_conf_path),
                "file-name": os.path.basename(repo_conf_path),
            }
        )
    configs.sort(key=lambda item: item["name"])
    return {"configs": configs}


@router.get("/editor/configs/{name}", include_in_schema=False)
def get_editor_config(name: str):
    repo_conf_path = _find_repo_config_file(name)
    if repo_conf_path is None:
        raise HTTPException(status_code=404, detail=f"'{name}' not found.")
    return JSONResponse(content=_read_repo_config_file(repo_conf_path))


@router.put("/editor/configs/{source_name}", include_in_schema=False)
async def save_editor_config(source_name: str, submitted_repo_conf: Request):
    content_type = submitted_repo_conf.headers["Content-Type"]
    if not content_type.startswith("application/json"):
        raise HTTPException(
            status_code=400, detail=f"Content type {content_type} not supported"
        )

    repo_conf_json = await submitted_repo_conf.json()
    try:
        repo_assistant = ras.RepoAssistantDataModel.model_validate(repo_conf_json)
    except ValidationError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Repository Configuration {e.with_traceback(e.__traceback__)}",
        )

    target_name = repo_assistant.assistant_config_name
    source_path = _find_repo_config_file(source_name)
    target_path = os.path.join(
        app_settings.repositories_conf_dir,
        f"{target_name}.json",
    )
    existing_target_path = _find_repo_config_file(target_name)
    if existing_target_path and source_path != existing_target_path and source_name != target_name:
        raise HTTPException(
            status_code=409,
            detail=f"Repository Configuration '{target_name}' already exists.",
        )

    if source_path and os.path.abspath(source_path) != os.path.abspath(target_path):
        os.remove(source_path)

    with open(target_path, "w", encoding="utf-8") as file:
        json.dump(repo_conf_json, file, indent=2, ensure_ascii=False)

    _refresh_repo_cache()
    return {"saved-conf": target_name, "file-name": os.path.basename(target_path)}