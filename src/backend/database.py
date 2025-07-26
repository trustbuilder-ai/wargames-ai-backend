from functools import cache
import os
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.ext.automap import AutomapBase, automap_base
from sqlalchemy.orm import Session, sessionmaker

from dotenv import load_dotenv

load_dotenv()

SQLALCHEMY_URL: str = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"


@cache
def get_sqlalchemy_engine(sqlalchemy_url: str) -> Engine:
    # pool_recycle addresses mysql connection errors when the the mysql side has closed
    # the connection. This is a common issue with mysql and sqlalchemy.
    # https://stackoverflow.com/questions/26891971/mysql-connection-not-available-when-use-sqlalchemymysql-and-flask
    # https://docs.sqlalchemy.org/en/20/core/engines.html#sqlalchemy.create_engine.params.pool_recycle
    return create_engine(sqlalchemy_url, pool_recycle=3600)


def get_sqlalchemy_session(engine: Optional[Engine] = None) -> Session:
    if engine is None:
        engine: Engine = get_sqlalchemy_engine(SQLALCHEMY_URL)

    # Set up a session
    return sessionmaker(bind=engine)()


@cache
def get_sqlalchemy_base(engine: Optional[Engine] = None) -> AutomapBase:
    if engine is None:
        engine: Engine = get_sqlalchemy_engine(SQLALCHEMY_URL)
    Base: AutomapBase = automap_base()
    Base.prepare(autoload_with=engine)
    return Base
