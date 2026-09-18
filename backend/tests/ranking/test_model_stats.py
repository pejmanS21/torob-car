import uuid

from ranking.model_stats import HISTOGRAM_BUCKETS, ModelRow, summarize_model


def make_row(price: int | None, **overrides: object) -> ModelRow:
    fields: dict[str, object] = {
        "listing_id": uuid.uuid4(),
        "trim": "پژو 206 تیپ ۲",
        "year": 1398,
        "price": price,
        "deal_score": 70,
    }
    return ModelRow(**{**fields, **overrides})


def test_histogram_counts_sum_to_the_priced_count_and_ignore_unpriced() -> None:
    rows = [make_row(price) for price in range(500, 1500, 10)]  # 100 priced rows
    rows += [make_row(None), make_row(None)]  # missing or suspect prices
    summary = summarize_model(rows, top_deals=6)
    assert summary.count == 102
    assert len(summary.histogram) == HISTOGRAM_BUCKETS
    assert sum(bucket.count for bucket in summary.histogram) == 100
    assert summary.price_min == 500 and summary.price_max == 1490
    assert summary.price_median == 995


def test_outliers_fall_into_the_edge_buckets() -> None:
    rows = [make_row(price) for price in range(1000, 1100)] + [
        make_row(1),
        make_row(10_000_000),
    ]
    histogram = summarize_model(rows, top_deals=6).histogram
    assert histogram[0].count >= 1 and histogram[-1].count >= 1
    assert sum(bucket.count for bucket in histogram) == 102
    assert all(
        b.high - b.low == histogram[0].high - histogram[0].low for b in histogram
    )


def test_trims_are_sorted_by_count_with_their_own_median() -> None:
    rows = [make_row(800, trim="تیپ ۵")] * 3 + [make_row(600, trim="تیپ ۲")]
    trims = summarize_model(rows, top_deals=6).trims
    assert [(trim.trim, trim.count) for trim in trims] == [("تیپ ۵", 3), ("تیپ ۲", 1)]
    assert trims[0].price_median == 800


def test_top_deals_are_the_highest_deal_scores() -> None:
    best = make_row(700, deal_score=95)
    rows = [make_row(800, deal_score=40), best, make_row(900, deal_score=None)]
    summary = summarize_model(rows, top_deals=1)
    assert summary.top_deal_ids == (best.listing_id,)


def test_a_single_priced_row_still_produces_eight_buckets() -> None:
    summary = summarize_model([make_row(800)], top_deals=6)
    assert len(summary.histogram) == HISTOGRAM_BUCKETS
    assert summary.histogram[0].count == 1


def test_no_rows_means_no_numbers() -> None:
    summary = summarize_model([], top_deals=6)
    assert summary.count == 0 and summary.price_median is None
    assert summary.histogram == () and summary.trims == ()
