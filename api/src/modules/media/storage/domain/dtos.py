from pydantic import BaseModel


class MediaDiskUsage(BaseModel):
    used_bytes: int
    free_bytes: int


class WorkspaceItem(BaseModel):
    job_id: int
    item_id: int
