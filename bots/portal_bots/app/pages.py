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
    rows = [buttons]
    if navigation.chart_id and navigation.page_titles:
        tabs = [
            InlineKeyboardButton(
                text=("✓ " if index == page else "") + title,
                callback_data=f"{prefix}:{index}",
            )
            for index, title in enumerate(navigation.page_titles)
        ]
        rows.extend(
            tabs[index : index + 2] for index in range(0, len(tabs), 2)
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)
