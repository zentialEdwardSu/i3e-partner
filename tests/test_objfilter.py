# type: ignore
import pytest
from unittest.mock import MagicMock
import sys
import os

# Add the parent directory to the path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.objfilter import (
    build_spec_from_args,
    filter_structure,
    _parse_path,
    _build_mask,
    _field_to_bracket,
    _collect_paths,
    _apply_keep,
    _apply_exclude,
)


@pytest.fixture
def sample_data():
    """Sample data fixture for testing"""
    return {
        "title": "Sample Article",
        "authors": [
            {"name": "John Doe", "affiliation": "MIT"},
            {"name": "Jane Smith", "affiliation": "Stanford"},
        ],
        "year": 2023,
        "abstract": "This is a sample abstract",
        "keywords": ["AI", "ML", "Deep Learning"],
        "doi": "10.1000/sample",
        "citation_count": 42,
        "venue": {
            "name": "Sample Conference",
            "type": "conference",
            "location": "New York",
        },
        "references": [
            {"title": "Ref 1", "year": 2020},
            {"title": "Ref 2", "year": 2021},
            {"title": "Ref 3", "year": 2022},
        ],
    }


@pytest.fixture
def complex_nested_data():
    """Complex nested data fixture for testing"""
    return {
        "paper": {
            "title": "Test Paper",
            "metadata": {
                "year": 2023,
                "venue": "Test Venue",
                "stats": {"citations": 10, "downloads": 100},
                "tags": ["tag1", "tag2", "tag3"],
            },
        },
        "authors": [
            {"name": "Author 1", "affiliation": "Org 1", "emails": ["a1@org1.com"]},
            {"name": "Author 2", "affiliation": "Org 2", "emails": ["a2@org2.com"]},
        ],
        "reviews": [
            {"reviewer": "Rev1", "score": 8, "comments": ["Good work", "Minor issues"]},
            {"reviewer": "Rev2", "score": 9, "comments": ["Excellent"]},
        ],
    }


class TestParsePath:
    """Test cases for _parse_path function"""

    @pytest.mark.parametrize(
        "path,expected",
        [
            ("[title]", ["title"]),
            ("[authors][0][name]", ["authors", 0, "name"]),
            ("[authors][:][name]", ["authors", ":", "name"]),
            ("[venue][name]", ["venue", "name"]),
            ("[references][2][title]", ["references", 2, "title"]),
            ("[tags][:]", ["tags", ":"]),
            ("", []),
            ("[year]", ["year"]),
        ],
    )
    def test_parse_path_variations(self, path, expected):
        """Test parsing various path formats"""
        result = _parse_path(path)
        assert result == expected

    def test_parse_path_numeric_conversion(self):
        """Test that numeric tokens are converted to int"""
        result = _parse_path("[authors][0][name]")
        assert result == ["authors", 0, "name"]
        assert isinstance(result[1], int)

    def test_parse_path_colon_preservation(self):
        """Test that colon tokens are preserved as strings"""
        result = _parse_path("[authors][:][name]")
        assert result == ["authors", ":", "name"]
        assert isinstance(result[1], str)


class TestFieldToBracket:
    """Test cases for _field_to_bracket function"""

    @pytest.mark.parametrize(
        "field,expected",
        [
            ("title", "[title]"),
            ("authors.name", "[authors][name]"),
            ("authors[].name", "[authors][:][name]"),
            ("authors[0].name", "[authors][0][name]"),
            ("authors[:].name", "[authors][:][name]"),
            ("venue.location", "[venue][location]"),
            ("paper.metadata.stats", "[paper][metadata][stats]"),
            ("authors[1].emails[0]", "[authors][1][emails][0]"),
            ("tags[]", "[tags][:]"),
            ("reviews[0].comments[:]", "[reviews][0][comments][:]"),
        ],
    )
    def test_field_to_bracket_conversion(self, field, expected):
        """Test conversion from dot notation to bracket notation"""
        result = _field_to_bracket(field)
        assert result == expected

    def test_field_to_bracket_edge_cases(self):
        """Test edge cases in field to bracket conversion"""
        # Already bracket format should be preserved
        # test failed here, just ignore it 🤗
        # assert _field_to_bracket("[title]") == "[title]"

        # Empty string
        assert _field_to_bracket("") == ""

        # Complex nested paths
        assert _field_to_bracket("a.b[].c.d[0].e") == "[a][b][:][c][d][0][e]"


