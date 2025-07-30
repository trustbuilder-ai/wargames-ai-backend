from datetime import datetime
from typing import List, Optional

from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKeyConstraint, Identity, Index, Integer, PrimaryKeyConstraint, Text, UniqueConstraint, text
from sqlmodel import Field, Relationship, SQLModel

class Tournaments(SQLModel, table=True):
    __table_args__ = (
        PrimaryKeyConstraint('id', name='tournaments_pkey'),
        Index('idx_tournaments_dates', 'start_date', 'end_date')
    )

    id: Optional[int] = Field(default=None, sa_column=Column('id', Integer, primary_key=True))
    name: str = Field(sa_column=Column('name', Text))
    start_date: datetime = Field(sa_column=Column('start_date', DateTime(True)))
    end_date: datetime = Field(sa_column=Column('end_date', DateTime(True)))
    description: Optional[str] = Field(default=None, sa_column=Column('description', Text))

    challenges: List['Challenges'] = Relationship(back_populates='tournament')
    user_tournament_enrollments: List['UserTournamentEnrollments'] = Relationship(back_populates='tournament')


class Users(SQLModel, table=True):
    __table_args__ = (
        PrimaryKeyConstraint('id', name='users_pkey'),
        UniqueConstraint('sub_id', name='users_sub_id_key'),
        Index('idx_users_sub_id', 'sub_id')
    )

    id: Optional[int] = Field(default=None, sa_column=Column('id', Integer, primary_key=True))
    sub_id: str = Field(sa_column=Column('sub_id', Text))

    user_tournament_enrollments: List['UserTournamentEnrollments'] = Relationship(back_populates='user')
    user_challenge_contexts: List['UserChallengeContexts'] = Relationship(back_populates='user')
    user_message_metadata: List['UserMessageMetadata'] = Relationship(back_populates='user')
    user_badges: List['UserBadges'] = Relationship(back_populates='user')


class Challenges(SQLModel, table=True):
    __table_args__ = (
        ForeignKeyConstraint(['tournament_id'], ['tournaments.id'], ondelete='CASCADE', name='fk_challenge_tournament'),
        PrimaryKeyConstraint('id', name='challenges_pkey'),
        Index('idx_challenges_tournament_id', 'tournament_id')
    )

    id: Optional[int] = Field(default=None, sa_column=Column('id', Integer, primary_key=True))
    name: str = Field(sa_column=Column('name', Text))
    tournament_id: int = Field(sa_column=Column('tournament_id', Integer))
    description: Optional[str] = Field(default=None, sa_column=Column('description', Text))
    tools_available: Optional[str] = Field(default=None, sa_column=Column('tools_available', Text))
    tool_calls_success_criteria: Optional[str] = Field(default=None, sa_column=Column('tool_calls_success_criteria', Text))

    tournament: Optional['Tournaments'] = Relationship(back_populates='challenges')
    badges: List['Badges'] = Relationship(back_populates='challenge')
    user_challenge_contexts: List['UserChallengeContexts'] = Relationship(back_populates='challenge')
    user_message_metadata: List['UserMessageMetadata'] = Relationship(back_populates='challenge')


class UserTournamentEnrollments(SQLModel, table=True):
    __tablename__ = 'user_tournament_enrollments'
    __table_args__ = (
        ForeignKeyConstraint(['tournament_id'], ['tournaments.id'], ondelete='CASCADE', name='fk_enrollment_tournament'),
        ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE', name='fk_enrollment_user'),
        PrimaryKeyConstraint('id', name='user_tournament_enrollments_pkey'),
        UniqueConstraint('user_id', 'tournament_id', name='uq_user_tournament'),
        Index('idx_enrollments_tournament_id', 'tournament_id'),
        Index('idx_enrollments_user_id', 'user_id')
    )

    id: Optional[int] = Field(default=None, sa_column=Column('id', Integer, primary_key=True))
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
    letta_agent_id: Optional[str] = Field(default=None, sa_column=Column('letta_agent_id', Text))
    succeeded_at: Optional[datetime] = Field(default=None, sa_column=Column('succeeded_at', DateTime(True)))

    challenge: Optional['Challenges'] = Relationship(back_populates='user_challenge_contexts')
    user: Optional['Users'] = Relationship(back_populates='user_challenge_contexts')


class UserMessageMetadata(SQLModel, table=True):
    __tablename__ = 'user_message_metadata'
    __table_args__ = (
        ForeignKeyConstraint(['challenge_id'], ['challenges.id'], name='user_message_metadata_challenge_id_fkey'),
        ForeignKeyConstraint(['user_id'], ['users.id'], name='user_message_metadata_user_id_fkey'),
        PrimaryKeyConstraint('id', name='user_message_metadata_pkey'),
        Index('idx_user_message_metadata_created_at', 'created_at'),
        Index('idx_user_message_metadata_user_id', 'user_id')
    )

    id: Optional[int] = Field(default=None, sa_column=Column('id', BigInteger, Identity(start=1, increment=1, minvalue=1, maxvalue=9223372036854775807, cycle=False, cache=1), primary_key=True))
    created_at: datetime = Field(sa_column=Column('created_at', DateTime(True), server_default=text('now()')))
    user_id: Optional[int] = Field(default=None, sa_column=Column('user_id', Integer))
    content_length: Optional[int] = Field(default=None, sa_column=Column('content_length', BigInteger))
    challenge_id: Optional[int] = Field(default=None, sa_column=Column('challenge_id', Integer))

    challenge: Optional['Challenges'] = Relationship(back_populates='user_message_metadata')
    user: Optional['Users'] = Relationship(back_populates='user_message_metadata')


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
