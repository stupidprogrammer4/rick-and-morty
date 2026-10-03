from html import escape

from portal_contracts.enums import Category
from portal_contracts.presentation import PortalPresentation


class PostRenderer:
    def __init__(self, presentation: PortalPresentation):
        self.presentation = presentation

    def render(self, title: str, text: str, category: str) -> str:
        style = self.presentation.posts[Category(category)]
        output = (
            f"<b>{escape(style.heading)}</b>\n{escape(style.separator)}\n\n"
            f"<b>{escape(title)}</b>\n\n{escape(text)}\n\n"
            f"{escape(style.separator)}\n{escape(style.footer)}\n\n"
            f"{escape(style.hashtags)}"
        )
        if len(output) > self.presentation.maximum_post_characters:
            raise ValueError("Rendered draft exceeds the single-post limit")
        return output
