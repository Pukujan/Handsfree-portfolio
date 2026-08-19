from __future__ import annotations

from dataclasses import replace
from threading import RLock

from handsfree_portfolio.domain.conversation import ConversationState


class StaleGenerationError(RuntimeError):
    pass


class InMemoryConversationSessions:
    def __init__(self) -> None:
        self._states: dict[str, ConversationState] = {}
        self._lock = RLock()

    def begin_turn(self, conversation_id: str) -> ConversationState:
        if not conversation_id:
            raise ValueError("conversation_id must not be empty")
        with self._lock:
            previous = self._states.get(conversation_id, ConversationState(conversation_id=conversation_id))
            state = ConversationState(
                conversation_id=conversation_id,
                active_generation=previous.active_generation + 1,
                status="idle",
                active_subject=previous.active_subject,
                referents=dict(previous.referents),
            )
            self._states[conversation_id] = state
            return state

    def get(self, conversation_id: str) -> ConversationState:
        with self._lock:
            return self._states.get(conversation_id, ConversationState(conversation_id=conversation_id))

    def owns_generation(self, conversation_id: str, generation: int) -> bool:
        with self._lock:
            return self.get(conversation_id).active_generation == generation

    def update(
        self,
        conversation_id: str,
        generation: int,
        *,
        status: str | None = None,
        active_subject: str | None = None,
        referents: dict[str, str] | None = None,
    ) -> ConversationState:
        with self._lock:
            current = self.get(conversation_id)
            if current.active_generation != generation:
                raise StaleGenerationError(
                    f"generation {generation} no longer owns conversation {conversation_id}"
                )
            updated = replace(
                current,
                status=status if status is not None else current.status,
                active_subject=active_subject if active_subject is not None else current.active_subject,
                referents=dict(referents) if referents is not None else dict(current.referents),
            )
            self._states[conversation_id] = updated
            return updated
