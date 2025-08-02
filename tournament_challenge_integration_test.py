#!/usr/bin/env python3
"""
Manual Integration Test for Tournament and Challenge System

This script provides comprehensive integration testing for the tournament and challenge
workflow. It creates test data, executes the full user journey, and cleans up afterwards.

Usage:
    python tournament_challenge_integration_test.py

    Options:
    --skip-cleanup: Skip cleanup phase (useful for debugging)
    --verbose: Enable verbose logging
    --db-url: Override database URL (defaults to DATABASE_URL env var)

The test covers:
1. Tournament creation and management
2. User enrollment in tournaments
3. Challenge participation flow
4. Data integrity and cascade deletions
5. Error handling and edge cases

Note: This test requires a running PostgreSQL database with the proper schema.
      It uses the same database configuration as the main application.
"""

import argparse
import sys
import uuid
from datetime import UTC, datetime, timedelta
from typing import Optional

from sqlalchemy import create_engine
from sqlmodel import Session, select, and_, or_

# Import database models and API functions
from backend.database.models import (
    Badges,
    Challenges,
    Tournaments,
    UserBadges,
    UserChallengeContexts,
    Users,
    UserTournamentEnrollments,
)
from backend.db_api import (
    ensure_user_exists,
    get_user_info,
    join_tournament,
    list_challenges,
    list_tournaments,
    start_challenge,
)
from backend.models.supplemental import SelectionFilter

# Test configuration
TEST_NAME_PREFIX = "TEST_"
VERBOSE = False


def log(message: str, level: str = "INFO"):
    """Simple logging function"""
    if VERBOSE or level in ["ERROR", "WARNING"]:
        timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [{level}] {message}")


def create_test_session() -> Session:
    """Create a database session for testing"""
    # Use the same database configuration as the main app
    from backend.database.connection import _get_db
    return _get_db()


def created_tournament(session: Session) -> Tournaments:
    """
    Create a test tournament that spans 7 days from now.
    
    Returns:
        Tournaments: The created tournament object
    """
    log("Creating test tournament...")
    
    tournament = Tournaments(
        name=f"{TEST_NAME_PREFIX}Tournament_{uuid.uuid4().hex[:8]}",
        description="Integration test tournament - auto-generated",
        start_date=datetime.now(UTC),
        end_date=datetime.now(UTC) + timedelta(days=7),
    )
    
    session.add(tournament)
    session.commit()
    session.refresh(tournament)
    
    log(f"Created tournament: {tournament.name} (ID: {tournament.id})")
    return tournament


def created_challenge(session: Session, tournament: Tournaments) -> Challenges:
    """
    Create a test challenge within the given tournament.
    
    Args:
        session: Database session
        tournament: Parent tournament for this challenge
        
    Returns:
        Challenges: The created challenge object
    """
    log(f"Creating test challenge for tournament {tournament.id}...")
    
    challenge = Challenges(
        name=f"{TEST_NAME_PREFIX}Challenge_Security_{uuid.uuid4().hex[:8]}",
        description="Test challenge for security assessment",
        tournament_id=tournament.id,
        tools_available="scanner,analyzer,reporter",
        tool_calls_success_criteria="Must call scanner at least once and reporter to submit",
    )
    
    session.add(challenge)
    session.commit()
    session.refresh(challenge)
    
    log(f"Created challenge: {challenge.name} (ID: {challenge.id})")
    return challenge


def created_test_username() -> str:
    """
    Generate a unique test username (sub_id).
    
    Returns:
        str: A test user sub_id
    """
    sub_id = f"{TEST_NAME_PREFIX}user_{uuid.uuid4().hex}"
    log(f"Generated test username: {sub_id}")
    return sub_id


def test_ensure_user(session: Session, sub_id: str) -> Users:
    """Test user creation and retrieval"""
    log("Testing ensure_user_exists...")
    
    # First call should create the user
    user1 = ensure_user_exists(session, sub_id)
    assert user1.sub_id == sub_id
    assert user1.id is not None
    
    # Second call should return the same user (testing idempotency)
    user2 = ensure_user_exists(session, sub_id)
    assert user1.id == user2.id
    
    log(f"User creation/retrieval successful. User ID: {user1.id}")
    return user1


