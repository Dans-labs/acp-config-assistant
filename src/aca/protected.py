import json
import logging
import os
from typing import Union

import jmespath
import requests
from fastapi import APIRouter, Request, HTTPException
from pydantic_core import ValidationError

from json_logic import jsonLogic

from src.aca.commons import app_settings, data, installed_repos_configs, project_details
from akmi_utils.models import ras

from src.aca.models.request_advice_model import RepositoryAdviceModel

router = APIRouter()


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


@router.get("/name/{name}")
def get_name_from_repositories_list(name: str):
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


@router.post("/seek-advice", status_code=200)
async def get_repo_advices(submitted_repo_data: Request):
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


@router.post("/upload-repo", status_code=201)
async def upload_repository(
    submitted_repo_conf: Request, overwrite: Union[bool, None] = False
):
    content_type = submitted_repo_conf.headers["Content-Type"]
    if content_type != "application/json":
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
            data.update({repo_assistant.assistant_config_name: repo_assistant})
            with open(
                os.path.join(
                    app_settings.repositories_conf_dir,
                    f"{repo_assistant.assistant_config_name}.json",
                ),
                mode="w+",
            ) as file:
                file.write(json.dumps(repo_conf_json))
            return {"saved-conf": repo_assistant.assistant_config_name}
    except ValidationError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Repository Configuration {e.with_traceback(e.__traceback__)}",
        )


@router.delete("/delete-repo/{name}")
def delete_repository(name: str):
    if name not in data:
        raise HTTPException(status_code=404, detail=f"'{name}' not found.")

    for repo_conf_filename in os.listdir(app_settings.repositories_conf_dir):
        repo_conf_file = os.path.join(
            app_settings.repositories_conf_dir, repo_conf_filename
        )
        with open(repo_conf_file, "r") as f:
            repo_conf_json = json.loads(f.read())
            if repo_conf_json["name"] == name:
                os.remove(repo_conf_json)
                data.pop(name)
                return {"deleted": name}

@router.get("/list-apps")
def list_apps():
    app_names = data.get("app_names")
    return sorted(app_names)