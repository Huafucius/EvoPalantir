from aos.model.context import materialize_session_context
from aos.model.history import SessionHistoryMessage


def test_materialize_projects_user_and_assistant_text_messages() -> None:
    history = [
        SessionHistoryMessage.user_text(seq=1, text="hello"),
        SessionHistoryMessage.assistant_text(seq=2, text="world"),
    ]

    context = materialize_session_context("session-1", history, folded_refs=set())

    assert [message.wire for message in context.messages] == [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "world"},
    ]


def test_materialize_uses_latest_completed_compaction_pair_as_boundary() -> None:
    marker = SessionHistoryMessage.compaction_marker(seq=3, from_seq=1, to_seq=2)

    history = [
        SessionHistoryMessage.user_text(seq=1, text="old-1"),
        SessionHistoryMessage.user_text(seq=2, text="old-2"),
        marker,
        SessionHistoryMessage.compaction_summary(seq=4, text="summary", parent_id=marker.id),
        SessionHistoryMessage.user_text(seq=5, text="new-work"),
    ]

    context = materialize_session_context("session-1", history, folded_refs=set())

    assert [message.wire["content"] for message in context.messages] == [
        "What did we do so far?",
        "summary",
        "new-work",
    ]
