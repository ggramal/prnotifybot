import os

class ConfigException(Exception):
    pass


def check_config():
    if not (
        TG_API_ID
        and TG_API_HASH
    ):
        raise ConfigException(
            """
            TG_API_ID
            TG_API_HASH
            env vars must be set
            """
        )


TG_API_ID = os.getenv("TG_API_ID")
TG_API_HASH = os.getenv("TG_API_HASH")

check_config()
