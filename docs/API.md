# Tournament Challenge API

A time-gated tournament system where users complete challenges to earn badges. Challenges test users' ability to make specific tool calls within an agent context.

## Communication Pattern

The typical user flow:
1. **Authentication**: User authenticates via Supabase JWT token (Bearer auth)
2. **User Context**: GET `/users/me` to retrieve UserInfo with active tournaments/challenges/badges
3. **Tournament Participation**: Browse tournaments, join via POST `/tournaments/{id}/join`
4. **Challenge Engagement**: Start challenges, submit messages, earn badges upon success
5. **Progress Tracking**: Monitor challenge status and badge collection
6. **LLM Integration**: Direct chat completions with multiple AI providers

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

### LLM Integration

**POST /llm/chat/completions**
- Create chat completions using multiple AI providers
- Supports OpenAI, Anthropic, GitHub, and Hugging Face models
- Requires authentication
- Request: ChatRequest with model, messages, temperature, max_tokens
- Response: ChatResponse with choices, usage, and token counts

**GET /llm/models**
- List available LLM models
- Only shows models with valid API keys configured
- Returns ModelInfo with id, provider, display_name, description
- Requires authentication

**GET /llm/health**
- Check LLM service health status
- Returns status (healthy/degraded/unhealthy), available model count
- Shows which providers have valid API keys
- Requires authentication

### Utility

**GET /health_check**
- Simple health check endpoint
- Returns 200 OK

**GET /**
- Root endpoint with API information
- Public endpoint

## OpenAPI Documentation

The API is fully documented using OpenAPI 3.1.0 specification. Documentation can be generated in multiple formats:

```bash
# Generate JSON format (default)
uv run python scripts/generate_openapi.py

# Generate YAML format
uv run python scripts/generate_openapi.py --format yaml

# Access interactive docs (when server is running)
# http://localhost:8080/docs - Swagger UI
# http://localhost:8080/redoc - ReDoc
```

Generated files:
- `openapi.json` - Complete OpenAPI specification in JSON
- `openapi.yaml` - Complete OpenAPI specification in YAML

## Testing

### API Testing

```bash
# Test API endpoints
scripts/test_api.sh

# Run comprehensive test suite
make test_all

# Run LLM-specific tests
make test_llm
make test_llm_verbose
```

### Validation

```bash
# Quick development validation
make quick_validate

# Complete pre-commit validation
make validate
```

The test suite includes:
- Unit tests for all LLM functionality
- Property-based testing using Hypothesis
- Integration tests with real API calls
- Model availability and API key validation
- Response format consistency testing