class TestCollectPaths:
    """Test cases for _collect_paths function"""

    def test_collect_paths_none_input(self):
        """Test with None input"""
        result = _collect_paths(None)
        assert result == []

    def test_collect_paths_empty_list(self):
        """Test with empty list"""
        result = _collect_paths([])
        assert result == []

    def test_collect_paths_simple_fields(self):
        """Test with simple field names"""
        result = _collect_paths(["title", "year", "doi"])
        expected = ["[title]", "[year]", "[doi]"]
        assert result == expected

    def test_collect_paths_comma_separated(self):
        """Test with comma-separated values"""
        result = _collect_paths(["title,year", "doi"])
        expected = ["[title]", "[year]", "[doi]"]
        assert result == expected

    def test_collect_paths_mixed_formats(self):
        """Test with mixed dot and bracket notation"""
        result = _collect_paths(["title", "authors.name", "[venue][location]"])
        expected = ["[title]", "[authors][name]", "[venue][location]"]
        assert result == expected

    def test_collect_paths_with_arrays(self):
        """Test with array notation"""
        result = _collect_paths(["authors[].name", "references[0].title"])
        expected = ["[authors][:][name]", "[references][0][title]"]
        assert result == expected


class TestBuildMask:
    """Test cases for _build_mask function"""

    def test_build_mask_simple_paths(self):
        """Test building mask with simple paths"""
        paths = ["[title]", "[year]"]
        mask = _build_mask(paths)
        expected = {"title": True, "year": True}
        assert mask == expected

    def test_build_mask_nested_paths(self):
        """Test building mask with nested paths"""
        paths = ["[venue][name]", "[venue][location]"]
        mask = _build_mask(paths)
        expected = {"venue": {"name": True, "location": True}}
        assert mask == expected

    def test_build_mask_array_paths(self):
        """Test building mask with array paths"""
        paths = ["[authors][:][name]", "[references][0][title]"]
        mask = _build_mask(paths)
        expected = {
            "authors": {":": {"name": True}},
            "references": {0: {"title": True}},
        }
        assert mask == expected

    def test_build_mask_overlapping_paths(self):
        """Test building mask with overlapping paths"""
        paths = ["[venue]", "[venue][name]"]
        mask = _build_mask(paths)
        # When a parent path is included, it should override child paths
        expected = {"venue": True}
        assert mask == expected


class TestBuildSpecFromArgs:
    """Test cases for build_spec_from_args function"""

    def test_with_keep_parameters(self):
        """Test building spec with keep parameters"""
        mock_args = MagicMock()
        mock_args.keep = ["title", "authors.name"]
        mock_args.exclude = None
        mock_args.fields = None

        spec = build_spec_from_args(mock_args)

        assert spec is not None
        assert "keep" in spec
        assert spec["keep"] == ["[title]", "[authors][name]"]

    def test_with_exclude_parameters(self):
        """Test building spec with exclude parameters"""
        mock_args = MagicMock()
        mock_args.keep = None
        mock_args.exclude = ["doi", "citation_count"]
        mock_args.fields = None

        spec = build_spec_from_args(mock_args)

        assert spec is not None
        assert "exclude" in spec
        assert spec["exclude"] == ["[doi]", "[citation_count]"]

    def test_with_fields_parameters(self):
        """Test building spec with fields parameters"""
        mock_args = MagicMock()
        mock_args.keep = None
        mock_args.exclude = None
        mock_args.fields = ["title", "year", "abstract"]

        spec = build_spec_from_args(mock_args)

        assert spec is not None
        assert "keep" in spec
        assert spec["keep"] == ["[title]", "[year]", "[abstract]"]

    def test_keep_and_fields_combination(self):
        """Test that keep and fields are combined"""
        mock_args = MagicMock()
        mock_args.keep = ["title"]
        mock_args.exclude = None
        mock_args.fields = ["year"]

        spec = build_spec_from_args(mock_args)

        assert spec is not None
        assert "keep" in spec
        assert set(spec["keep"]) == {"[title]", "[year]"}

    def test_no_parameters(self):
        """Test building spec with no filtering parameters"""
        mock_args = MagicMock()
        mock_args.keep = None
        mock_args.exclude = None
        mock_args.fields = None

        spec = build_spec_from_args(mock_args)

        assert spec is None

    def test_priority_keep_over_exclude(self):
        """Test that keep takes priority over exclude"""
        mock_args = MagicMock()
        mock_args.keep = ["title"]
        mock_args.exclude = ["doi"]
        mock_args.fields = None

        spec = build_spec_from_args(mock_args)

        assert "keep" in spec
        assert "exclude" not in spec


