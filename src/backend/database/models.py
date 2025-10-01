from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKeyConstraint,
    Identity,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, Relationship, SQLModel


class ChatTemplateContainer(SQLModel, table=True):
    __tablename__ = "chat_template_container"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="tournaments_pkey"),
        UniqueConstraint("id", name="tournaments_id_key"),
        Index("idx_chat_template_container_type", "type"),
        Index("idx_tournaments_dates", "start_date", "end_date"),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(
            "id",
            Integer,
            Identity(
                start=1,
                increment=1,
                minvalue=1,
                maxvalue=2147483647,
                cycle=False,
                cache=1,
            ),
            primary_key=True,
        ),
    )
    name: str = Field(sa_column=Column("name", Text))
    type: str = Field(
        sa_column=Column(
            "type",
            Text,
            server_default=text("'challenge'::text"),
            comment="Type of container: challenge, tutorial, assessment, etc.",
        )
    )
    description: str | None = Field(default=None, sa_column=Column("description", Text))
    start_date: datetime | None = Field(
        default=None,
        sa_column=Column(
            "start_date",
            DateTime(True),
            comment="Container start date. NULL means no start restriction (always started)",
        ),
    )
    end_date: datetime | None = Field(
        default=None,
        sa_column=Column(
            "end_date",
            DateTime(True),
            comment="Container end date. NULL means no end restriction (never ends)",
        ),
    )

    chat_template: list["ChatTemplate"] = Relationship(
        back_populates="chat_template_container"
    )


class Users(SQLModel, table=True):
    __table_args__ = (
        PrimaryKeyConstraint("id", name="users_pkey"),
        UniqueConstraint("id", name="users_id_key"),
        UniqueConstraint("sub_id", name="users_sub_id_key"),
        Index("idx_users_sub_id", "sub_id"),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(
            "id",
            Integer,
            Identity(
                start=1,
                increment=1,
                minvalue=1,
                maxvalue=2147483647,
                cycle=False,
                cache=1,
            ),
            primary_key=True,
        ),
    )
    sub_id: str = Field(sa_column=Column("sub_id", Text))

    chat_context: list["ChatContext"] = Relationship(back_populates="user")
    user_badges: list["UserBadges"] = Relationship(back_populates="user")


class ChatTemplate(SQLModel, table=True):
    __tablename__ = "chat_template"
    __table_args__ = (
        ForeignKeyConstraint(
            ["chat_template_container_id"],
            ["chat_template_container.id"],
            ondelete="CASCADE",
            name="fk_chat_template_container",
        ),
        PrimaryKeyConstraint("id", name="challenges_pkey"),
        UniqueConstraint("id", name="challenges_id_key"),
        Index("idx_chat_template_container_id", "chat_template_container_id"),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(
            "id",
            Integer,
            Identity(
                start=1,
                increment=1,
                minvalue=1,
                maxvalue=2147483647,
                cycle=False,
                cache=1,
            ),
            primary_key=True,
        ),
    )
    name: str = Field(sa_column=Column("name", Text))
    chat_template_container_id: int = Field(
        sa_column=Column("chat_template_container_id", Integer)
    )
    description: str | None = Field(default=None, sa_column=Column("description", Text))
    required_tools: str | None = Field(
        default=None, sa_column=Column("required_tools", Text)
    )
    evaluation_prompt: str | None = Field(
        default=None, sa_column=Column("evaluation_prompt", Text)
    )
    message_tree: dict | None = Field(
        default=None, sa_column=Column("message_tree", JSONB)
    )

    chat_template_container: Optional["ChatTemplateContainer"] = Relationship(
        back_populates="chat_template"
    )
    badges: list["Badges"] = Relationship(back_populates="chat_template")
    chat_context: list["ChatContext"] = Relationship(back_populates="chat_template")


class Badges(SQLModel, table=True):
    __table_args__ = (
        ForeignKeyConstraint(
            ["chat_template_id"],
            ["chat_template.id"],
            ondelete="CASCADE",
            name="fk_badge_chat_template",
        ),
        PrimaryKeyConstraint("id", name="badges_pkey"),
        Index("idx_badges_chat_template_id", "chat_template_id"),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(
            "id",
            Integer,
            Identity(
                start=1,
                increment=1,
                minvalue=1,
                maxvalue=2147483647,
                cycle=False,
                cache=1,
            ),
            primary_key=True,
        ),
    )
    chat_template_id: int = Field(sa_column=Column("chat_template_id", Integer))

    chat_template: Optional["ChatTemplate"] = Relationship(back_populates="badges")
    user_badges: list["UserBadges"] = Relationship(back_populates="badge")


