import os


class ConfigException(Exception):
    pass


def check_config():
    if not (TG_API_ID and TG_API_HASH and TG_CHAT_NAME):
        raise ConfigException(
            """
            TG_API_ID
            TG_API_HASH
            TG_CHAT_NAME
            env vars must be set
            """
        )


TG_API_ID = os.getenv("TG_API_ID")
TG_API_HASH = os.getenv("TG_API_HASH")
TG_CHAT_NAME = os.getenv("TG_CHAT_NAME")
WH_SECRET = os.getenv("WH_SECRET", None)
TIMEZONE = os.getenv("TIMEZONE", 'UTC')

check_config()