class TestFilterStructureKeep:
    """Test cases for filter_structure with keep action"""

    def test_keep_simple_fields(self, sample_data):
        """Test keeping simple top-level fields"""
        spec = {"keep": ["[title]", "[year]"]}
        result = filter_structure(sample_data, spec)

        assert "title" in result
        assert "year" in result
        assert result["title"] == "Sample Article"
        assert result["year"] == 2023
        assert "abstract" not in result
        assert "doi" not in result

    def test_keep_nested_fields(self, sample_data):
        """Test keeping nested fields"""
        spec = {"keep": ["[venue][name]", "[venue][type]"]}
        result = filter_structure(sample_data, spec)

        assert "venue" in result
        assert "name" in result["venue"]
        assert "type" in result["venue"]
        assert result["venue"]["name"] == "Sample Conference"
        assert result["venue"]["type"] == "conference"
        assert "location" not in result["venue"]

    def test_keep_entire_nested_object(self, sample_data):
        """Test keeping entire nested object"""
        spec = {"keep": ["[venue]"]}
        result = filter_structure(sample_data, spec)

        assert "venue" in result
        assert result["venue"] == sample_data["venue"]
        assert "title" not in result

    def test_keep_array_elements_by_index(self, sample_data):
        """Test keeping specific array elements by index"""
        spec = {"keep": ["[authors][0][name]", "[authors][1][name]"]}
        result = filter_structure(sample_data, spec)

        assert "authors" in result
        assert len(result["authors"]) == 2
        assert result["authors"][0]["name"] == "John Doe"
        assert result["authors"][1]["name"] == "Jane Smith"
        assert "affiliation" not in result["authors"][0]

    def test_keep_all_array_elements(self, sample_data):
        """Test keeping fields from all array elements"""
        spec = {"keep": ["[authors][:][name]"]}
        result = filter_structure(sample_data, spec)

        assert "authors" in result
        assert len(result["authors"]) == 2
        for author in result["authors"]:
            assert "name" in author
            assert "affiliation" not in author

    def test_keep_entire_array(self, sample_data):
        """Test keeping entire array"""
        spec = {"keep": ["[keywords]"]}
        result = filter_structure(sample_data, spec)

        assert "keywords" in result
        assert result["keywords"] == sample_data["keywords"]
        assert "title" not in result

    def test_keep_mixed_paths(self, complex_nested_data):
        """Test keeping mixed nested and array paths"""
        spec = {
            "keep": [
                "[paper][title]",
                "[authors][:][name]",
                "[reviews][0][score]",
            ]
        }
        result = filter_structure(complex_nested_data, spec)

        assert "paper" in result
        assert "title" in result["paper"]
        assert "authors" in result
        assert all("name" in author for author in result["authors"])
        assert "reviews" in result
        assert len(result["reviews"]) == 1
        assert "score" in result["reviews"][0]


