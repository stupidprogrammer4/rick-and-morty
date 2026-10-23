from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from portal_contracts.telegram import PublicationNavigation


def page_keyboard(navigation: PublicationNavigation) -> InlineKeyboardMarkup:
    page = navigation.page
    prefix = (
        f"charts:{navigation.chart_id}"
        if navigation.chart_id
        else f"prices:{navigation.publication_id}"
    )
    buttons = []
    if page > 0:
        buttons.append(
            InlineKeyboardButton(
                text=navigation.previous_label,
                callback_data=f"{prefix}:{page - 1}",
            )
        )
    label = navigation.page_label.replace("{page}", str(page + 1)).replace(
        "{total}", str(navigation.total)
    )
    buttons.append(
        InlineKeyboardButton(
            text=label,
            callback_data=f"{prefix}:{page}",
        )
    )
    if page + 1 < navigation.total:
        buttons.append(
            InlineKeyboardButton(
                text=navigation.next_label,
                callback_data=f"{prefix}:{page + 1}",
            )
        )
    return InlineKeyboardMarkup(inline_keyboard=[buttons])