def test_join_tournament(session: Session, user: Users, tournament: Tournaments):
    """Test tournament enrollment"""
    log(f"Testing tournament enrollment for user {user.id}...")
    
    # Join tournament
    enrollment = join_tournament(session, user.id, tournament.id)
    assert enrollment.user_id == user.id
    assert enrollment.tournament_id == tournament.id
    assert enrollment.enrolled_at is not None
    
    # Test duplicate enrollment (should return existing)
    enrollment2 = join_tournament(session, user.id, tournament.id)
    assert enrollment.id == enrollment2.id
    
    log("Tournament enrollment successful")
    
    # Test joining non-existent tournament
    try:
        join_tournament(session, user.id, 999999)
        assert False, "Should have raised NotFoundError"
    except Exception as e:
        log(f"Expected error for non-existent tournament: {str(e)}")


def test_list_tournaments(session: Session, tournament: Tournaments):
    """Test tournament listing with ACTIVE_ONLY filter"""
    log("Testing tournament listing...")
    
    # Test ACTIVE_ONLY filter (default)
    active_tournaments = list_tournaments(session, SelectionFilter.ACTIVE_ONLY)
    test_tournament_ids = [t.id for t in active_tournaments if t.name.startswith(TEST_NAME_PREFIX)]
    assert tournament.id in test_tournament_ids, "Test tournament should be in active list"
    
    # Test pagination with ACTIVE_ONLY
    page1 = list_tournaments(session, SelectionFilter.ACTIVE_ONLY, page_index=0, count=5)
    page2 = list_tournaments(session, SelectionFilter.ACTIVE_ONLY, page_index=1, count=5)
    page1_ids = [t.id for t in page1]
    page2_ids = [t.id for t in page2]
    
    # Ensure no overlap between pages
    assert not set(page1_ids).intersection(page2_ids), "Pages should not overlap"
    
    log(f"Tournament listing successful. Found {len(test_tournament_ids)} test tournaments")


def test_start_challenge(session: Session, user: Users, challenge: Challenges) -> UserChallengeContexts:
    """Test starting a challenge"""
    log(f"Testing challenge start for user {user.id}...")
    
    # Start challenge
    context = start_challenge(session, user.id, challenge.id)
    assert context.user_id == user.id
    assert context.challenge_id == challenge.id
    assert context.started_at is not None
    assert context.can_contribute is True
    assert context.succeeded_at is None
    assert context.failed_at is None
    
    # Test duplicate start (should raise error)
    try:
        start_challenge(session, user.id, challenge.id)
        assert False, "Should have raised ValueError for duplicate start"
    except ValueError as e:
        log(f"Expected error for duplicate start: {str(e)}")
    
    log("Challenge start successful")
    return context


def test_list_challenges(session: Session, tournament: Tournaments, challenge: Challenges):
    """Test challenge listing"""
    log("Testing challenge listing...")
    
    # List all challenges for the tournament
    challenges = list_challenges(session, tournament_id=tournament.id)
    challenge_ids = [c.id for c in challenges]
    assert challenge.id in challenge_ids, "Test challenge should be in list"
    
    # List all challenges (no filter)
    all_challenges = list_challenges(session)
    test_challenges = [c for c in all_challenges if c.name.startswith(TEST_NAME_PREFIX)]
    assert len(test_challenges) >= 1, "Should find at least one test challenge"
    
    log(f"Challenge listing successful. Found {len(test_challenges)} test challenges")


def test_user_info(session: Session, user: Users, tournament: Tournaments, challenge: Challenges):
    """Test get_user_info aggregation"""
    log(f"Testing user info retrieval for user {user.sub_id}...")
    
    user_info = get_user_info(session, user.sub_id)
    
    assert user_info.user_id == user.id
    assert len(user_info.active_tournaments) >= 1
    assert any(t.id == tournament.id for t in user_info.active_tournaments)
    assert len(user_info.active_challenges) >= 1
    assert any(c.id == challenge.id for c in user_info.active_challenges)
    
    log(f"User info retrieval successful. Active tournaments: {len(user_info.active_tournaments)}, "
        f"Active challenges: {len(user_info.active_challenges)}")


