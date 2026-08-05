# tests/test_content_cleaner.py
# Parameterized tests for announcement content cleaner heading classification.
# Regression guard: ensures newly added heading patterns are never lost.

import pytest
from pilotstd.announcement._content_cleaner import clean_announcement_content


class TestHeadingClassification:
    """Verify all known heading lines are classified as announce-heading."""

    HEADING_CASES = [
        # (input_text, expected_class_count)
        # GB standard
        ("中华人民共和国国家标准\n\n公告\n\n2026年第31号", 3),
        ("中华人民共和国国家标准\n\n公告\n\n2025年第8号", 3),
        # Industry standard
        ("行业标准公告\n\n2026年第12号", 2),
        ("行业标准备案公告\n\n2025年第6号", 2),
        # Local standard
        ("地方标准公告\n\n2026年第5号", 2),
        # Monthly report
        ("备案月报\n\n2026年第3期", 1),
    ]

    @pytest.mark.parametrize("text,expected_count", HEADING_CASES)
    def test_headings_classified_correctly(self, text, expected_count):
        result = clean_announcement_content(text)
        count = result.count('class="announce-heading"')
        assert count == expected_count, (
            f"Expected {expected_count} announce-heading, got {count}\nResult:\n{result}"
        )

    BODY_CASES = [
        "关于批准发布《食品安全国家标准》等16项国家标准的公告",
        "国家市场监督管理总局（国家标准化管理委员会）批准以下标准，现予以公告",
    ]

    @pytest.mark.parametrize("text", BODY_CASES)
    def test_body_not_misclassified_as_heading(self, text):
        result = clean_announcement_content(text)
        assert 'class="announce-body"' in result
        assert 'class="announce-heading"' not in result


class TestDateClassification:
    """Verify date lines stay as announce-date."""

    def test_date_line(self):
        result = clean_announcement_content("2026-07-15")
        assert 'class="announce-date"' in result

    def test_date_not_misclassified(self):
        result = clean_announcement_content("2026-07-15")
        assert 'class="announce-heading"' not in result


class TestSignatureClassification:
    """Verify signature lines stay as announce-signature."""

    def test_signature_line(self):
        result = clean_announcement_content(
            "国家市场监督管理总局 国家标准化管理委员会\n\n2026-07-15"
        )
        assert 'class="announce-signature"' in result


class TestEmptyAndEdgeCases:
    """Verify edge cases don't crash."""

    def test_empty_input(self):
        assert clean_announcement_content("") == ""

    def test_whitespace_only(self):
        assert clean_announcement_content("   \n  \n  ") == ""

    def test_single_line_no_match(self):
        result = clean_announcement_content("随机文本内容")
        assert 'class="announce-body"' in result
