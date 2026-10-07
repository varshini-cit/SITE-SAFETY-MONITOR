"""
Unit tests for src/utils.py: overlap geometry and timestamp formatting.
Pure logic -- no model, dataset, or ultralytics needed.
"""

from src.utils import class_matches, compute_overlap_fraction, format_timestamp


class TestComputeOverlapFraction:
    def test_identical_boxes(self):
        box = (0.0, 0.0, 100.0, 100.0)
        assert compute_overlap_fraction(box, box) == 1.0

    def test_disjoint_boxes(self):
        assert compute_overlap_fraction((0, 0, 10, 10), (20, 20, 30, 30)) == 0.0

    def test_partial_overlap(self):
        # Intersection 10x10=100; box_a area 100x100=10000 -> 0.01.
        frac = compute_overlap_fraction((0, 0, 100, 100), (90, 90, 110, 110))
        assert abs(frac - 0.01) < 1e-9

    def test_contained_box_gives_full_fraction(self):
        # box_a fully inside box_b -> fraction relative to box_a = 1.0.
        assert compute_overlap_fraction((10, 10, 30, 30), (0, 0, 100, 100)) == 1.0

    def test_zero_area_box_returns_zero(self):
        assert compute_overlap_fraction((5, 5, 5, 5), (0, 0, 10, 10)) == 0.0

    def test_negative_overlap_clamps_to_zero(self):
        assert compute_overlap_fraction((10, 10, 5, 5), (0, 0, 10, 10)) == 0.0


class TestFormatTimestamp:
    def test_zero(self):
        assert format_timestamp(0, 25.0) == "00:00:00.000"

    def test_75_frames_at_25fps_is_three_seconds(self):
        assert format_timestamp(75, 25.0) == "00:00:03.000"

    def test_negative_or_zero_fps_falls_back_to_frames_as_seconds(self):
        assert format_timestamp(10, 0) == "00:00:10.000"


class TestClassMatches:
    def test_case_insensitive(self):
        assert class_matches("Hardhat", ("hardhat", "helmet")) is True
        assert class_matches("SAFETY VEST", ("safety vest", "vest")) is True

    def test_non_match(self):
        assert class_matches("excavator", ("hardhat",)) is False
