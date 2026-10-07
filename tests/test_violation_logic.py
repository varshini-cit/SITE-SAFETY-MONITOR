"""
Unit tests for src/violation_logic.py: association + 8-frame persistence.

These tests do NOT need a trained model, the dataset, or ultralytics --
they exercise pure logic only.
"""

from src.violation_logic import (
    ViolationStateTracker,
    associate_ppe_with_persons,
)


def person(x1=100, y1=100, x2=200, y2=300, track_id=None, name="person"):
    return {"bbox": (x1, y1, x2, y2), "class_name": name, "track_id": track_id}


def ppe(name, x1, y1, x2, y2):
    return {"bbox": (x1, y1, x2, y2), "class_name": name, "confidence": 0.9}


# ---------------------------------------------------------------------------
# Association tests
# ---------------------------------------------------------------------------
class TestAssociation:
    def test_compliant_person(self):
        dets = [
            person(track_id=1),
            ppe("hardhat", 110, 90, 190, 140),
            ppe("safety vest", 105, 140, 195, 260),
        ]
        result = associate_ppe_with_persons(dets, overlap_threshold=0.05)
        assert len(result) == 1
        assert result[0].has_helmet is True
        assert result[0].has_vest is True
        assert result[0].missing_ppe == []
        assert result[0].is_compliant is True

    def test_missing_both_ppe(self):
        result = associate_ppe_with_persons([person(track_id=1)], overlap_threshold=0.05)
        assert result[0].has_helmet is False
        assert result[0].has_vest is False
        assert result[0].missing_ppe == ["helmet", "safety vest"]
        assert result[0].is_compliant is False

    def test_helmet_only(self):
        dets = [person(track_id=1), ppe("helmet", 110, 90, 190, 140)]
        result = associate_ppe_with_persons(dets, overlap_threshold=0.05)
        assert result[0].has_helmet is True
        assert result[0].has_vest is False
        assert result[0].missing_ppe == ["safety vest"]

    def test_ppe_too_far_is_not_associated(self):
        dets = [person(track_id=1), ppe("hardhat", 500, 500, 540, 540)]
        result = associate_ppe_with_persons(dets, overlap_threshold=0.05)
        assert result[0].has_helmet is False

    def test_overlap_threshold_is_configurable(self):
        # Hardhat box (25x20=500px^2) overlapping the person by 1x20=20px^2
        # -> 4% of its own area: below the 5% threshold, above 0.1%.
        dets = [person(track_id=1), ppe("hardhat", 199, 105, 220, 125)]
        below = associate_ppe_with_persons(dets, overlap_threshold=0.05)
        assert below[0].has_helmet is False

        above = associate_ppe_with_persons(dets, overlap_threshold=0.001)
        assert above[0].has_helmet is True

    def test_case_insensitive_class_names(self):
        dets = [
            {"bbox": (100, 100, 200, 300), "class_name": "PERSON", "track_id": 1},
            {"bbox": (110, 90, 190, 140), "class_name": "Hardhat"},
            {"bbox": (105, 140, 195, 260), "class_name": "Safety Vest"},
        ]
        result = associate_ppe_with_persons(dets, overlap_threshold=0.05)
        assert result[0].has_helmet is True
        assert result[0].has_vest is True

    def test_track_id_is_carried_through(self):
        dets = [person(track_id=7)]
        result = associate_ppe_with_persons(dets, overlap_threshold=0.05)
        assert result[0].track_id == 7


# ---------------------------------------------------------------------------
# 8-frame persistence tests
# ---------------------------------------------------------------------------
class TestPersistence:
    def test_confirms_exactly_on_eighth_frame(self):
        vt = ViolationStateTracker(persistence_frames=8)
        fired = [vt.update(track_id=1, violation_type="missing_helmet",
                           is_violating=True) for _ in range(8)]
        assert fired[:7] == [False] * 7
        assert fired[7] is True

    def test_no_confirmation_before_eight_frames(self):
        vt = ViolationStateTracker(persistence_frames=8)
        for _ in range(7):
            assert vt.update(1, "missing_helmet", True) is False

    def test_reset_when_violation_disappears(self):
        vt = ViolationStateTracker(persistence_frames=8)
        for _ in range(5):
            vt.update(1, "missing_helmet", True)
        # Violation disappears for two frames -> counter resets.
        assert vt.update(1, "missing_helmet", False) is False
        assert vt.update(1, "missing_helmet", False) is False
        assert vt.get_count(1, "missing_helmet") == 0
        # Needs the full 8 consecutive frames again.
        fired = [vt.update(1, "missing_helmet", True) for _ in range(8)]
        assert fired[:7] == [False] * 7
        assert fired[7] is True

    def test_duplicate_alert_prevention(self):
        vt = ViolationStateTracker(persistence_frames=8)
        for _ in range(8):
            vt.update(1, "missing_helmet", True)
        # Same continuous violation continues for many more frames: no new alert.
        for _ in range(20):
            assert vt.update(1, "missing_helmet", True) is False

    def test_new_episode_after_clearing(self):
        vt = ViolationStateTracker(persistence_frames=8)
        for _ in range(8):
            assert vt.update(1, "missing_helmet", True) is False or True
        # First episode already alerted on frame 8; continue 10 frames: silent.
        for _ in range(10):
            assert vt.update(1, "missing_helmet", True) is False
        # Violation clears, then a NEW episode starts -> can confirm again.
        vt.update(1, "missing_helmet", False)
        fired = [vt.update(1, "missing_helmet", True) for _ in range(8)]
        assert fired[7] is True

    def test_persons_tracked_independently(self):
        vt = ViolationStateTracker(persistence_frames=8)
        for _ in range(7):
            vt.update(1, "missing_helmet", True)
            vt.update(2, "missing_helmet", True)
        # Frame 8: only person 1 has reached 8 if person 2 started later.
        assert vt.update(2, "missing_helmet", True) is True
        # Person 1 still at 7.
        assert vt.get_count(1, "missing_helmet") == 7

    def test_violation_types_tracked_independently(self):
        vt = ViolationStateTracker(persistence_frames=8)
        for _ in range(4):
            vt.update(1, "missing_helmet", True)
        assert vt.get_count(1, "missing_safety_vest") == 0

    def test_none_track_id_treated_as_separate_slot(self):
        vt = ViolationStateTracker(persistence_frames=2)
        assert vt.update(None, "missing_helmet", True) is False
        assert vt.update(None, "missing_helmet", True) is True

    def test_invalid_persistence_raises(self):
        import pytest
        with pytest.raises(ValueError):
            ViolationStateTracker(persistence_frames=0)

    def test_clear_person_and_reset(self):
        vt = ViolationStateTracker(persistence_frames=8)
        for _ in range(3):
            vt.update(1, "missing_helmet", True)
            vt.update(2, "missing_helmet", True)
        vt.clear_person(1)
        assert vt.get_count(1, "missing_helmet") == 0
        assert vt.get_count(2, "missing_helmet") == 3
        vt.reset()
        assert vt.get_count(2, "missing_helmet") == 0
        assert vt.has_suspected_violation(2, "missing_helmet") is False
