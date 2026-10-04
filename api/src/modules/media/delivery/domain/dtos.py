from pydantic import BaseModel


class MediaCaption(BaseModel):
    job_id: int
    position: int
    total: int
    title: str
    source_url: str
    provider: str
