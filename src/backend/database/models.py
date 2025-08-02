from datetime import datetime
from typing import List, Optional

from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKeyConstraint, Identity, Index, Integer, PrimaryKeyConstraint, String, Text, UniqueConstraint, text
from sqlmodel import Field, Relationship, SQLModel

class Tournaments(SQLModel, table=True):
    __table_args__ = (
        PrimaryKeyConstraint('id', name='tournaments_pkey'),
        UniqueConstraint('id', name='tournaments_id_key'),
        Index('idx_tournaments_dates', 'start_date', 'end_date')
    )

    id: Optional[int] = Field(default=None, sa_column=Column('id', Integer, Identity(start=1, increment=1, minvalue=1, maxvalue=2147483647, cycle=False, cache=1), primary_key=True))
    name: str = Field(sa_column=Column('name', Text))
    start_date: datetime = Field(sa_column=Column('start_date', DateTime(True)))
    end_date: datetime = Field(sa_column=Column('end_date', DateTime(True)))
    description: Optional[str] = Field(default=None, sa_column=Column('description', Text))

    challenges: List['Challenges'] = Relationship(back_populates='tournament')
    user_tournament_enrollments: List['UserTournamentEnrollments'] = Relationship(back_populates='tournament')


class Users(SQLModel, table=True):
    __table_args__ = (
        PrimaryKeyConstraint('id', name='users_pkey'),
        UniqueConstraint('id', name='users_id_key'),
        UniqueConstraint('sub_id', name='users_sub_id_key'),
        Index('idx_users_sub_id', 'sub_id')
    )

    id: Optional[int] = Field(default=None, sa_column=Column('id', Integer, Identity(start=1, increment=1, minvalue=1, maxvalue=2147483647, cycle=False, cache=1), primary_key=True))
    sub_id: str = Field(sa_column=Column('sub_id', Text))

    user_tournament_enrollments: List['UserTournamentEnrollments'] = Relationship(back_populates='user')
    user_challenge_contexts: List['UserChallengeContexts'] = Relationship(back_populates='user')
    user_badges: List['UserBadges'] = Relationship(back_populates='user')


class Challenges(SQLModel, table=True):
    __table_args__ = (
        ForeignKeyConstraint(['tournament_id'], ['tournaments.id'], ondelete='CASCADE', name='fk_challenge_tournament'),
        PrimaryKeyConstraint('id', name='challenges_pkey'),
        UniqueConstraint('id', name='challenges_id_key'),
        Index('idx_challenges_tournament_id', 'tournament_id')
    )

    id: Optional[int] = Field(default=None, sa_column=Column('id', Integer, Identity(start=1, increment=1, minvalue=1, maxvalue=2147483647, cycle=False, cache=1), primary_key=True))
    name: str = Field(sa_column=Column('name', Text))
    tournament_id: int = Field(sa_column=Column('tournament_id', Integer))
    description: Optional[str] = Field(default=None, sa_column=Column('description', Text))
    required_tools: Optional[str] = Field(default=None, sa_column=Column('required_tools', Text))
    evaluation_prompt: Optional[str] = Field(default=None, sa_column=Column('evaluation_prompt', Text))

    tournament: Optional['Tournaments'] = Relationship(back_populates='challenges')
    badges: List['Badges'] = Relationship(back_populates='challenge')
    user_challenge_contexts: List['UserChallengeContexts'] = Relationship(back_populates='challenge')


class UserTournamentEnrollments(SQLModel, table=True):
    __tablename__ = 'user_tournament_enrollments'
    __table_args__ = (
        ForeignKeyConstraint(['tournament_id'], ['tournaments.id'], ondelete='CASCADE', name='fk_enrollment_tournament'),
        ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE', name='fk_enrollment_user'),
        PrimaryKeyConstraint('id', name='user_tournament_enrollments_pkey'),
        UniqueConstraint('id', name='user_tournament_enrollments_id_key'),
        UniqueConstraint('user_id', 'tournament_id', name='uq_user_tournament'),
        Index('idx_enrollments_tournament_id', 'tournament_id'),
        Index('idx_enrollments_user_id', 'user_id')
    )

    id: Optional[int] = Field(default=None, sa_column=Column('id', Integer, Identity(start=1, increment=1, minvalue=1, maxvalue=2147483647, cycle=False, cache=1), primary_key=True))
    enrolled_at: datetime = Field(sa_column=Column('enrolled_at', DateTime(True)))
    user_id: int = Field(sa_column=Column('user_id', Integer))
    tournament_id: int = Field(sa_column=Column('tournament_id', Integer))

    tournament: Optional['Tournaments'] = Relationship(back_populates='user_tournament_enrollments')
    user: Optional['Users'] = Relationship(back_populates='user_tournament_enrollments')


class Badges(SQLModel, table=True):
    __table_args__ = (
        ForeignKeyConstraint(['challenge_id'], ['challenges.id'], ondelete='CASCADE', name='fk_badge_challenge'),
        PrimaryKeyConstraint('id', name='badges_pkey'),
        Index('idx_badges_challenge_id', 'challenge_id')
    )

    id: Optional[int] = Field(default=None, sa_column=Column('id', Integer, primary_key=True))
    challenge_id: int = Field(sa_column=Column('challenge_id', Integer))

    challenge: Optional['Challenges'] = Relationship(back_populates='badges')
    user_badges: List['UserBadges'] = Relationship(back_populates='badge')


