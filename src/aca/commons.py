import json
import logging
import os

import requests
from akmi_utils import commons as a_commons
from dynaconf import Dynaconf
from pydantic import ValidationError
from urllib.parse import urlparse, urlunparse, urlencode
from src.aca.models import repository_assistant_config as ras

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
        if not repo_conf_filename.endswith(".json"):
            continue

        file_path = os.path.join(app_settings.repositories_conf_dir, repo_conf_filename)
        print(f'Processing file: {file_path}')
        logging.info(f"Processing file: {file_path}")
        try:
            with open(file_path) as f:
                saved_repo_assistant = json.load(f)

            repo_assistant = ras.RepoAssistantDataModel.model_validate(saved_repo_assistant)
            if not repo_assistant:
                logging.error(f"Invalid configuration in {repo_conf_filename}")
                continue

            transformed_metadata_urls = [
                convert_transformer_url(transformer.transformer_url)
                for target_repo in repo_assistant.targets
                if target_repo.metadata
                for transformer in (target_repo.metadata.transformed_metadata or [])
                if transformer.transformer_url
            ]

            # Keep assistant configs loadable even when MTS is temporarily unavailable
            # (e.g. ACA starts before MTS in docker compose). We still log failed checks.
            can_be_added = True
            if not transformed_metadata_urls:
                logging.warning(
                    f"{repo_conf_filename} does not define transformed metadata URLs. Loading configuration anyway."
                )
            else:
                has_verified_transformer = False
                for transformer_url in transformed_metadata_urls:
                    try:
                        response = requests.get(transformer_url, timeout=5)
                        if response.status_code == 200 and response.json():
                            has_verified_transformer = True
                            break
                    except requests.RequestException as exc:
                        logging.warning(f"Transformer URL check failed for {transformer_url}: {exc}")
                if not has_verified_transformer:
                    logging.warning(
                        f"{repo_conf_filename} transformer URLs could not be verified at startup. "
                        "Loading configuration anyway."
                    )

            if can_be_added:
                app_names.append(repo_assistant.app_name)
                if repo_assistant.assistant_config_name in data:
                    logging.warning(
                        f"{repo_conf_filename} - Duplicate configuration: {repo_assistant.assistant_config_name}. Overwriting."
                    )
                data[repo_assistant.assistant_config_name] = repo_assistant
                logging.info(f"Loaded configuration: {repo_assistant.assistant_config_name} from {repo_conf_filename}")
            else:
                logging.error(f"Invalid configuration in {repo_conf_filename}")
        except (json.JSONDecodeError, ValidationError) as e:
            logging.error(f"Error processing {repo_conf_filename}: {e}")
            continue
        except Exception as e:
            logging.exception(f"Unexpected error processing {repo_conf_filename}: {e}")
            continue

    data["app_names"] = app_names
    logging.info(f"Available apps: {sorted(app_names)}")


def convert_transformer_url(original_url):
    """
    Converts a transformer URL to the saved XSL list format.

    Args:
        original_url (str | HttpUrl): The original transformer URL.

    Returns:
        str: The converted URL in the saved XSL list format.
    """
    parsed_url = urlparse(str(original_url))
    xslt_name = parsed_url.path.rsplit("/", 1)[-1]  # Extract the last part of the path
    new_query = urlencode({"xslt_name": xslt_name})
    return urlunparse(parsed_url._replace(path="/saved-xsl-list", query=new_query))