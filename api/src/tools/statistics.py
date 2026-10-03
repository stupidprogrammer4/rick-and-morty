from datetime import datetime

from pydantic import BaseModel


class StatisticsCriteria(BaseModel):
    at: datetime


class StatisticsSnapshot(BaseModel):
    generated_at: datetime
