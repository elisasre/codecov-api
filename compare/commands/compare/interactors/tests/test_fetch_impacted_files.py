import enum
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.test import TransactionTestCase
from shared.reports.types import ReportTotals

from codecov_auth.tests.factories import OwnerFactory
from compare.tests.factories import CommitComparisonFactory
from core.tests.factories import CommitFactory
from services.comparison import ImpactedFile, ImpactedFileParameter

from ..fetch_impacted_files import FetchImpactedFiles


class OrderingDirection(enum.Enum):
    ASC = "ascending"
    DESC = "descending"


mock_data_with_unintended_changes = """
{
    "files": [{
        "head_name": "fileA",
        "base_name": "fileA",
        "head_coverage": {
            "hits": 10,
            "misses": 1,
            "partials": 1,
            "branches": 3,
            "sessions": 0,
            "complexity": 0,
            "complexity_total": 0,
            "methods": 5
        },
        "base_coverage": {
            "hits": 5,
            "misses": 6,
            "partials": 1,
            "branches": 2,
            "sessions": 0,
            "complexity": 0,
            "complexity_total": 0,
            "methods": 4
        },
        "added_diff_coverage": [
            [9,"h"],
            [2,"m"],
            [3,"m"],
            [13,"p"],
            [14,"h"],
            [15,"h"],
            [16,"h"],
            [17,"h"]
        ],
        "unexpected_line_changes": [[[1, "h"], [1, "h"]]]
    },
    {
        "head_name": "fileB",
        "base_name": "fileB",
        "head_coverage": {
            "hits": 12,
            "misses": 1,
            "partials": 1,
            "branches": 3,
            "sessions": 0,
            "complexity": 0,
            "complexity_total": 0,
            "methods": 5
        },
        "base_coverage": {
            "hits": 5,
            "misses": 6,
            "partials": 1,
            "branches": 2,
            "sessions": 0,
            "complexity": 0,
            "complexity_total": 0,
            "methods": 4
        },
        "added_diff_coverage": [
            [9,"h"],
            [10,"m"],
            [13,"p"],
            [14,"h"],
            [15,"h"],
            [16,"h"],
            [17,"h"]
        ]
    }]
}
"""


mock_data_from_archive = """
{
    "files": [{
        "head_name": "fileA",
        "base_name": "fileA",
        "head_coverage": {
            "hits": 10,
            "misses": 1,
            "partials": 1,
            "branches": 3,
            "sessions": 0,
            "complexity": 0,
            "complexity_total": 0,
            "methods": 5
        },
        "base_coverage": {
            "hits": 5,
            "misses": 6,
            "partials": 1,
            "branches": 2,
            "sessions": 0,
            "complexity": 0,
            "complexity_total": 0,
            "methods": 4
        },
        "added_diff_coverage": [
            [9,"h"],
            [2,"m"],
            [3,"m"],
            [13,"p"],
            [14,"h"],
            [15,"h"],
            [16,"h"],
            [17,"h"]
        ]
    },
    {
        "head_name": "fileB",
        "base_name": "fileB",
        "head_coverage": {
            "hits": 12,
            "misses": 1,
            "partials": 1,
            "branches": 3,
            "sessions": 0,
            "complexity": 0,
            "complexity_total": 0,
            "methods": 5
        },
        "base_coverage": {
            "hits": 5,
            "misses": 6,
            "partials": 1,
            "branches": 2,
            "sessions": 0,
            "complexity": 0,
            "complexity_total": 0,
            "methods": 4
        },
        "added_diff_coverage": [
            [9,"h"],
            [10,"m"],
            [13,"p"],
            [14,"h"],
            [15,"h"],
            [16,"h"],
            [17,"h"]
        ]
    }]
}
"""

mock_data_without_misses = """
{
    "files": [{
        "head_name": "fileA",
        "base_name": "fileA",
        "head_coverage": {
            "hits": 10,
            "misses": 1,
            "partials": 1,
            "branches": 3,
            "sessions": 0,
            "complexity": 0,
            "complexity_total": 0,
            "methods": 5
        },
        "base_coverage": {
            "hits": 5,
            "misses": 6,
            "partials": 1,
            "branches": 2,
            "sessions": 0,
            "complexity": 0,
            "complexity_total": 0,
            "methods": 4
        },
        "added_diff_coverage": []
    },
    {
        "head_name": "fileB",
        "base_name": "fileB",
        "head_coverage": {
            "hits": 12,
            "misses": 1,
            "partials": 1,
            "branches": 3,
            "sessions": 0,
            "complexity": 0,
            "complexity_total": 0,
            "methods": 5
        },
        "base_coverage": {
            "hits": 5,
            "misses": 6,
            "partials": 1,
            "branches": 2,
            "sessions": 0,
            "complexity": 0,
            "complexity_total": 0,
            "methods": 4
        },
        "added_diff_coverage": [
            [9,"h"],
            [10,"m"],
            [13,"p"],
            [14,"h"],
            [15,"h"],
            [16,"h"],
            [17,"h"]
        ]
    }]
}
"""


