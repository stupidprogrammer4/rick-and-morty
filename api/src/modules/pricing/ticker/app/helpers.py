from fractions import Fraction
from typing import Protocol, Sequence

from src.modules.pricing.symbols.domain.enums import CurrencyType
from src.modules.pricing.ticker.domain.enums import ChartType
from src.modules.pricing.ticker.domain.models import (
    ChartOutputModel,
    PointOutputModel,
)
from src.tools.currency import round_rial


class PricedPoint(Protocol):
    price: int
    timestamp: int


class ChartBuilder:
    def points(
        self,
        rows: Sequence[PricedPoint],
    ) -> list[PointOutputModel]:
        """
        Desc: Turn priced rows into the points a chart is drawn from.
        Args:
            rows (Sequence[PricedPoint]): Rows as read, oldest first.
        Returns:
            return (list[PointOutputModel]): Points of the chart.
        """
        return [
            PointOutputModel(price=row.price, timestamp=row.timestamp)
            for row in rows
        ]

    def build(
        self,
        type: ChartType,
        rows: Sequence[PricedPoint],
        now: int,
        currency: CurrencyType = CurrencyType.RIAL,
    ) -> ChartOutputModel:
        """
        Desc: Build one chart with its span, extremes and change rate.
        Args:
            type (ChartType): Chart being drawn, which sets the span.
            rows (Sequence[PricedPoint]): Rows as read, oldest first.
            now (int): Epoch second the span ends at.
        Returns:
            return (ChartOutputModel): The chart and its summary.
        """
        points = self.points(rows)
        prices = [point.price for point in points]
        opening = prices[0] if prices else 0
        closing = prices[-1] if prices else 0
        divisor = opening or 1
        average = Fraction(sum(prices), len(prices)) if prices else Fraction(0)
        mean = (
            round_rial(average)
            if currency is CurrencyType.RIAL
            else round(average)
        )
        return ChartOutputModel(
            type=type,
            points=points,
            from_timestamp=now - type.span,
            to_timestamp=now,
            max=max(prices, default=0),
            min=min(prices, default=0),
            mean=mean,
            change_rate=(closing - opening) / divisor,
        )
