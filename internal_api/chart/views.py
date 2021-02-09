from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import JSONParser

from codecov_auth.models import Owner
from core.models import Commit
from .filters import apply_default_filters, apply_simple_filters
from .helpers import (
    annotate_commits_with_totals,
    apply_grouping,
    validate_params,
    validate_analytics_chart_params,
)
from internal_api.permissions import ChartPermissions
from internal_api.mixins import RepositoriesMixin


class RepositoryChartHandler(APIView, RepositoriesMixin):
    """
    Returns data used to populate the repository-level coverage chart. See "validate_params" for documentation on accepted parameters. 
    Can either group and aggregate commits by a unit of time, or just return latest commits from the repo within the given time frame.
    When aggregating by coverage, will also apply aggregation based on complexity ratio and return that.

    Responses take the following format (semantics of the response depend on whether we're grouping by time or not):     
    {
        "coverage": [
            {
                "date": "2019-06-01 00:00:00+00:00",
                    # grouping by time: NOT the commit timestamp, the date for this time window
                    # no grouping: when returning ungrouped commits: commit timestamp
                "coverage": <coverage value>
                    # grouping by time: coverage from the commit retrieved (the one with min/max coverage) for this time unit
                    # no grouping: coverage from the commit
                "commitid": <commitid>
                    # grouping by time: id of the commit retrieved (the one with min/max coverage) for this time unit
                    # no grouping: id of the commit
            },
            {
                "date": "2019-07-01 00:00:00+00:00",
                "coverage": <coverage value>
                "commitid": <commit id>
                ...
            },
            ...
        ],
        "complexity": [
            {
                "date": "2019-07-01 00:00:00+00:00",
                "complexity_ratio": <complexity ratio value>
                "commitid": <commit id>
            },
            {
                "date": "2019-07-01 00:00:00+00:00",     
                ...   
            },
            ...
        ]
    }
    """

    permission_classes = [ChartPermissions]
    parser_classes = [JSONParser]

    def post(self, request, *args, **kwargs):
        request_params = {**self.request.data, **self.kwargs}
        validate_params(request_params)
        coverage_ordering = "" if request_params.get("coverage_timestamp_order", "increasing") == "increasing" else "-"

        queryset = apply_simple_filters(
            apply_default_filters(Commit.objects.all()), request_params, self.request.user
        )

        annotated_queryset = annotate_commits_with_totals(queryset)

        # if grouping_unit doesn't specify time, return all values
        if self.request.data.get("grouping_unit") == "commit":
            max_num_commits = 1000
            commits = annotated_queryset.order_by(f"{coverage_ordering}timestamp")[:max_num_commits]
            coverage = [
                {
                    "date": commits[index].timestamp,
                    "coverage": commits[index].coverage,
                    "coverage_change": commits[index].coverage -
                                       commits[max(index - 1, 0)].coverage,
                    "commitid": commits[index].commitid,
                }
                for index in range(len(commits))
            ]

            complexity = [
                {
                    "date": commit.timestamp,
                    "complexity_ratio": commit.complexity_ratio,
                    "commitid": commit.commitid,
                }
                for commit in annotated_queryset.order_by(f"{coverage_ordering}timestamp")[:max_num_commits] if commit.complexity_ratio is not None
            ]

        else:
            # Coverage
            coverage_grouped_queryset = apply_grouping(
                annotated_queryset, self.request.data
            )

            commits = coverage_grouped_queryset
            coverage = [
                {
                    "date": commits[index].truncated_date,
                    "coverage": commits[index].coverage,
                    "coverage_change": commits[index].coverage -
                                       commits[max(index - 1, 0)].coverage,
                    "commitid": commits[index].commitid,
                }
                for index in range(len(commits))
            ]

            # Complexity
            complexity_params = self.request.data.copy()
            complexity_params["agg_value"] = "complexity_ratio"
            complexity_grouped_queryset = apply_grouping(
                annotated_queryset, complexity_params
            )
            complexity = [
                {
                    "date": commit.truncated_date,
                    "complexity_ratio": commit.complexity_ratio,
                    "commitid": commit.commitid,
                }
                for commit in complexity_grouped_queryset if commit.complexity_ratio is not None
            ]

        return Response(data={"coverage": coverage, "complexity": complexity})


class OrganizationChartHandler(APIView, RepositoriesMixin):
    """
    Returns data used to populate the organization-level analytics chart. See "validate_params" for documentation on accepted parameters. 
    Functions generally similarly to the repository chart, with a few exceptions: aggregates coverage across multiple repositories, 
    doesn't return complexity, and doesn't support retrieving a list of commits (so coverage must be grouped by a unit of time).

    Responses take the following format: (example assumes grouping by month)
    {
        "coverage": [
            {
                "date": "2019-06-01 00:00:00+00:00", <NOT the commit timestamp, the date for the time window>
                "coverage": <coverage calculated by taking (total_lines + total_hits) / total_partials>,
                "total_lines": <sum of lines across repositories from the commit we retrieved for the repo>,
                "total_hits": <sum of hits across repositories>,
                "total_partials": <sum of partials across repositories>,
            },
            {
                "date": "2019-07-01 00:00:00+00:00",
                ...
            },
            ...
        ]
    }
    """

    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def _get_ordering(self, request_params):
        return "DESC" if request_params.get("ordering") == "decreasing" else ""

    def _get_end_date(self, request_params):
        # Determine end date to use, default is now
        if "end_date" in request_params:
            end_date = parser.parse(request_params.get("end_date"))
        else:
            end_date = datetime.date(datetime.now())
        return end_date

    def _get_start_date(self, request_params):
        # Determine start date to use
        if "start_date" in request_params:
            start_date = parser.parse(request_params.get("start_date"))
        else:
            start_date = None
        return start_date

    def _get_repoids(self, user, request_params):
        # Get organization
        organization = Owner.objects.get(
            service=request_params["service"],
            username=request_params["owner_username"]
        )

        # Get list of relevant repoids
        repoids = organization.repository_set.viewable_repos(
            user
        ).values_list("repoid", flat=True)

        if request_params.get("repositories", []):
            repoids = repoids.filter(name__in=request_params.get("repositories", []))

        return repoids

    def post(self, request, *args, **kwargs):
        request_params = {**self.request.data, **self.kwargs}
        validate_analytics_chart_params(request_params)

        return Response(
            data={
                "coverage": retrieve_org_analytics_data(
                    repoids=self._get_repoids(request.user, request_params),
                    start_date=self._get_start_date(request_params),
                    end_date=self._get_end_date(request_params),
                    grouping_unit=request_params.get("grouping_unit"),
                    ordering=self._get_ordering(request_params)
                )
            }
        )
