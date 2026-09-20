from enums import Category, DocumentStatus, LlmProvider, PriceType, SortKey, Source


def test_enum_values_are_stable_api_strings() -> None:
    assert Category.MOTORCYCLE.value == "motorcycle"
    assert SortKey.RELEVANCE.value == "relevance"
    assert LlmProvider("openai_compatible") is LlmProvider.OPENAI_COMPATIBLE
    assert Source("hamrah_mechanic") is Source.HAMRAH_MECHANIC
    assert PriceType.INSTALLMENT.value == "installment"
    # Both deed vocabularies live in one enum; neither may collide with the other.
    assert DocumentStatus("single_page") is not DocumentStatus.TITLE_IN_NAME
