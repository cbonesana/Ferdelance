from ferdelance.cli.fdl_suites.clients.functions import describe_client, list_clients
from ferdelance.database import AsyncSession
from ferdelance.database.tables import Component
from ferdelance.schemas.components import Client as ClientView

import pytest


@pytest.mark.asyncio
async def test_list_clients(session: AsyncSession):
    c1: Component = Component(
        id="C1",
        version="test",
        public_key="1",
        machine_system="1",
        machine_mac_address="1",
        machine_node="1",
        ip_address="1",
        type_name="CLIENT",
    )

    c2: Component = Component(
        id="C2",
        version="test",
        public_key="2",
        machine_system="2",
        machine_mac_address="2",
        machine_node="2",
        ip_address="2",
        type_name="CLIENT",
    )

    session.add(c1)

    session.add(c2)

    await session.commit()

    res: list[ClientView] = await list_clients()

    assert len(res) == 2


@pytest.mark.asyncio
async def test_describe_client(session: AsyncSession):
    c1: Component = Component(
        id="C1",
        version="test",
        public_key="1",
        machine_system="1",
        machine_mac_address="1",
        machine_node="1",
        ip_address="1",
        type_name="CLIENT",
    )
    session.add(c1)

    await session.commit()

    res: ClientView | None = await describe_client(client_id=c1.id)

    assert res is not None
    assert isinstance(res, ClientView)
    assert res.id == "C1"
    assert res.version == "test"

    res = await describe_client(client_id="do not exist")
    assert res is None
