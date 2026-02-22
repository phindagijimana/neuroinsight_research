"""
Integration tests for the results module.

Tests the FreeSurfer .stats parser, label parser, and file classification
without requiring Docker or a database.

Run with:  PYTHONPATH=. python3 -m pytest tests/test_results_integration.py -v
"""
import json
import tempfile
from pathlib import Path

import pytest


class TestStatsFileParser:
    """Test parsing of FreeSurfer .stats files."""

    def test_parse_aseg_stats(self):
        """Parse a realistic aseg.stats file."""
        from backend.routes.results import _parse_stats_file

        content = """# Title Segmentation Statistics
#
# Measure BrainSeg, BrainSegVol, Brain Segmentation Volume, 1234567.0, mm^3
# Measure BrainSegNotVent, BrainSegVolNotVent, Brain Segmentation Volume Without Ventricles, 1100000.0, mm^3
# Measure lhCortex, lhCortexVol, Left hemisphere cortical gray matter volume, 245678.0, mm^3
# Measure EstimatedTotalIntraCranialVol, eTIV, Estimated Total Intracranial Volume, 1567890.0, mm^3
#
# ColHeaders  Index SegId NVoxels Volume_mm3 StructName
  1    2    8902   8456.0  Left-Cerebral-White-Matter
  2    3    9102   8989.0  Left-Cerebral-Cortex
  3   17    4321   4049.0  Left-Hippocampus
  4   53    4198   3841.0  Right-Hippocampus
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".stats", delete=False) as f:
            f.write(content)
            f.flush()
            result = _parse_stats_file(Path(f.name))

        assert result is not None
        assert result["BrainSegVol"] == 1234567.0
        assert result["eTIV"] == 1567890.0
        assert "table" in result
        assert len(result["table"]) == 4
        assert result["table"][2]["StructName"] == "Left-Hippocampus"

    def test_parse_empty_stats_returns_none(self):
        """Empty or comment-only stats file returns None."""
        from backend.routes.results import _parse_stats_file

        with tempfile.NamedTemporaryFile(mode="w", suffix=".stats", delete=False) as f:
            f.write("# Only comments\n# Nothing useful\n")
            f.flush()
            assert _parse_stats_file(Path(f.name)) is None


class TestColorLUTParser:
    """Test parsing of FreeSurfer color LUT files."""

    def test_parse_color_lut(self):
        """Parse a typical color LUT."""
        from backend.routes.results import _parse_color_lut

        content = """# This is a comment
0   Unknown          0   0   0   0
1   Left-Cerebral-WM 245 245 245 0
17  Left-Hippocampus 220 216 20  0
53  Right-Hippocampus 220 216 20 0
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(content)
            f.flush()
            labels = _parse_color_lut(Path(f.name))

        assert "0" in labels
        assert labels["17"]["name"] == "Left-Hippocampus"
        assert labels["17"]["color"] == "#dcd814"


class TestFileClassification:
    """Test the file type classifier."""

    def test_volume_classification(self):
        from backend.routes.results import _classify_file
        assert _classify_file("brain.nii.gz") == "volume"
        assert _classify_file("aseg.mgz") == "volume"
        assert _classify_file("T1.mgh") == "volume"

    def test_metrics_classification(self):
        from backend.routes.results import _classify_file
        assert _classify_file("aseg.stats") == "metrics"
        assert _classify_file("volumes.csv") == "metrics"
        assert _classify_file("table.tsv") == "metrics"

    def test_metadata_classification(self):
        from backend.routes.results import _classify_file
        assert _classify_file("labels.json") == "metadata"

    def test_report_classification(self):
        from backend.routes.results import _classify_file
        assert _classify_file("report.html") == "report"

    def test_image_classification(self):
        from backend.routes.results import _classify_file
        assert _classify_file("overlay.png") == "image"


class TestFormatSize:
    """Test the human-readable file size formatter."""

    def test_bytes(self):
        from backend.routes.results import _format_size
        assert _format_size(500) == "500 B"

    def test_kilobytes(self):
        from backend.routes.results import _format_size
        assert _format_size(2048) == "2.0 KB"

    def test_megabytes(self):
        from backend.routes.results import _format_size
        assert _format_size(5 * 1024 * 1024) == "5.0 MB"

    def test_gigabytes(self):
        from backend.routes.results import _format_size
        assert _format_size(2 * 1024 * 1024 * 1024) == "2.0 GB"
