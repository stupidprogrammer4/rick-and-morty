from typing import Literal

from pydantic import BaseModel, Field


class AssetChartPolicy(BaseModel):
    enabled: bool = False
    window: Literal["daily", "weekly", "monthly"] = "daily"
    width: int = Field(default=1000, ge=640, le=1400)
    height: int = Field(default=760, ge=480, le=1000)
    background: str = Field(default="#101827", pattern=r"^#[0-9a-fA-F]{6}$")
    foreground: str = Field(default="#e5edf8", pattern=r"^#[0-9a-fA-F]{6}$")
    rising: str = Field(default="#34d399", pattern=r"^#[0-9a-fA-F]{6}$")
    falling: str = Field(default="#fb7185", pattern=r"^#[0-9a-fA-F]{6}$")
    line_label: str = Field(default="Close price", max_length=100)
    ohlc_label: str = Field(default="OHLC", max_length=100)
    unit_label: str = Field(default="Toman", max_length=50)
    empty_label: str = Field(default="No recorded candles", max_length=100)
    footer: str = Field(
        default="Calculated asset price | Closed candles", max_length=200
    )
    caption: str = Field(
        default="📈 نمودار خطی و OHLC؛ بر اساس قیمت محاسبه‌شدهٔ دارایی",
        max_length=300,
    )
    asset_labels: dict[str, str] = Field(default_factory=dict)
    asset_symbols: dict[str, str] = Field(default_factory=dict)
