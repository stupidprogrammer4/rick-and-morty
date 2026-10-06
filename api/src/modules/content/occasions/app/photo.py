import base64
from functools import lru_cache
from importlib.resources import files

from portal_contracts.telegram import bounded_png


@lru_cache(maxsize=1)
def occasion_photo() -> str:
    image = (
        files("src.modules.content.occasions")
        .joinpath("data/rick-occasions.png")
        .read_bytes()
    )
    return bounded_png(base64.b64encode(image).decode("ascii"))