class UserChallengeContexts(SQLModel, table=True):
    __tablename__ = 'user_challenge_contexts'
    __table_args__ = (
        ForeignKeyConstraint(['challenge_id'], ['challenges.id'], ondelete='CASCADE', name='fk_context_challenge'),
        ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE', name='fk_context_user'),
        PrimaryKeyConstraint('id', name='user_challenge_contexts_pkey'),
        UniqueConstraint('user_id', 'challenge_id', name='uq_user_challenge'),
        Index('idx_contexts_challenge_id', 'challenge_id'),
        Index('idx_contexts_user_id', 'user_id')
    )

    id: Optional[int] = Field(default=None, sa_column=Column('id', Integer, primary_key=True))
    can_contribute: bool = Field(sa_column=Column('can_contribute', Boolean))
    challenge_id: int = Field(sa_column=Column('challenge_id', Integer))
    started_at: datetime = Field(sa_column=Column('started_at', DateTime(True)))
    user_id: int = Field(sa_column=Column('user_id', Integer))

    challenge: Optional['Challenges'] = Relationship(back_populates='user_challenge_contexts')
    user: Optional['Users'] = Relationship(back_populates='user_challenge_contexts')
    challenge_evaluations: List['ChallengeEvaluations'] = Relationship(back_populates='user_challenge_context')
    user_challenge_context_messages: List['UserChallengeContextMessages'] = Relationship(back_populates='user_challenge_context')


class ChallengeEvaluations(SQLModel, table=True):
    __tablename__ = 'challenge_evaluations'
    __table_args__ = (
        ForeignKeyConstraint(['user_challenge_context_id'], ['user_challenge_contexts.id'], ondelete='CASCADE', name='challenge_evaluation_user_challenge_context_id_fkey'),
        PrimaryKeyConstraint('id', name='challenge_evaluation_pkey'),
        UniqueConstraint('id', name='challenge_evaluation_id_key')
    )

    id: Optional[int] = Field(default=None, sa_column=Column('id', BigInteger, Identity(start=1, increment=1, minvalue=1, maxvalue=9223372036854775807, cycle=False, cache=1), primary_key=True))
    created_at: datetime = Field(sa_column=Column('created_at', DateTime(True), server_default=text('now()')))
    deleted_at: Optional[datetime] = Field(default=None, sa_column=Column('deleted_at', DateTime(True)))
    succeeded_at: Optional[datetime] = Field(default=None, sa_column=Column('succeeded_at', DateTime(True)))
    failed_at: Optional[datetime] = Field(default=None, sa_column=Column('failed_at', DateTime(True)))
    errored_at: Optional[datetime] = Field(default=None, sa_column=Column('errored_at', DateTime(True)))
    result: Optional[str] = Field(default=None, sa_column=Column('result', Text))
    result_text: Optional[str] = Field(default=None, sa_column=Column('result_text', Text))
    result_type: Optional[str] = Field(default=None, sa_column=Column('result_type', String))
    user_challenge_context_id: Optional[int] = Field(default=None, sa_column=Column('user_challenge_context_id', Integer))

    user_challenge_context: Optional['UserChallengeContexts'] = Relationship(back_populates='challenge_evaluations')


class UserBadges(SQLModel, table=True):
    __tablename__ = 'user_badges'
    __table_args__ = (
        ForeignKeyConstraint(['badge_id'], ['badges.id'], ondelete='CASCADE', name='fk_user_badge_badge'),
        ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE', name='fk_user_badge_user'),
        PrimaryKeyConstraint('id', name='user_badges_pkey'),
        UniqueConstraint('user_id', 'badge_id', name='uq_user_badge'),
        Index('idx_user_badges_badge_id', 'badge_id'),
        Index('idx_user_badges_user_id', 'user_id')
    )

    id: Optional[int] = Field(default=None, sa_column=Column('id', Integer, primary_key=True))
    user_id: int = Field(sa_column=Column('user_id', Integer))
    badge_id: int = Field(sa_column=Column('badge_id', Integer))
    awarded_at: datetime = Field(sa_column=Column('awarded_at', DateTime(True)))

    badge: Optional['Badges'] = Relationship(back_populates='user_badges')
    user: Optional['Users'] = Relationship(back_populates='user_badges')


class UserChallengeContextMessages(SQLModel, table=True):
    __tablename__ = 'user_challenge_context_messages'
    __table_args__ = (
        ForeignKeyConstraint(['user_challenge_context_id'], ['user_challenge_contexts.id'], ondelete='CASCADE', name='user_challenge_context_messages_user_challenge_context_id_fkey'),
        PrimaryKeyConstraint('id', name='user_message_metadata_pkey'),
        Index('idx_user_message_metadata_created_at', 'created_at'),
        Index('idx_user_message_metadata_user_id', 'user_challenge_context_id')
    )

    id: Optional[int] = Field(default=None, sa_column=Column('id', BigInteger, Identity(start=1, increment=1, minvalue=1, maxvalue=9223372036854775807, cycle=False, cache=1), primary_key=True))
    created_at: datetime = Field(sa_column=Column('created_at', DateTime(True), server_default=text('now()')))
    user_challenge_context_id: int = Field(sa_column=Column('user_challenge_context_id', Integer))
    content: str = Field(sa_column=Column('content', Text))
    content_type: str = Field(sa_column=Column('content_type', String))
    model: Optional[str] = Field(default=None, sa_column=Column('model', Text))
    is_user_provided: Optional[bool] = Field(default=None, sa_column=Column('is_user_provided', Boolean))
    role: Optional[str] = Field(default=None, sa_column=Column('role', String))

    user_challenge_context: Optional['UserChallengeContexts'] = Relationship(back_populates='user_challenge_context_messages')
