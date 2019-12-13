import asyncio

from rest_framework import generics
from django.shortcuts import get_object_or_404

from compare.services import Comparison
from internal_api.compare.serializers import (
    CommitsComparisonSerializer,
    ComparisonFullSrcSerializer,
    SingleFileSourceSerializer,
    FlagComparisonSerializer,
    ComparisonDetailsSerializer,
    SingleFileDiffSerializer,
)
from internal_api.mixins import CompareSlugMixin, RepoSlugUrlMixin
from core.models import Pull


class CompareCommits(CompareSlugMixin, generics.RetrieveAPIView):
    serializer_class = CommitsComparisonSerializer

    def get_object(self):
        asyncio.set_event_loop(asyncio.new_event_loop())
        base, head = self.get_commits()
        report = Comparison(base_commit=base, head_commit=head, user=self.request.user)
        return report


class CompareDetails(CompareSlugMixin, generics.RetrieveAPIView):
    serializer_class = ComparisonDetailsSerializer

    def get_object(self):
        asyncio.set_event_loop(asyncio.new_event_loop())
        base, head = self.get_commits()
        report = Comparison(base_commit=base, head_commit=head, user=self.request.user)
        return report


class CompareFullSource(CompareSlugMixin, generics.RetrieveAPIView):
    serializer_class = ComparisonFullSrcSerializer

    def get_object(self):
        asyncio.set_event_loop(asyncio.new_event_loop())
        base, head = self.get_commits()
        report = Comparison(base_commit=base, head_commit=head, user=self.request.user)
        return report


class CompareSingleFileSource(CompareSlugMixin, generics.RetrieveAPIView):
    serializer_class = SingleFileSourceSerializer

    def get_object(self):
        base, head = self.get_commits()
        file_path = self.kwargs.get('file_path')
        before = self.request.query_params.get('before')
        report = Comparison(base_commit=base, head_commit=head, user=self.request.user)
        file_changes = report.file_source(file_path=file_path, before_path=before)
        return asyncio.run(file_changes)


class CompareSingleFileDiff(CompareSlugMixin, generics.RetrieveAPIView):
    serializer_class = SingleFileDiffSerializer

    def get_object(self):
        asyncio.set_event_loop(asyncio.new_event_loop())
        base, head = self.get_commits()
        file_path = self.kwargs.get('file_path')
        report = Comparison(base_commit=base, head_commit=head, user=self.request.user)
        file_changes = report.file_diff(file_path=file_path)
        return file_changes


class CompareFlagsList(CompareSlugMixin, generics.ListAPIView):
    serializer_class = FlagComparisonSerializer

    def get_queryset(self):
        asyncio.set_event_loop(asyncio.new_event_loop())
        base, head = self.get_commits()
        comparison = Comparison(base_commit=base, head_commit=head, user=self.request.user)
        return list(
            comparison.flag_comparison(flag_name) for flag_name in comparison.available_flags
        )