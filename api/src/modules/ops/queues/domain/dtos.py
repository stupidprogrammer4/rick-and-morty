from pydantic import BaseModel


class TaskStreams(BaseModel):
    main: str
