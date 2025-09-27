from pydantic import BaseModel, Field
from strenum import StrEnum

from backend.database.models import (
    Badges,
    ChatTemplate,
    ChatTemplateContainer,
    UserChatTemplateContext,
)
from backend.models.evaluation import EvalResult
from backend.models.llm import ToolCall


class UserInfo(BaseModel):
    """
    Represents a user's information including active chat template containers, chat templates,
    and badges.
    """

    user_id: int
    email: str | None = None
    active_chat_template_containers: list[ChatTemplateContainer]
    active_chat_template_contexts: list[UserChatTemplateContext]
    badges: list[Badges]
    eval_results: list[EvalResult] = []

    class Config:
        from_attributes = True
        arbitrary_types_allowed = True  # Allow using SQLModel types directly


class Message(BaseModel):
    role: str
    content: str
    is_tool_call: bool = False
    tool_name: str | None = None
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None


class ChatTemplateContextResponse(BaseModel):
    """
    Represents the full message context for a chat template, including user chat template context
    and messages.
    """

    user_chat_template_context: UserChatTemplateContext
    messages: list["MessageContainer"] = []
    eval_result: EvalResult | None = None
    remaining_message_count: int = 0


class SelectionFilter(StrEnum):
    PAST_ONLY = "PAST"
    ACTIVE_ONLY = "ACTIVE"
    FUTURE_ONLY = "FUTURE"
    PAST_AND_ACTIVE = "PAST_AND_ACTIVE"
    ACTIVE_AND_FUTURE = "ACTIVE_AND_FUTURE"


# ============================================================================
# ScrollyTell models for message tree structures
# ============================================================================


class MessageContainer(BaseModel):
    """Container for a message with its position in the message tree.

    Used for the ScrollyTell feature to represent hierarchical message structures.

    Attributes:
        id_in_tree: Tree-scoped identifier for the message container (not database ID).
        parent_id_in_tree: Tree-scoped ID of the parent message, null for root.
        message: The actual message content.
    """

    id_in_tree: int = Field(
        ..., description="Tree-scoped identifier for the message container"
    )
    parent_id_in_tree: int | None = Field(
        default=None, description="Tree-scoped ID of the parent message, null for root"
    )
    message: Message = Field(..., description="The actual message content")


# MessageTree is represented as a List type alias
MessageTree = list[MessageContainer]


class ChatTemplateContextLLMResponse(BaseModel):
    """
    Represents a response from the LLM call.
    """

    remaining_message_count: int
    messages: list[Message]


class ChatTemplatesPublic(BaseModel):
    chat_template: ChatTemplate
    container_name: str
