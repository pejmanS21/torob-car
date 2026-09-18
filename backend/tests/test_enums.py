from enums import Category, LlmProvider, SortKey


def test_enum_values_are_stable_api_strings() -> None:
    assert Category.MOTORCYCLE.value == "motorcycle"
    assert SortKey.RELEVANCE.value == "relevance"
    assert LlmProvider("openai_compatible") is LlmProvider.OPENAI_COMPATIBLE