class FetchImpactedFilesTest(TransactionTestCase):
    def setUp(self):
        self.user = OwnerFactory(username="codecov-user")
        self.parent_commit = CommitFactory()
        self.commit = CommitFactory(
            parent_commit_id=self.parent_commit.commitid,
            repository=self.parent_commit.repository,
        )
        self.comparison = CommitComparisonFactory(
            base_commit=self.parent_commit,
            compare_commit=self.commit,
            report_storage_path="v4/test.json",
        )

    # helper to execute the interactor
    def execute(self, user, *args):
        service = user.service if user else "github"
        current_user = user or AnonymousUser()
        return FetchImpactedFiles(current_user, service).execute(*args)

    @patch("services.archive.ArchiveService.read_file")
    def test_impacted_file_sort_function(self, read_file):
        read_file.return_value = mock_data_from_archive
        parameter = ImpactedFileParameter.CHANGE_COVERAGE
        direction = OrderingDirection.ASC
        filters = {"ordering": {"parameter": parameter, "direction": direction}}
        sorted_files = self.execute(None, self.comparison, filters)

        assert sorted_files == [
            ImpactedFile(
                file_name="fileA",
                base_name="fileA",
                head_name="fileA",
                base_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=6,
                    partials=1,
                    coverage=41.666666666666664,
                    branches=2,
                    methods=4,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                head_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=10,
                    misses=1,
                    partials=1,
                    coverage=83.33333333333333,
                    branches=3,
                    methods=5,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                patch_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=2,
                    partials=1,
                    coverage=62.5,
                    branches=0,
                    methods=0,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                change_coverage=41.666666666666664,
            ),
            ImpactedFile(
                file_name="fileB",
                base_name="fileB",
                head_name="fileB",
                base_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=6,
                    partials=1,
                    coverage=41.666666666666664,
                    branches=2,
                    methods=4,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                head_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=12,
                    misses=1,
                    partials=1,
                    coverage=85.71428571428571,
                    branches=3,
                    methods=5,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                patch_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=1,
                    partials=1,
                    coverage=71.42857142857143,
                    branches=0,
                    methods=0,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                change_coverage=44.047619047619044,
            ),
        ]

    @patch("services.archive.ArchiveService.read_file")
    def test_impacted_file_sort_function_no_misses(self, read_file):
        read_file.return_value = mock_data_without_misses
        parameter = ImpactedFileParameter.PATCH_COVERAGE_MISSES
        direction = OrderingDirection.ASC
        filters = {"ordering": {"parameter": parameter, "direction": direction}}
        sorted_files = self.execute(None, self.comparison, filters)

        assert sorted_files == [
            ImpactedFile(
                file_name="fileB",
                base_name="fileB",
                head_name="fileB",
                base_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=6,
                    partials=1,
                    coverage=41.666666666666664,
                    branches=2,
                    methods=4,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                head_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=12,
                    misses=1,
                    partials=1,
                    coverage=85.71428571428571,
                    branches=3,
                    methods=5,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                patch_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=1,
                    partials=1,
                    coverage=71.42857142857143,
                    branches=0,
                    methods=0,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                change_coverage=44.047619047619044,
            ),
            ImpactedFile(
                file_name="fileA",
                base_name="fileA",
                head_name="fileA",
                base_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=6,
                    partials=1,
                    coverage=41.666666666666664,
                    branches=2,
                    methods=4,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                head_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=10,
                    misses=1,
                    partials=1,
                    coverage=83.33333333333333,
                    branches=3,
                    methods=5,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                patch_coverage=None,
                change_coverage=41.666666666666664,
            ),
        ]

    @patch("services.archive.ArchiveService.read_file")
    def test_impacted_file_sort_function_error(self, read_file):
        read_file.return_value = mock_data_from_archive
        parameter = "something else"
        direction = OrderingDirection.DESC
        filters = {"ordering": {"parameter": parameter, "direction": direction}}

        with self.assertRaises(ValueError) as ctx:
            self.execute(None, self.comparison, filters)
        self.assertEqual(
            "invalid impacted file parameter: something else", str(ctx.exception)
        )

    @patch("services.archive.ArchiveService.read_file")
    def test_impacted_files_filtered_by_change_coverage_ascending(self, read_file):
        read_file.return_value = mock_data_from_archive
        filters = {
            "ordering": {
                "direction": OrderingDirection.ASC,
                "parameter": ImpactedFileParameter.CHANGE_COVERAGE,
            }
        }
        impacted_files = self.execute(None, self.comparison, filters)
        assert impacted_files == [
            ImpactedFile(
                file_name="fileA",
                base_name="fileA",
                head_name="fileA",
                base_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=6,
                    partials=1,
                    coverage=41.666666666666664,
                    branches=2,
                    methods=4,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                head_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=10,
                    misses=1,
                    partials=1,
                    coverage=83.33333333333333,
                    branches=3,
                    methods=5,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                patch_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=2,
                    partials=1,
                    coverage=62.5,
                    branches=0,
                    methods=0,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                change_coverage=41.666666666666664,
            ),
            ImpactedFile(
                file_name="fileB",
                base_name="fileB",
                head_name="fileB",
                base_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=6,
                    partials=1,
                    coverage=41.666666666666664,
                    branches=2,
                    methods=4,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                head_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=12,
                    misses=1,
                    partials=1,
                    coverage=85.71428571428571,
                    branches=3,
                    methods=5,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                patch_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=1,
                    partials=1,
                    coverage=71.42857142857143,
                    branches=0,
                    methods=0,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                change_coverage=44.047619047619044,
            ),
        ]

    @patch("services.archive.ArchiveService.read_file")
    def test_impacted_files_filtered_by_change_coverage_descending(self, read_file):
        read_file.return_value = mock_data_from_archive
        filters = {
            "ordering": {
                "direction": OrderingDirection.DESC,
                "parameter": ImpactedFileParameter.CHANGE_COVERAGE,
            }
        }
        impacted_files = self.execute(None, self.comparison, filters)
        assert impacted_files == [
            ImpactedFile(
                file_name="fileB",
                base_name="fileB",
                head_name="fileB",
                base_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=6,
                    partials=1,
                    coverage=41.666666666666664,
                    branches=2,
                    methods=4,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                head_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=12,
                    misses=1,
                    partials=1,
                    coverage=85.71428571428571,
                    branches=3,
                    methods=5,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                patch_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=1,
                    partials=1,
                    coverage=71.42857142857143,
                    branches=0,
                    methods=0,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                change_coverage=44.047619047619044,
            ),
            ImpactedFile(
                file_name="fileA",
                base_name="fileA",
                head_name="fileA",
                base_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=6,
                    partials=1,
                    coverage=41.666666666666664,
                    branches=2,
                    methods=4,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                head_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=10,
                    misses=1,
                    partials=1,
                    coverage=83.33333333333333,
                    branches=3,
                    methods=5,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                patch_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=2,
                    partials=1,
                    coverage=62.5,
                    branches=0,
                    methods=0,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                change_coverage=41.666666666666664,
            ),
        ]

    @patch("services.archive.ArchiveService.read_file")
    def test_impacted_files_filtered_by_head_coverage_ascending(self, read_file):
        read_file.return_value = mock_data_from_archive
        filters = {
            "ordering": {
                "direction": OrderingDirection.ASC,
                "parameter": ImpactedFileParameter.HEAD_COVERAGE,
            }
        }
        impacted_files = self.execute(None, self.comparison, filters)
        assert impacted_files == [
            ImpactedFile(
                file_name="fileA",
                base_name="fileA",
                head_name="fileA",
                base_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=6,
                    partials=1,
                    coverage=41.666666666666664,
                    branches=2,
                    methods=4,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                head_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=10,
                    misses=1,
                    partials=1,
                    coverage=83.33333333333333,
                    branches=3,
                    methods=5,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                patch_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=2,
                    partials=1,
                    coverage=62.5,
                    branches=0,
                    methods=0,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                change_coverage=41.666666666666664,
            ),
            ImpactedFile(
                file_name="fileB",
                base_name="fileB",
                head_name="fileB",
                base_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=6,
                    partials=1,
                    coverage=41.666666666666664,
                    branches=2,
                    methods=4,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                head_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=12,
                    misses=1,
                    partials=1,
                    coverage=85.71428571428571,
                    branches=3,
                    methods=5,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                patch_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=1,
                    partials=1,
                    coverage=71.42857142857143,
                    branches=0,
                    methods=0,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                change_coverage=44.047619047619044,
            ),
        ]

    @patch("services.archive.ArchiveService.read_file")
    def test_impacted_files_filtered_by_patch_coverage_ascending(self, read_file):
        read_file.return_value = mock_data_from_archive
        filters = {
            "ordering": {
                "direction": OrderingDirection.ASC,
                "parameter": ImpactedFileParameter.PATCH_COVERAGE,
            }
        }
        impacted_files = self.execute(None, self.comparison, filters)
        assert impacted_files == [
            ImpactedFile(
                file_name="fileA",
                base_name="fileA",
                head_name="fileA",
                base_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=6,
                    partials=1,
                    coverage=41.666666666666664,
                    branches=2,
                    methods=4,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                head_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=10,
                    misses=1,
                    partials=1,
                    coverage=83.33333333333333,
                    branches=3,
                    methods=5,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                patch_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=2,
                    partials=1,
                    coverage=62.5,
                    branches=0,
                    methods=0,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                change_coverage=41.666666666666664,
            ),
            ImpactedFile(
                file_name="fileB",
                base_name="fileB",
                head_name="fileB",
                base_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=6,
                    partials=1,
                    coverage=41.666666666666664,
                    branches=2,
                    methods=4,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                head_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=12,
                    misses=1,
                    partials=1,
                    coverage=85.71428571428571,
                    branches=3,
                    methods=5,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                patch_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=1,
                    partials=1,
                    coverage=71.42857142857143,
                    branches=0,
                    methods=0,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                change_coverage=44.047619047619044,
            ),
        ]

    @patch("services.archive.ArchiveService.read_file")
    def test_impacted_files_filtered_by_patch_coverage_descending(self, read_file):
        read_file.return_value = mock_data_from_archive
        filters = {
            "ordering": {
                "direction": OrderingDirection.DESC,
                "parameter": ImpactedFileParameter.PATCH_COVERAGE,
            }
        }
        impacted_files = self.execute(None, self.comparison, filters)
        assert impacted_files == [
            ImpactedFile(
                file_name="fileB",
                base_name="fileB",
                head_name="fileB",
                base_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=6,
                    partials=1,
                    coverage=41.666666666666664,
                    branches=2,
                    methods=4,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                head_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=12,
                    misses=1,
                    partials=1,
                    coverage=85.71428571428571,
                    branches=3,
                    methods=5,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                patch_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=1,
                    partials=1,
                    coverage=71.42857142857143,
                    branches=0,
                    methods=0,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                change_coverage=44.047619047619044,
            ),
            ImpactedFile(
                file_name="fileA",
                base_name="fileA",
                head_name="fileA",
                base_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=6,
                    partials=1,
                    coverage=41.666666666666664,
                    branches=2,
                    methods=4,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                head_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=10,
                    misses=1,
                    partials=1,
                    coverage=83.33333333333333,
                    branches=3,
                    methods=5,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                patch_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=2,
                    partials=1,
                    coverage=62.5,
                    branches=0,
                    methods=0,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                change_coverage=41.666666666666664,
            ),
        ]

    @patch("services.archive.ArchiveService.read_file")
    def test_impacted_files_filtered_by_head_coverage_descending(self, read_file):
        read_file.return_value = mock_data_from_archive
        filters = {
            "ordering": {
                "direction": OrderingDirection.DESC,
                "parameter": ImpactedFileParameter.HEAD_COVERAGE,
            }
        }
        impacted_files = self.execute(None, self.comparison, filters)
        assert impacted_files == [
            ImpactedFile(
                file_name="fileB",
                base_name="fileB",
                head_name="fileB",
                base_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=6,
                    partials=1,
                    coverage=41.666666666666664,
                    branches=2,
                    methods=4,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                head_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=12,
                    misses=1,
                    partials=1,
                    coverage=85.71428571428571,
                    branches=3,
                    methods=5,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                patch_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=1,
                    partials=1,
                    coverage=71.42857142857143,
                    branches=0,
                    methods=0,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                change_coverage=44.047619047619044,
            ),
            ImpactedFile(
                file_name="fileA",
                base_name="fileA",
                head_name="fileA",
                base_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=6,
                    partials=1,
                    coverage=41.666666666666664,
                    branches=2,
                    methods=4,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                head_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=10,
                    misses=1,
                    partials=1,
                    coverage=83.33333333333333,
                    branches=3,
                    methods=5,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                patch_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=2,
                    partials=1,
                    coverage=62.5,
                    branches=0,
                    methods=0,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                change_coverage=41.666666666666664,
            ),
        ]

    @patch("services.archive.ArchiveService.read_file")
    def test_impacted_files_filtered_by_head_name_ascending(self, read_file):
        read_file.return_value = mock_data_from_archive
        filters = {
            "ordering": {
                "direction": OrderingDirection.ASC,
                "parameter": ImpactedFileParameter.FILE_NAME,
            }
        }
        impacted_files = self.execute(None, self.comparison, filters)
        assert impacted_files == [
            ImpactedFile(
                file_name="fileA",
                base_name="fileA",
                head_name="fileA",
                base_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=6,
                    partials=1,
                    coverage=41.666666666666664,
                    branches=2,
                    methods=4,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                head_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=10,
                    misses=1,
                    partials=1,
                    coverage=83.33333333333333,
                    branches=3,
                    methods=5,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                patch_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=2,
                    partials=1,
                    coverage=62.5,
                    branches=0,
                    methods=0,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                change_coverage=41.666666666666664,
            ),
            ImpactedFile(
                file_name="fileB",
                base_name="fileB",
                head_name="fileB",
                base_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=6,
                    partials=1,
                    coverage=41.666666666666664,
                    branches=2,
                    methods=4,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                head_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=12,
                    misses=1,
                    partials=1,
                    coverage=85.71428571428571,
                    branches=3,
                    methods=5,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                patch_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=1,
                    partials=1,
                    coverage=71.42857142857143,
                    branches=0,
                    methods=0,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                change_coverage=44.047619047619044,
            ),
        ]

    @patch("services.archive.ArchiveService.read_file")
    def test_impacted_files_filtered_by_head_name_descending(self, read_file):
        read_file.return_value = mock_data_from_archive
        filters = {
            "ordering": {
                "direction": OrderingDirection.DESC,
                "parameter": ImpactedFileParameter.FILE_NAME,
            }
        }
        impacted_files = self.execute(None, self.comparison, filters)
        assert impacted_files == [
            ImpactedFile(
                file_name="fileB",
                base_name="fileB",
                head_name="fileB",
                base_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=6,
                    partials=1,
                    coverage=41.666666666666664,
                    branches=2,
                    methods=4,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                head_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=12,
                    misses=1,
                    partials=1,
                    coverage=85.71428571428571,
                    branches=3,
                    methods=5,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                patch_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=1,
                    partials=1,
                    coverage=71.42857142857143,
                    branches=0,
                    methods=0,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                change_coverage=44.047619047619044,
            ),
            ImpactedFile(
                file_name="fileA",
                base_name="fileA",
                head_name="fileA",
                base_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=6,
                    partials=1,
                    coverage=41.666666666666664,
                    branches=2,
                    methods=4,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                head_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=10,
                    misses=1,
                    partials=1,
                    coverage=83.33333333333333,
                    branches=3,
                    methods=5,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                patch_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=2,
                    partials=1,
                    coverage=62.5,
                    branches=0,
                    methods=0,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                change_coverage=41.666666666666664,
            ),
        ]

    @patch("services.archive.ArchiveService.read_file")
    def test_impacted_files_filtered_by_patch_coverage_misses_ascending(
        self, read_file
    ):
        read_file.return_value = mock_data_from_archive
        filters = {
            "ordering": {
                "direction": OrderingDirection.ASC,
                "parameter": ImpactedFileParameter.PATCH_COVERAGE_MISSES,
            }
        }
        impacted_files = self.execute(None, self.comparison, filters)
        assert impacted_files == [
            ImpactedFile(
                file_name="fileB",
                base_name="fileB",
                head_name="fileB",
                base_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=6,
                    partials=1,
                    coverage=41.666666666666664,
                    branches=2,
                    methods=4,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                head_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=12,
                    misses=1,
                    partials=1,
                    coverage=85.71428571428571,
                    branches=3,
                    methods=5,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                patch_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=1,
                    partials=1,
                    coverage=71.42857142857143,
                    branches=0,
                    methods=0,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                change_coverage=44.047619047619044,
            ),
            ImpactedFile(
                file_name="fileA",
                base_name="fileA",
                head_name="fileA",
                base_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=6,
                    partials=1,
                    coverage=41.666666666666664,
                    branches=2,
                    methods=4,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                head_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=10,
                    misses=1,
                    partials=1,
                    coverage=83.33333333333333,
                    branches=3,
                    methods=5,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                patch_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=2,
                    partials=1,
                    coverage=62.5,
                    branches=0,
                    methods=0,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                change_coverage=41.666666666666664,
            ),
        ]

    @patch("services.archive.ArchiveService.read_file")
    def test_impacted_files_filtered_by_patch_coverage_misses_descending(
        self, read_file
    ):
        read_file.return_value = mock_data_from_archive
        filters = {
            "ordering": {
                "direction": OrderingDirection.DESC,
                "parameter": ImpactedFileParameter.PATCH_COVERAGE_MISSES,
            }
        }
        impacted_files = self.execute(None, self.comparison, filters)
        assert impacted_files == [
            ImpactedFile(
                file_name="fileA",
                base_name="fileA",
                head_name="fileA",
                base_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=6,
                    partials=1,
                    coverage=41.666666666666664,
                    branches=2,
                    methods=4,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                head_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=10,
                    misses=1,
                    partials=1,
                    coverage=83.33333333333333,
                    branches=3,
                    methods=5,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                patch_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=2,
                    partials=1,
                    coverage=62.5,
                    branches=0,
                    methods=0,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                change_coverage=41.666666666666664,
            ),
            ImpactedFile(
                file_name="fileB",
                base_name="fileB",
                head_name="fileB",
                base_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=6,
                    partials=1,
                    coverage=41.666666666666664,
                    branches=2,
                    methods=4,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                head_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=12,
                    misses=1,
                    partials=1,
                    coverage=85.71428571428571,
                    branches=3,
                    methods=5,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                patch_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=1,
                    partials=1,
                    coverage=71.42857142857143,
                    branches=0,
                    methods=0,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                change_coverage=44.047619047619044,
            ),
        ]

    @patch("services.archive.ArchiveService.read_file")
    def test_impacted_files_without_filters(self, read_file):
        read_file.return_value = mock_data_from_archive
        filters = {}
        impacted_files = self.execute(None, self.comparison, filters)
        assert impacted_files == [
            ImpactedFile(
                file_name="fileA",
                base_name="fileA",
                head_name="fileA",
                base_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=6,
                    partials=1,
                    coverage=41.666666666666664,
                    branches=2,
                    methods=4,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                head_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=10,
                    misses=1,
                    partials=1,
                    coverage=83.33333333333333,
                    branches=3,
                    methods=5,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                patch_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=2,
                    partials=1,
                    coverage=62.5,
                    branches=0,
                    methods=0,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                change_coverage=41.666666666666664,
            ),
            ImpactedFile(
                file_name="fileB",
                base_name="fileB",
                head_name="fileB",
                base_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=6,
                    partials=1,
                    coverage=41.666666666666664,
                    branches=2,
                    methods=4,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                head_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=12,
                    misses=1,
                    partials=1,
                    coverage=85.71428571428571,
                    branches=3,
                    methods=5,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                patch_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=1,
                    partials=1,
                    coverage=71.42857142857143,
                    branches=0,
                    methods=0,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                change_coverage=44.047619047619044,
            ),
        ]

    @patch("services.archive.ArchiveService.read_file")
    def test_impacted_files_filtered_by_unintended_changes(self, read_file):
        read_file.return_value = mock_data_from_archive
        filters = {
            "has_unintended_changes": True,
            "ordering": {
                "direction": OrderingDirection.ASC,
                "parameter": ImpactedFileParameter.FILE_NAME,
            },
        }
        impacted_files = self.execute(None, self.comparison, filters)
        assert impacted_files == []

    @patch("services.archive.ArchiveService.read_file")
    def test_impacted_files_filtered_by_unintended_changes_returns_data(
        self, read_file
    ):
        read_file.return_value = mock_data_with_unintended_changes
        filters = {
            "has_unintended_changes": True,
        }
        impacted_files = self.execute(None, self.comparison, filters)
        assert impacted_files == [
            ImpactedFile(
                file_name="fileA",
                base_name="fileA",
                head_name="fileA",
                base_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=6,
                    partials=1,
                    coverage=41.666666666666664,
                    branches=2,
                    methods=4,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                head_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=10,
                    misses=1,
                    partials=1,
                    coverage=83.33333333333333,
                    branches=3,
                    methods=5,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                patch_coverage=ReportTotals(
                    files=0,
                    lines=0,
                    hits=5,
                    misses=2,
                    partials=1,
                    coverage=62.5,
                    branches=0,
                    methods=0,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                change_coverage=41.666666666666664,
            )
        ]
