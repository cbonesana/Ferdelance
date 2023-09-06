from ferdelance.const import TYPE_CLIENT
from ferdelance.logging import get_logger
from ferdelance.node.middlewares import SignedAPIRoute, ValidSessionArgs, valid_session_args
from ferdelance.node.services import ComponentService

from fastapi import APIRouter, Depends, HTTPException

from sqlalchemy.exc import NoResultFound

from ferdelance.schemas.client import ClientUpdate
from ferdelance.schemas.updates import UpdateExecute, UpdateNothing

LOGGER = get_logger(__name__)


client_router = APIRouter(prefix="/client", route_class=SignedAPIRoute)


async def allow_access(args: ValidSessionArgs = Depends(valid_session_args)) -> ValidSessionArgs:
    try:
        if args.component.type_name != TYPE_CLIENT:
            LOGGER.warning(
                f"component_id={args.component.id}: client of type={args.component.type_name} cannot access this route"
            )
            raise HTTPException(403)

        return args
    except NoResultFound:
        LOGGER.warning(f"client_id={args.component.id} not found")
        raise HTTPException(403)


@client_router.get("/")
async def client_home():
    return "Client 🏠"


@client_router.get("/update", response_model=UpdateExecute | UpdateNothing)
async def client_update(
    _: ClientUpdate,
    args: ValidSessionArgs = Depends(allow_access),
) -> UpdateExecute | UpdateNothing:
    """API used by the client to get the updates. Updates can be one of the following:
    - new server public key
    - new artifact package
    - new client app package
    - nothing (keep alive)
    """
    LOGGER.debug(f"client_id={args.component.id}: update request")

    cs: ComponentService = ComponentService(args.session, args.component)

    next_action = await cs.update()

    return next_action
