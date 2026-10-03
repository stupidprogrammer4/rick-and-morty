"""Shared rial settlement and input constraints."""

from decimal import Decimal
from fractions import Fraction
from typing import Annotated

from papilio.types.aliases import RialType as NativeRialType
from pydantic import Field

RIAL_QUANTUM = 100
RialType = Annotated[NativeRialType, Field(multiple_of=RIAL_QUANTUM)]


def round_rial(amount: int | float | Decimal | Fraction) -> int:
    """Round to 100 rials, with Python's nearest-even tie rule."""
    if isinstance(amount, bool):
        raise ValueError("A rial amount must be numeric, not boolean")
    return round(Fraction(amount) / RIAL_QUANTUM) * RIAL_QUANTUM
