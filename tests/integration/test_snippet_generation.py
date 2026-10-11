"""Real MongoDB saves generated drafts/rejections and preserves old schema-v1 turns."""

import os
from unittest.mock import AsyncMock

import pytest

from ml_pipeline_pro.conversation_schemas import ChatRequest, ModelStep
from ml_pipeline_pro.conversation_service import ConversationService
from ml_pipeline_pro.conversation_store import ConversationStore
from ml_pipeline_pro.errors import ApiError
from ml_pipeline_pro.snippet_schemas import SnippetCandidate
from tests.integration.test_conversation_service import exercise
from tests.test_snippet_generation import Generator
from tests.test_snippet_validation import example

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("MLPP_RUN_INTEGRATION") != "1", reason="Requires real MongoDB/API"
    ),
]


@pytest.mark.parametrize("rejected", [False, True])
def test_real_draft_replay_project_scope_and_no_action_or_domain_request(rejected):
    async def run(settings, connections, database, store, context, client, transport):
        model = Generator(
            ModelStep(snippet=SnippetCandidate(code="import subprocess" if rejected else example()))
        )
        transport.request = AsyncMock(wraps=transport.request)
        body = ChatRequest(
            request_id="snippet", message="Generate Python listing", expected_revision=0
        )
        first = await ConversationService(settings, store, model, transport).chat(context, body)
        assert first.status == "completed" and first.pending_action is None
        assert first.snippet.status == ("rejected" if rejected else "validated")
        assert first.snippet.review_required is True
        assert first.snippet.code == (None if rejected else example())
        assert await store.actions.count_documents({}) == 0
        restarted = ConversationService(
            settings, ConversationStore(database, settings), None, transport
        )
        assert await restarted.chat(context, body) == first
        history = await store.history(context.project_id, first.conversation_id)
        assert history.turns[0].snippet == first.snippet
        with pytest.raises(ApiError) as caught:
            await store.history("foreign-project", first.conversation_id)
        assert caught.value.code == "conversation_not_found"
        transport.request.assert_not_awaited()
        model.generate_snippet.assert_awaited_once()

    exercise(run)


def test_schema_v1_turn_without_snippet_reads_without_generated_evidence():
    async def run(settings, connections, database, store, context, client, transport):
        body = ChatRequest(request_id="legacy", message="Generate Python", expected_revision=0)
        first = await ConversationService(settings, store, Generator(), transport).chat(
            context, body
        )
        await store.turns.update_one({"_id": first.turn_id}, {"$unset": {"public.snippet": ""}})
        history = await store.history(context.project_id, first.conversation_id)
        assert history.turns[0].snippet is None
        assert await store.actions.count_documents({}) == 0

    exercise(run)