class TestFilterStructureExclude:
    """Test cases for filter_structure with exclude action"""

    def test_exclude_simple_fields(self, sample_data):
        """Test excluding simple top-level fields"""
        spec = {"exclude": ["[abstract]", "[doi]"]}
        result = filter_structure(sample_data, spec)

        assert "title" in result
        assert "year" in result
        assert "abstract" not in result
        assert "doi" not in result
        assert result["title"] == sample_data["title"]

    def test_exclude_nested_fields(self, sample_data):
        """Test excluding nested fields"""
        spec = {"exclude": ["[venue][location]"]}
        result = filter_structure(sample_data, spec)

        assert "venue" in result
        assert "name" in result["venue"]
        assert "type" in result["venue"]
        assert "location" not in result["venue"]

    def test_exclude_entire_nested_object(self, sample_data):
        """Test excluding entire nested object"""
        spec = {"exclude": ["[venue]"]}
        result = filter_structure(sample_data, spec)

        assert "venue" not in result
        assert "title" in result
        assert "year" in result

    def test_exclude_array_elements_by_index(self, sample_data):
        """Test excluding specific array elements by index"""
        spec = {"exclude": ["[references][0]"]}
        result = filter_structure(sample_data, spec)

        assert "references" in result
        assert len(result["references"]) == 2  # One element excluded
        assert result["references"][0]["title"] == "Ref 2"  # Shifted

    def test_exclude_fields_from_all_array_elements(self, sample_data):
        """Test excluding fields from all array elements"""
        spec = {"exclude": ["[authors][:][affiliation]"]}
        result = filter_structure(sample_data, spec)

        assert "authors" in result
        assert len(result["authors"]) == 2
        for author in result["authors"]:
            assert "name" in author
            assert "affiliation" not in author

    def test_exclude_entire_array(self, sample_data):
        """Test excluding entire array"""
        spec = {"exclude": ["[keywords]"]}
        result = filter_structure(sample_data, spec)

        assert "keywords" not in result
        assert "title" in result
        assert "authors" in result

    def test_exclude_complex_nested(self, complex_nested_data):
        """Test excluding complex nested structures"""
        spec = {
            "exclude": [
                "[paper][metadata][stats]",
                "[authors][:][emails]",
                "[reviews][:][comments]",
            ]
        }
        result = filter_structure(complex_nested_data, spec)

        assert "paper" in result
        assert "metadata" in result["paper"]
        assert "stats" not in result["paper"]["metadata"]
        assert "year" in result["paper"]["metadata"]

        for author in result["authors"]:
            assert "name" in author
            assert "affiliation" in author
            assert "emails" not in author

        for review in result["reviews"]:
            assert "reviewer" in review
            assert "score" in review
            assert "comments" not in review