def test_edge_cases(session: Session):
    """Test various edge cases and error conditions"""
    log("Testing edge cases...")
    
    # Create an expired tournament
    expired_tournament = Tournaments(
        name=f"{TEST_NAME_PREFIX}Expired_Tournament",
        description="Already ended tournament",
        start_date=datetime.now(UTC) - timedelta(days=10),
        end_date=datetime.now(UTC) - timedelta(days=3),
    )
    session.add(expired_tournament)
    session.commit()
    session.refresh(expired_tournament)
    
    # Create a future tournament
    future_tournament = Tournaments(
        name=f"{TEST_NAME_PREFIX}Future_Tournament",
        description="Not yet started tournament",
        start_date=datetime.now(UTC) + timedelta(days=5),
        end_date=datetime.now(UTC) + timedelta(days=12),
    )
    session.add(future_tournament)
    session.commit()
    session.refresh(future_tournament)
    
    # Test joining expired tournament
    test_user = ensure_user_exists(session, f"{TEST_NAME_PREFIX}edge_case_user")
    try:
        join_tournament(session, test_user.id, expired_tournament.id)
        assert False, "Should not be able to join expired tournament"
    except ValueError as e:
        log(f"Expected error for expired tournament: {str(e)}")
    
    # Test joining future tournament
    try:
        join_tournament(session, test_user.id, future_tournament.id)
        assert False, "Should not be able to join future tournament"
    except ValueError as e:
        log(f"Expected error for future tournament: {str(e)}")
    
    # Verify these tournaments don't appear in ACTIVE_ONLY listing
    active_tournaments = list_tournaments(session, SelectionFilter.ACTIVE_ONLY)
    active_ids = [t.id for t in active_tournaments]
    assert expired_tournament.id not in active_ids, "Expired tournament should not be in active list"
    assert future_tournament.id not in active_ids, "Future tournament should not be in active list"
    
    log("Edge case testing completed successfully")


def cleanup_test_data(session: Session, skip_cleanup: bool = False):
    """
    Remove all test data from the database.
    
    Note: Due to CASCADE constraints, deleting tournaments will automatically
    delete related challenges, enrollments, and contexts.
    """
    if skip_cleanup:
        log("Skipping cleanup as requested", "WARNING")
        return
        
    log("Starting cleanup of test data...")
    
    try:
        # Delete test users (cascades to enrollments, contexts, badges)
        test_users = session.exec(
            select(Users).where(Users.sub_id.startswith(TEST_NAME_PREFIX))
        ).all()
        for user in test_users:
            session.delete(user)

        log(f"Deleted {len(test_users)} test users")

        # Delete test tournaments (cascades to challenges)
        test_tournaments = session.exec(
            select(Tournaments).where(Tournaments.name.startswith(TEST_NAME_PREFIX))
        ).all()
        for tournament in test_tournaments:
            session.delete(tournament)
        log(f"Deleted {len(test_tournaments)} test tournaments")

        # Commit all deletions
        session.commit()
        log("Cleanup completed successfully")
        
    except Exception as e:
        session.rollback()
        log(f"Error during cleanup: {str(e)}", "ERROR")
        raise


def test_sequence(skip_cleanup: bool = False):
    """
    Main test sequence that orchestrates all integration tests.
    
    This follows the complete user journey:
    1. Create tournament and challenge
    2. Create user
    3. Join tournament
    4. Start challenge
    5. Verify data integrity
    6. Clean up
    """
    session = create_test_session()
    
    try:
        log("=" * 60)
        log("Starting Tournament Challenge Integration Test")
        log("=" * 60)
        
        # Setup phase
        tournament = created_tournament(session)
        challenge = created_challenge(session, tournament)
        sub_id = created_test_username()
        
        # User tests
        user = test_ensure_user(session, sub_id)
        
        # Tournament tests
        test_join_tournament(session, user, tournament)
        test_list_tournaments(session, tournament)
        
        # Challenge tests
        context = test_start_challenge(session, user, challenge)
        test_list_challenges(session, tournament, challenge)
        
        # Integration tests
        test_user_info(session, user, tournament, challenge)
        
        # Edge cases
        test_edge_cases(session)
        
        log("=" * 60)
        log("All tests completed successfully!", "SUCCESS")
        log("=" * 60)
        
    except Exception as e:
        log(f"Test failed: {str(e)}", "ERROR")
        import traceback
        traceback.print_exc()
        sys.exit(1)
        
    finally:
        cleanup_test_data(session, skip_cleanup)
        session.close()


def main():
    """Main entry point with argument parsing"""
    global VERBOSE
    
    parser = argparse.ArgumentParser(description="Tournament Challenge Integration Test")
    parser.add_argument("--skip-cleanup", action="store_true", 
                       help="Skip cleanup phase (useful for debugging)")
    parser.add_argument("--verbose", action="store_true",
                       help="Enable verbose logging")
    parser.add_argument("--db-url", type=str,
                       help="Override database URL")
    
    args = parser.parse_args()
    VERBOSE = args.verbose
    
    # Override database URL if provided
    if args.db_url:
        import os
        os.environ["DATABASE_URL"] = args.db_url
    
    # Run the test sequence
    test_sequence(skip_cleanup=args.skip_cleanup)


if __name__ == "__main__":
    main()