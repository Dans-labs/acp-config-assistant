from __future__ import annotations

from enum import StrEnum, auto
from typing import Optional

from pydantic import BaseModel, HttpUrl, Field


class DepositType(StrEnum):
    """
    Enum representing different types of deposits.

    Attributes:
    - DATASET: Represents a dataset deposit.
    - CODE: Represents a code deposit.
    - REPORT: Represents a report deposit.
    - PUBLICATION: Represents a publication deposit.
    """
    DATASET = auto()
    CODE = auto()
    REPORT = auto()
    PUBLICATION = auto()


class RepositoryAdviceModel(BaseModel):
    """
    Represents the model for repository advice.

    Attributes:
    - affiliation (HttpUrl): The URL of the affiliation.
    - domain (HttpUrl): The URL of the domain.
    - deposit_type (DepositType): The type of deposit, with an alias 'deposit-type'.
    - file_type (Optional[str]): The type of file, with an alias 'file-type'. Defaults to None.
    """
    affiliation: HttpUrl
    domain: HttpUrl
    deposit_type: DepositType = Field(..., alias='deposit-type')
    file_type: Optional[str] = Field(None, alias='file-type')