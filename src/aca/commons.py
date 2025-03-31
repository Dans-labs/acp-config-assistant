import json
import logging
import os

import tomli
from akmi_utils.models import ras
from akmi_utils import commons as a_commons
from dynaconf import Dynaconf
from pydantic import ValidationError

base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["BASE_DIR"] = os.getenv("BASE_DIR", base_dir)

app_settings = Dynaconf(
    settings_files=["conf/settings.toml", "conf/*.yaml", "conf/.secrets.toml"],
    environments=True,
)
data = {}

project_details = a_commons.get_project_details(
    os.getenv("BASE_DIR"), ["name", "version", "description", "title"]
)


def installed_repos_configs():
    logging.debug("startup")
    app_names = []

    for repo_conf_filename in os.listdir(app_settings.repositories_conf_dir):
        if repo_conf_filename.endswith(".json"):
            with open(
                os.path.join(app_settings.repositories_conf_dir, repo_conf_filename)
            ) as f:
                try:
                    logging.info(f"repo_conf_filename: {repo_conf_filename}")
                    saved_repo_assistant = json.loads(f.read())
                    repo_assistant = ras.RepoAssistantDataModel.model_validate(
                        saved_repo_assistant
                    )
                    app_names.append(repo_assistant.app_name)
                    if repo_assistant.assistant_config_name in data:
                        logging.warning(
                            f"Configuration {repo_assistant.assistant_config_name} already exists and will be overwritten."
                        )
                    data.update({repo_assistant.assistant_config_name: repo_assistant})
                    logging.info(
                        f"Loaded valid: {repo_assistant.assistant_config_name} in {repo_conf_filename}"
                    )
                except json.JSONDecodeError as e:
                    logging.error(f"Error loading {repo_conf_filename}: {e}")
                    continue
                except ValidationError as e:
                    logging.error(
                        f">>> Error validating: {repo_conf_filename}, caused by {e}"
                    )
                    continue

    data.update({"app_names": app_names})
    logging.info(f"Available apps : {sorted(app_names)}")