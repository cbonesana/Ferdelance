from .tables import Artifact, Client, ClientApp, ClientEvent, ClientToken, Setting, Task, ClientTaskEvent, Model, ClientDataSource, ClientFeature, ClientTask

from sqlalchemy.orm import Session

import logging

LOGGER = logging.getLogger(__name__)


def init_content(db: Session) -> None:
    """Initialize all tables in the database.

    :param db:
        Session with the connection to the database.
    """

    logging.info('Database creation started')

    engine = db.get_bind()

    Client.__table__.create(bind=engine, checkfirst=True)
    Setting.__table__.create(bind=engine, checkfirst=True)
    ClientToken.__table__.create(bind=engine, checkfirst=True)
    ClientEvent.__table__.create(bind=engine, checkfirst=True)
    ClientApp.__table__.create(bind=engine, checkfirst=True)
    Artifact.__table__.create(bind=engine, checkfirst=True)
    Task.__table__.create(bind=engine, checkfirst=True)
    ClientTask.__table__.create(bind=engine, checkfirst=True)
    ClientTaskEvent.__table__.create(bind=engine, checkfirst=True)
    Model.__table__.create(bind=engine, checkfirst=True)
    ClientDataSource.__table__.create(bind=engine, checkfirst=True)
    ClientFeature.__table__.create(bind=engine, checkfirst=True)

    db.commit()

    server_exists_query = db.query(Client).filter(Client.client_id=="SERVER").first()

    if server_exists_query is None:
        
        server_client: Client = Client(
            client_id="SERVER",
            machine_system="SERVER",
            machine_mac_address="SERVER",
            machine_node="SERVER",
            ip_address="localhost"
        )

        db.add(server_client)
        db.commit()

    LOGGER.info('Database creation completed')
