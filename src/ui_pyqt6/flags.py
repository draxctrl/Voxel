"""Country flags for the language picker.

Windows deliberately omits flag emoji from Segoe UI Emoji — a regional
indicator pair renders as the letters, not a flag — so these are image assets
rather than text. SVGs are MIT-licensed from lipis/flag-icons; see
src/assets/flags/LICENSE.
"""
import logging
import os

from PyQt6.QtGui import QIcon

logger = logging.getLogger(__name__)

#: Language code to ISO country code. Where a language spans several countries
#: the flag follows speaker numbers rather than country of origin — hence Brazil
#: for Portuguese and the United States for English. Whisper treats the variants
#: as one language, so they are not split into separate rows.
LANGUAGE_FLAGS: dict[str, str] = {
    "en": "us",
    "es": "es",
    "fr": "fr",
    "de": "de",
    "it": "it",
    "pt": "br",
    "ja": "jp",
    "ko": "kr",
    "zh": "cn",
    # "auto" (Auto-detect) is deliberately absent: it isn't a country.
}


def flag_icon(lang_code: str, assets_dir: str) -> QIcon | None:
    """Flag for a language, or None if there isn't one.

    Returns None rather than an empty QIcon so callers can tell "no flag" from
    "broken flag" and simply add the row without an icon — a missing asset
    should cost a picture, never a language.
    """
    country = LANGUAGE_FLAGS.get(lang_code)
    if country is None:
        return None

    path = os.path.join(assets_dir, "flags", f"{country}.svg")
    if not os.path.isfile(path):
        logger.warning("Flag asset missing: %s", path)
        return None

    icon = QIcon(path)
    if icon.isNull():
        logger.warning("Qt could not read flag asset: %s", path)
        return None
    return icon