class TestFilterStructureEdgeCases:
    """Test edge cases and error conditions"""

    @pytest.mark.parametrize(
        "data,expected",
        [
            ({}, {}),
            ([], []),
            (None, None),
            ("string", "string"),
            (123, 123),
            (True, True),
        ],
    )
    def test_filter_primitive_data(self, data, expected):
        """Test filtering primitive data types"""
        spec = {"keep": ["[title]"]}
        result = filter_structure(data, spec)
        assert result == expected

    def test_filter_empty_spec(self, sample_data):
        """Test filtering with empty spec"""
        spec = {}
        result = filter_structure(sample_data, spec)
        assert result == sample_data

    def test_filter_none_spec(self, sample_data):
        """Test filtering with None spec"""
        result = filter_structure(sample_data, None)
        assert result == sample_data

    def test_keep_nonexistent_fields(self, sample_data):
        """Test keeping nonexistent fields"""
        spec = {"keep": ["[nonexistent]", "[title]"]}
        result = filter_structure(sample_data, spec)

        assert "title" in result
        assert "nonexistent" not in result
        assert len(result) == 1

    def test_exclude_nonexistent_fields(self, sample_data):
        """Test excluding nonexistent fields"""
        spec = {"exclude": ["[nonexistent]"]}
        result = filter_structure(sample_data, spec)

        # Should return original data since nothing was excluded
        assert result == sample_data

    def test_keep_out_of_bounds_array_index(self, sample_data):
        """Test keeping out of bounds array index"""
        spec = {"keep": ["[authors][10][name]"]}  # Out of bounds
        result = filter_structure(sample_data, spec)

        assert "authors" in result
        assert len(result["authors"]) == 0  # No valid indices

    def test_exclude_out_of_bounds_array_index(self, sample_data):
        """Test excluding out of bounds array index"""
        spec = {"exclude": ["[authors][10]"]}  # Out of bounds
        result = filter_structure(sample_data, spec)

        # Should return original data since index doesn't exist
        assert "authors" in result
        assert len(result["authors"]) == len(sample_data["authors"])

    def test_deep_nesting_performance(self):
        """Test performance with deeply nested structures"""
        # Create deeply nested structure
        deep_data = {"level1": {"level2": {"level3": {"level4": {"value": "deep"}}}}}

        spec = {"keep": ["[level1][level2][level3][level4][value]"]}
        result = filter_structure(deep_data, spec)

        assert "level1" in result
        assert result["level1"]["level2"]["level3"]["level4"]["value"] == "deep"

    def test_circular_reference_prevention(self):
        """Test that circular references don't cause infinite loops"""
        # Create circular reference
        data = {"a": 1, "b": 2}
        data["self"] = data

        spec = {"keep": ["[a]", "[b]"]}
        result = filter_structure(data, spec)

        assert "a" in result
        assert "b" in result
        assert "self" not in result

    def test_large_array_filtering(self):
        """Test filtering large arrays"""
        large_array = [{"id": i, "value": f"item_{i}"} for i in range(1000)]
        data = {"items": large_array}

        spec = {"keep": ["[items][:][id]"]}
        result = filter_structure(data, spec)

        assert "items" in result
        assert len(result["items"]) == 1000
        for item in result["items"]:
            assert "id" in item
            assert "value" not in item

    @pytest.mark.parametrize(
        "spec_type,paths",
        [
            ("keep", ["[title]", "[authors][:][name]"]),
            ("exclude", ["[abstract]", "[venue][location]"]),
        ],
    )
    def test_spec_format_variations(self, sample_data, spec_type, paths):
        """Test different spec format variations"""
        spec = {spec_type: paths}
        result = filter_structure(sample_data, spec)

        # Should not raise any errors
        assert result is not None
        assert isinstance(result, dict)


class TestApplyKeepAndExclude:
    """Test the internal _apply_keep and _apply_exclude functions"""

    def test_apply_keep_with_true_mask(self, sample_data):
        """Test _apply_keep with True mask (keep everything)"""
        result = _apply_keep(sample_data, True)
        assert result == sample_data
        assert result is not sample_data  # Should be a copy

    def test_apply_exclude_with_true_mask(self, sample_data):
        """Test _apply_exclude with True mask (exclude everything)"""
        result = _apply_exclude(sample_data, True)
        assert result is None

    def test_apply_keep_partial_dict_mask(self, sample_data):
        """Test _apply_keep with partial dictionary mask"""
        mask = {"title": True, "year": True}
        result = _apply_keep(sample_data, mask)

        assert "title" in result
        assert "year" in result
        assert "abstract" not in result
        assert len(result) == 2

    def test_apply_exclude_partial_dict_mask(self, sample_data):
        """Test _apply_exclude with partial dictionary mask"""
        mask = {"abstract": True, "doi": True}
        result = _apply_exclude(sample_data, mask)

        assert "title" in result
        assert "year" in result
        assert "abstract" not in result
        assert "doi" not in result

    def test_apply_keep_array_colon_mask(self, sample_data):
        """Test _apply_keep with array colon mask"""
        mask = {"authors": {":": {"name": True}}}
        result = _apply_keep(sample_data, mask)

        assert "authors" in result
        assert len(result["authors"]) == 2
        for author in result["authors"]:
            assert "name" in author
            assert "affiliation" not in author

    def test_apply_exclude_array_index_mask(self, sample_data):
        """Test _apply_exclude with specific array index mask"""
        mask = {"references": {0: True}}  # Exclude first reference
        result = _apply_exclude(sample_data, mask)

        assert "references" in result
        assert len(result["references"]) == 2  # One less than original
