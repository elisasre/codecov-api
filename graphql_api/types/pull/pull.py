from ariadne import ObjectType
from asgiref.sync import async_to_sync, sync_to_async

from compare.models import CommitComparison
from graphql_api.dataloader.commit import load_commit_by_id
from graphql_api.dataloader.owner import load_owner_by_id
from graphql_api.helpers.connection import queryset_to_connection
from graphql_api.types.enums import OrderingDirection
from graphql_api.types.enums.enums import PullRequestState
from services.comparison import PullRequestComparison

pull_bindable = ObjectType("Pull")

pull_bindable.set_alias("pullId", "pullid")


@pull_bindable.field("state")
def resolve_state(pull, info):
    return PullRequestState(pull.state)


@pull_bindable.field("author")
def resolve_author(pull, info):
    if pull.author_id:
        return load_owner_by_id(info, pull.author_id)


@pull_bindable.field("head")
def resolve_head(pull, info):
    if pull.head == None:
        return None
    return load_commit_by_id(info, pull.head, pull.repository_id)


@pull_bindable.field("comparedTo")
def resolve_base(pull, info):
    if pull.compared_to == None:
        return None
    return load_commit_by_id(info, pull.compared_to, pull.repository_id)


@pull_bindable.field("compareWithBase")
@sync_to_async
def resolve_compare_with_base(pull, info, **kwargs):
    command = info.context["executor"].get_command("compare")
    commit_comparison = async_to_sync(command.compare_pull_request)(pull)

    if commit_comparison.state == CommitComparison.CommitComparisonStates.PROCESSED:
        # store the comparison in the context - to be used in the `Comparison` resolvers
        request = info.context["request"]
        info.context["comparison"] = PullRequestComparison(request.user, pull)

    return commit_comparison


@pull_bindable.field("commits")
async def resolve_commits(pull, info, **kwargs):
    command = info.context["executor"].get_command("commit")
    queryset = await command.fetch_commits_by_pullid(pull)

    return await queryset_to_connection(
        queryset,
        ordering="updatestamp",
        ordering_direction=OrderingDirection.ASC,
        **kwargs,
    )
