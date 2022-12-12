from pydantic import BaseModel

from ..artifacts import DataSource


class WorkbenchJoinRequest(BaseModel):
    """Data sent by the workbench to join the server."""
    public_key: str


class WorkbenchJoinData(BaseModel):
    """Data sent by the server to a workbench after a successful join."""
    id: str
    token: str
    public_key: str


class WorkbenchClientList(BaseModel):
    client_ids: list[str]


class WorkbenchDataSourceIdList(BaseModel):
    datasource_ids: list[str]


class WorkbenchDataSourceList(BaseModel):
    datasources: list[DataSource]
