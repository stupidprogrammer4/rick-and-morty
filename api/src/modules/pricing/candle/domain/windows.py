from typing import Self

from pydantic import BaseModel


class PriceWindow(BaseModel):
    open: int
    high: int
    low: int
    close: int

    def folded(self, price: int) -> Self:
        return self.model_copy(
            update={
                "high": max(self.high, price),
                "low": min(self.low, price),
                "close": price,
            }
        )


class AssetPriceWindow(PriceWindow):
    asset_id: int

    @classmethod
    def opened(cls, asset_id: int, price: int) -> Self:
        return cls(
            asset_id=asset_id,
            open=price,
            high=price,
            low=price,
            close=price,
        )


class SourcePriceWindow(PriceWindow):
    source_id: int
    symbol_id: int

    @classmethod
    def opened(
        cls,
        source_id: int,
        symbol_id: int,
        price: int,
    ) -> Self:
        return cls(
            source_id=source_id,
            symbol_id=symbol_id,
            open=price,
            high=price,
            low=price,
            close=price,
        )
