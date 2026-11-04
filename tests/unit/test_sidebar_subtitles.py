"""A sidebar card's subtitle names the service's family in words a reader uses.

The vendor's icon folders became subtitles by title case, which read
"Ai Machine Learning" and "Iot", and folders that only sort the vendor's
files ("new-icons", "general", "other") put words like "New Icons" under a
card. A subtitle now spells the family properly, and a sorting folder gives
way to the category the card is listed under, which the sidebar then leaves
out as a repeat.
"""

from __future__ import annotations

import re

import pytest

from infragram.catalog import load_default_provider_registry
from infragram.editor import load_sidebar_catalog
from infragram.editor.sidebar import _SORTING_FOLDERS, _folder_subtitle


def test_a_folder_reads_as_its_family_name() -> None:
    assert (
        _folder_subtitle("ai-machine-learning", "AI & Machine Learning") == "AI & Machine Learning"
    )
    assert _folder_subtitle("iot", "Internet of Things") == "Internet of Things"
    assert _folder_subtitle("migrate", "Hybrid & MultiCloud") == "Migrate"


def test_a_sorting_folder_gives_way_to_the_category() -> None:
    for folder in _SORTING_FOLDERS:
        assert _folder_subtitle(folder, "Integration") == "Integration"


def test_a_family_keeps_its_own_spelling() -> None:
    assert _folder_subtitle("ai", "AI & Machine Learning") == "AI"
    assert _folder_subtitle("devops", "Developer Tools") == "DevOps"
    assert _folder_subtitle("generic-os", "Compute") == "Generic OS"


@pytest.mark.parametrize(
    "provider", [provider.id for provider in load_default_provider_registry().providers]
)
def test_no_shipped_card_carries_a_title_cased_slug_or_a_sorting_folder(provider: str) -> None:
    """Every library this edition ships, not only the one the rule was found in."""
    catalog = load_sidebar_catalog(provider)
    subtitles = {
        component.subtitle for category in catalog.categories for component in category.components
    }
    title_cased = re.compile(r"\b(Ai|Iot|Os|Saas|Dns|Devops)\b")
    assert not {"New Icons", "General", "Other", "Menu"} & subtitles
    assert not {subtitle for subtitle in subtitles if title_cased.search(subtitle)}
