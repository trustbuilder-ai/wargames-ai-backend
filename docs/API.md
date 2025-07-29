# Tournament Challenge API

A time-gated tournament system where users complete challenges to earn badges. Challenges test users' ability to make specific tool calls within an agent context.

## Communication Pattern

The typical user flow:
1. **Authentication**: User authenticates via Supabase JWT token (Bearer auth)
2. **User Context**: GET `/users/me` to retrieve UserInfo with active tournaments/challenges/badges
3. **Tournament Participation**: Browse tournaments, join via POST `/tournaments/{id}/join`
4. **Challenge Engagement**: Start challenges, submit messages, earn badges upon success
5. **Progress Tracking**: Monitor challenge status and badge collection

## API Routes

### User Management

**GET /users/me**
- Returns UserInfo with user's active tournaments, challenges, and earned badges
- Requires authentication


### Tournaments

**GET /tournaments**
- Lists tournaments with SelectionFilter (PAST, ACTIVE, FUTURE, etc.)
- Supports pagination (page_index, count)
- Public endpoint

**GET /tournaments/{tournament_id}**
- Returns specific Tournaments details
- Requires authentication

**POST /tournaments/{tournament_id}/join**
- Enrolls authenticated user in tournament
- Creates UserTournamentEnrollments record

### Challenges

**GET /challenges**
- Lists challenges, optionally filtered by tournament_id
- Returns Challenges with tool requirements
- Requires authentication

**POST /challenges/{challenge_id}/start**
- Initiates challenge for user
- Creates UserChallengeContexts with Letta agent

**POST /challenges/{challenge_id}/submit_message**
- Submits message to challenge agent
- Returns updated UserChallengeContexts
- Challenge succeeds when correct tool call is made
- Once succeeded, no further messages accepted

**GET /challenges/{challenge_id}/context**
- Returns ChallengeContextResponse with current status
- Shows if user can still contribute (can_contribute flag)
- Returns list of messages with role and indication of whether
  a tool was called.

### Badges

**GET /badges**
- Lists all badges or user's earned badges (user_badges_only flag)
- Returns Badges linked to challenges
- Requires authentication

**GET /badges/{badge_id}**
- Returns specific Badges details
- Requires authentication

### Utility

**GET /health_check**
- Simple health check endpoint
- Returns 200 OK
