from abc import abstractmethod
from typing import Any

from ferdelance.core.entity import Entity
from ferdelance.core.environment.core import Environment
from ferdelance.core.queries import Query


class Operation(Entity):
    data_names: list[str] = list()  # variables from local data
    env_names: list[str] = list()  # variables in the environment

    random_seed: Any = (None,)

    @abstractmethod
    def exec(self, env: Environment) -> Environment:
        raise NotImplementedError()


class QueryOperation(Operation):
    query: Query | None = None


class DoNothing(Operation):
    def exec(self, env: Environment) -> Environment:
        return env
