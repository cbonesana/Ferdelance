"""Implementation of the CLI features regarding models
"""

from typing import List

import pandas as pd

from ....database import DataBase
from ....database.schemas import Model
from ....database.services import ModelService
from ...visualization import show_many, show_one


async def list_models(artifact_id: str | None = None) -> List[Model]:
    """Print model list, with or without filters on ARTIFACT_ID, MODEL_ID"""
    # TODO depending on 1:1, 1:n relations with artifacts arguments change or disappear

    db = DataBase()
    async with db.async_session() as session:

        model_service = ModelService(session)

        if artifact_id is not None:
            models: list[Model] = await model_service.get_models_by_artifact_id(artifact_id)
        else:
            models: list[Model] = await model_service.get_model_list()

        show_many(models)

        return models


async def describe_model(model_id: str | None = None) -> Model:
    """Describe single model by printing its db record.

    Args:
        model_id (str): Unique ID of the model

    Raises:
        ValueError: if no model id is provided

    Returns:
        Model: the Model object
    """

    if model_id is None:
        raise ValueError("Provide a Model ID")

    db = DataBase()
    async with db.async_session() as session:

        model_service = ModelService(session)

        model: Model | None = await model_service.get_model_by_id(model_id)

        if model is None:
            print(f"No model found with id {model_id}")
        else:
            show_one(model)

        return model