class ChatContext(SQLModel, table=True):
    __tablename__ = "chat_context"
    __table_args__ = (
        ForeignKeyConstraint(
            ["chat_template_id"],
            ["chat_template.id"],
            ondelete="CASCADE",
            name="fk_context_chat_template",
        ),
        ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE", name="fk_context_user"
        ),
        PrimaryKeyConstraint("id", name="user_challenge_contexts_pkey"),
        UniqueConstraint("user_id", "chat_template_id", name="uq_user_chat_template"),
        Index("idx_chat_context_chat_template_id", "chat_template_id"),
        Index("idx_chat_context_message_tree", "message_tree"),
        Index("idx_chat_context_user_id", "user_id"),
        {
            "comment": "Stores user-specific context for chat templates including message "
            "history"
        },
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(
            "id",
            Integer,
            Identity(
                start=1,
                increment=1,
                minvalue=1,
                maxvalue=2147483647,
                cycle=False,
                cache=1,
            ),
            primary_key=True,
        ),
    )
    can_contribute: bool = Field(sa_column=Column("can_contribute", Boolean))
    chat_template_id: int = Field(sa_column=Column("chat_template_id", Integer))
    started_at: datetime = Field(sa_column=Column("started_at", DateTime(True)))
    user_id: int = Field(sa_column=Column("user_id", Integer))
    message_tree: dict | None = Field(
        default=None,
        sa_column=Column(
            "message_tree",
            JSONB,
            comment="Hierarchical message tree structure in JSONB format, matching chat_template.message_tree structure",
        ),
    )

    chat_template: Optional["ChatTemplate"] = Relationship(
        back_populates="chat_context"
    )
    user: Optional["Users"] = Relationship(back_populates="chat_context")
    challenge_evaluations: list["ChallengeEvaluations"] = Relationship(
        back_populates="chat_context"
    )


class ChallengeEvaluations(SQLModel, table=True):
    __tablename__ = "challenge_evaluations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["chat_context_id"],
            ["chat_context.id"],
            ondelete="CASCADE",
            name="fk_evaluation_chat_context",
        ),
        PrimaryKeyConstraint("id", name="challenge_evaluation_pkey"),
        UniqueConstraint("id", name="challenge_evaluation_id_key"),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(
            "id",
            BigInteger,
            Identity(
                start=1,
                increment=1,
                minvalue=1,
                maxvalue=9223372036854775807,
                cycle=False,
                cache=1,
            ),
            primary_key=True,
        ),
    )
    created_at: datetime = Field(
        sa_column=Column("created_at", DateTime(True), server_default=text("now()"))
    )
    deleted_at: datetime | None = Field(
        default=None, sa_column=Column("deleted_at", DateTime(True))
    )
    succeeded_at: datetime | None = Field(
        default=None, sa_column=Column("succeeded_at", DateTime(True))
    )
    failed_at: datetime | None = Field(
        default=None, sa_column=Column("failed_at", DateTime(True))
    )
    errored_at: datetime | None = Field(
        default=None, sa_column=Column("errored_at", DateTime(True))
    )
    result: str | None = Field(default=None, sa_column=Column("result", Text))
    result_text: str | None = Field(default=None, sa_column=Column("result_text", Text))
    result_type: str | None = Field(
        default=None, sa_column=Column("result_type", String)
    )
    chat_context_id: int | None = Field(
        default=None, sa_column=Column("chat_context_id", Integer)
    )
    processed_at: datetime | None = Field(
        default=None, sa_column=Column("processed_at", DateTime(True))
    )
    processing_started_at: datetime | None = Field(
        default=None, sa_column=Column("processing_started_at", DateTime(True))
    )
    processor_id: str | None = Field(
        default=None, sa_column=Column("processor_id", String)
    )
    context_message_leaf_id: int | None = Field(
        default=None, sa_column=Column("context_message_leaf_id", Integer)
    )

    chat_context: Optional["ChatContext"] = Relationship(
        back_populates="challenge_evaluations"
    )


class UserBadges(SQLModel, table=True):
    __tablename__ = "user_badges"
    __table_args__ = (
        ForeignKeyConstraint(
            ["badge_id"], ["badges.id"], ondelete="CASCADE", name="fk_user_badge_badge"
        ),
        ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE", name="fk_user_badge_user"
        ),
        PrimaryKeyConstraint("id", name="user_badges_pkey"),
        UniqueConstraint("user_id", "badge_id", name="uq_user_badge"),
        Index("idx_user_badges_badge_id", "badge_id"),
        Index("idx_user_badges_user_id", "user_id"),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(
            "id",
            Integer,
            Identity(
                start=1,
                increment=1,
                minvalue=1,
                maxvalue=2147483647,
                cycle=False,
                cache=1,
            ),
            primary_key=True,
        ),
    )
    user_id: int = Field(sa_column=Column("user_id", Integer))
    badge_id: int = Field(sa_column=Column("badge_id", Integer))
    awarded_at: datetime = Field(sa_column=Column("awarded_at", DateTime(True)))

    badge: Optional["Badges"] = Relationship(back_populates="user_badges")
    user: Optional["Users"] = Relationship(back_populates="user_badges")
