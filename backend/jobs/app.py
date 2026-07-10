import procrastinate

from api.config import get_settings

connector = procrastinate.PsycopgConnector(conninfo=get_settings().database_url)

app = procrastinate.App(connector=connector)
