from decimal import Decimal

import pytest
from papilio.errors.exceptions import ValidationException
from papilio.utils import currency as currency_utils
from papilio.utils.currency import TROY_OUNCE_GRAMS

from src.modules.pricing.calculator.app.helpers import SymbolConverter
from src.modules.pricing.symbols.domain.enums import CurrencyType, SymbolCode


class TestWhatASymbolCarries:
    def test_the_ounce_quotes_dollars_and_the_gram_quotes_rial(self) -> None:
        converter = SymbolConverter()

        assert converter.currencies[SymbolCode.XAU_OUNCE] is CurrencyType.USD
        assert (
            converter.currencies[SymbolCode.GOLD18_MAZANE] is CurrencyType.RIAL
        )

    def test_the_ounce_is_pure_and_the_gram_is_eighteen_karat(self) -> None:
        converter = SymbolConverter()

        assert converter.pure_grams[SymbolCode.XAU_OUNCE] == TROY_OUNCE_GRAMS
        assert converter.pure_grams[SymbolCode.GOLD18_GRAM] == Decimal("0.750")


class TestWithoutTheDollar:
    def test_a_gram_price_becomes_a_mazane_price(self) -> None:
        converter = SymbolConverter()

        mazane = converter.convert(
            10_000_000,
            SymbolCode.GOLD18_GRAM,
            SymbolCode.GOLD18_MAZANE,
        )

        assert mazane == 43_318_000

    def test_and_back_again_without_drifting(self) -> None:
        converter = SymbolConverter()

        mazane = converter.convert(
            12_345_670,
            SymbolCode.GOLD18_GRAM,
            SymbolCode.GOLD18_MAZANE,
        )
        gram = converter.convert(
            mazane,
            SymbolCode.GOLD18_MAZANE,
            SymbolCode.GOLD18_GRAM,
        )

        assert abs(gram - 12_345_670) <= 50

    def test_the_same_symbol_answers_what_it_was_given(self) -> None:
        converter = SymbolConverter()

        same = converter.convert(
            9_876_543,
            SymbolCode.GOLD18_GRAM,
            SymbolCode.GOLD18_GRAM,
        )

        assert same == 9_876_500

    def test_a_dollar_quoting_symbol_is_turned_away(self) -> None:
        converter = SymbolConverter()

        with pytest.raises(ValidationException):
            converter.convert(
                330_000,
                SymbolCode.XAU_OUNCE,
                SymbolCode.GOLD18_GRAM,
            )

    def test_a_symbol_that_weighs_no_gold_is_turned_away(self) -> None:
        converter = SymbolConverter()

        with pytest.raises(ValidationException):
            converter.convert(
                1_000_000,
                SymbolCode.USD_RIAL,
                SymbolCode.GOLD18_GRAM,
            )


class TestAcrossTheDollar:
    def test_an_ounce_in_cent_becomes_a_gram_in_rial(self) -> None:
        converter = SymbolConverter()
        cents = 330_000
        usd_price = 1_000_000

        per_gram = converter.convert_with_usd(
            cents,
            SymbolCode.XAU_OUNCE,
            SymbolCode.GOLD18_GRAM,
            usd_price,
        )

        assert per_gram == 79_573_100

    def test_a_gram_in_rial_becomes_an_ounce_in_cent(self) -> None:
        converter = SymbolConverter()
        usd_price = 1_000_000
        cents = 330_000
        per_gram = converter.convert_with_usd(
            cents,
            SymbolCode.XAU_OUNCE,
            SymbolCode.GOLD18_GRAM,
            usd_price,
        )

        back = converter.convert_with_usd(
            per_gram,
            SymbolCode.GOLD18_GRAM,
            SymbolCode.XAU_OUNCE,
            usd_price,
        )

        assert abs(back - cents) <= 2

    def test_a_mazane_price_reaches_the_ounce_too(self) -> None:
        converter = SymbolConverter()
        usd_price = 1_000_000
        mazane = currency_utils.to_mazane(10_000_000)

        ounce = converter.convert_with_usd(
            mazane,
            SymbolCode.GOLD18_MAZANE,
            SymbolCode.XAU_OUNCE,
            usd_price,
        )
        gram = converter.convert_with_usd(
            ounce,
            SymbolCode.XAU_OUNCE,
            SymbolCode.GOLD18_GRAM,
            usd_price,
        )

        assert abs(gram - 10_000_000) <= 100

    def test_without_a_dollar_price_it_refuses_rather_than_guesses(
        self,
    ) -> None:
        converter = SymbolConverter()

        with pytest.raises(ValidationException):
            converter.convert_with_usd(
                330_000,
                SymbolCode.XAU_OUNCE,
                SymbolCode.GOLD18_GRAM,
                usd_price=0,
            )


class TestASymbolThatWeighsAnotherMetal:
    def test_gold_does_not_restate_as_silver(self) -> None:
        converter = SymbolConverter()

        with pytest.raises(ValidationException) as raised:
            converter.convert(
                1_000_000,
                SymbolCode.GOLD18_GRAM,
                SymbolCode.SILVER_GRAM,
            )

        assert "different metals" in str(raised.value)

    def test_nor_across_the_dollar(self) -> None:
        converter = SymbolConverter()

        with pytest.raises(ValidationException):
            converter.convert_with_usd(
                1_000_000,
                SymbolCode.GOLD18_GRAM,
                SymbolCode.XAG_OUNCE,
                1_000_000,
            )

    def test_silver_restates_on_its_own_ounce(self) -> None:
        converter = SymbolConverter()

        restated = converter.convert_with_usd(
            4_663_650,
            SymbolCode.SILVER_GRAM,
            SymbolCode.XAG_OUNCE,
            1_000_000,
        )

        assert restated > 0


pytestmark = [pytest.mark.unit]
