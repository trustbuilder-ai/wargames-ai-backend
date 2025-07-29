# Agent instructions for TrustBuilder Wargames AI Backend

This file provides guidance for AI coding agents working on the TrustBuilder Wargames AI Backend project. This project is a FastAPI-based backend service that integrates with Supabase for authentication and Letta for AI agent functionality in a competitive wargames platform.

## Table of Contents

### Getting Started

- [Core Rules & AI Behavior](#core-rules--ai-behavior) - Fundamental guidelines
- [Architecture Overview](#architecture-overview) - System design and data flow
- [Decision Framework for Agents](#decision-framework-for-agents) - Conflict resolution and priorities

### Development Workflow

- [Codebase Structure & Modularity](#codebase-structure--modularity) - Organization principles
- [Development Commands & Environment](#development-commands--environment) - Setup and quality checks
- [Style, Patterns & Documentation](#style-patterns--documentation) - Coding standards and patterns
- [API Development Guidelines](#api-development-guidelines) - FastAPI patterns and best practices
- [Agent Integration](#agent-integration) - Letta agent patterns and workflows
- [Code Review & PR Guidelines](#code-review--pr-guidelines) - Quality assurance

### Reference

- [Unified Command Reference](#unified-command-reference) - All commands with error recovery
- [Agent Quick Reference](#agent-quick-reference---critical-reminders) - Essential commands and patterns
- [Requests to Humans](#requests-to-humans) - Escalation and clarifications
- [Agent Learning Documentation](#agent-learning-documentation) - Pattern discovery and documentation

## Core Rules & AI Behavior

### Fundamental Guidelines

- Follow FastAPI patterns and conventions established in the codebase
- Always use SQLModel for database operations with proper session management
- Integrate with Supabase for authentication using the established patterns
- Use Letta client for AI agent functionality following existing patterns
- Maintain code quality standards using ruff and pyright
- Write comprehensive tests for new functionality
- Never assume missing context - ask questions if uncertain about requirements
- Never use libraries not listed in `pyproject.toml` - ask user to confirm before adding new dependencies

### Security and Safety

- Always validate and sanitize user inputs in API endpoints
- Use proper authentication and authorization patterns with Supabase
- Never expose sensitive data like API keys or database credentials
- Follow security best practices for handling JWT tokens and user sessions
- Validate data using Pydantic models before database operations

### Code Quality Standards

- Follow Test-Driven Development (TDD) when possible
- Write comprehensive docstrings using Google style format
- Keep functions and files focused and modular
- Use type hints consistently throughout the codebase
- Run validation checks (`make validate`) before committing changes

## Decision Framework for Agents

When facing conflicting instructions or ambiguous situations, use this priority hierarchy:

### Priority Hierarchy

1. **Explicit user instructions** - Always override all other guidelines
2. **AGENTS.md rules** - Override general best practices when specified
3. **src/backend/ structure** - Source of truth for all file organization
4. **Project-specific patterns** - Found in existing codebase
5. **General best practices** - Default fallback for unspecified cases

### Common Conflict Resolution

#### File Structure Conflicts

- **Follow the established src/backend/ structure** as the definitive source
- Keep related functionality grouped (database/, agents/, models/)
- Use absolute imports from backend module root

#### Command Execution Conflicts

- **Prefer make commands** when available (e.g., `make ruff` over direct `uv run ruff`)
- If make commands fail, try direct commands as fallback
- Always document when deviating from standard commands

#### Documentation Update Conflicts

- Update **both AGENTS.md and related files** to maintain consistency
- When learning something new, add it to the appropriate section
- Prefer specific examples over vague instructions

### Decision Examples

#### Example 1: Missing Library

**Situation:** Code references library not in `pyproject.toml`

**Decision Process:**

1. User instruction? *(None given)*
2. AGENTS.md rule? *"Never use libraries not listed in pyproject.toml"* ✅
3. **Action:** Ask user to confirm library or find alternative

#### Example 2: Test Framework Unclear

**Situation:** Need to write tests but framework not specified

**Decision Process:**

1. User instruction? *(None given)*
2. AGENTS.md rule? *"Use pytest with clear arrange/act/assert structure"* ✅  
3. **Action:** Use pytest as specified

#### Example 3: Code Organization

**Situation:** File approaching 500 lines

**Decision Process:**

1. User instruction? *(None given)*
2. AGENTS.md rule? *"Never create a file longer than 500 lines of code"* ✅
3. **Action:** Refactor into smaller modules

### When to Stop and Ask

**Always stop and ask for clarification when:**

- Explicit user instructions conflict with safety/security practices
- Multiple AGENTS.md rules contradict each other  
- Required information is completely missing from all sources
- Actions would significantly change project architecture

**Don't stop to ask when:**

- Clear hierarchy exists to resolve the conflict
- Standard patterns can be followed safely
- Minor implementation details need decisions

## Architecture Overview

This is a FastAPI-based backend service for the TrustBuilder Wargames platform that integrates AI agents into competitive challenges. The system enables users to participate in tournaments, complete challenges, and interact with AI agents through the Letta framework.

### Data Flow

1. User authenticates via Supabase → JWT token verification
2. API requests processed through FastAPI with dependency injection
3. Database operations via SQLModel with PostgreSQL (Supabase)
4. Challenge interactions routed through Letta AI agents
5. Real-time updates and notifications via Supabase realtime

### Key Dependencies

- **FastAPI**: Web framework for building APIs
- **SQLModel**: Database ORM built on SQLAlchemy and Pydantic
- **Supabase**: Authentication and PostgreSQL database
- **Letta**: AI agent framework for challenge interactions
- **Ruff**: Code formatting and linting
- **Pyright**: Static type checking

## Codebase Structure & Modularity

### Main Components

```
src/backend/
├── server.py              # Main FastAPI application with all routes
├── db_api.py             # Database utility functions (get_user_info, ensure_user_exists)
├── database/
│   ├── connection.py     # Database connection management and session factory
│   ├── models.py         # SQLModel database models (Users, Tournaments, etc.)
│   └── locking.py        # Database locking utilities
├── models/
│   └── supplemental.py   # Pydantic response models (UserInfo, ChallengeContextResponse)
└── agents/
    └── letta.py          # Letta client integration and agent management
```

### Code Organization Rules

- **Never create a file longer than 500 lines of code.** If a file approaches this limit, refactor by splitting it into smaller, more focused modules or helper files.
- Organize code into clearly separated modules grouped by feature (database, agents, models).
- Use clear, consistent, and absolute imports within packages.
- **Never name modules/packages after existing Python libraries.** This creates import conflicts and type checking issues.
  - ❌ `src/backend/models/` (too generic, conflicts with many libraries)
  - ❌ `src/backend/client/` (conflicts with various client libraries)
  - ❌ `src/backend/database/database.py` (redundant naming)
  - ✅ `src/backend/models/supplemental.py` (specific, descriptive naming)
  - ✅ `src/backend/agents/letta.py` (specific to Letta integration)
  - ✅ `src/backend/database/connection.py` (clear purpose)

## Development Commands & Environment

### Environment Setup

The project requirements are defined in `pyproject.toml`. Your development environment should be set up automatically using the provided `Makefile`.

**Required dependencies:**
- `fastapi>=0.116.1` - Web framework
- `sqlmodel>=0.0.24` - Database ORM
- `supabase>=2.17.0` - Authentication and database
- `letta-client>=0.1.223` - AI agent integration
- `psycopg2-binary>=2.9.10` - PostgreSQL driver

**Setup commands:**
```bash
make setup          # Complete setup: uv, sync, Claude CLI, Gemini CLI
uv sync --all-groups # Alternative: manual dependency installation
```

### Code Quality

Code formatting and type checking are managed by **ruff** and **pyright** and orchestrated via the `Makefile`.

**Quality commands:**
```bash
make ruff           # Format and lint code
make type_check     # Static type checking with pyright
make validate       # Complete validation (ruff + type_check + tests)
make quick_validate # Fast validation (ruff + type_check only)
```

### Quality Evaluation Framework

Use this universal framework to assess task readiness before implementation:

**Rate task readiness (1-10 scale):**

- **Context Completeness**: All required information and patterns gathered from codebase, documentation, and requirements
- **Implementation Clarity**: Clear understanding and actionable implementation path of what needs to be built and how to build it.
- **Requirements Alignment**: Solution follows feature requirements, project patterns, conventions, and architectural decisions
- **Success Probability**: Confidence level for completing the task successfully in one pass

**Minimum thresholds for proceeding:**

- Context Completeness: 8/10 or higher
- Implementation Clarity: 7/10 or higher  
- Requirements Alignment: 8/10 or higher
- Success Probability: 7/10 or higher

**If any score is below threshold:** Stop and gather more context, clarify requirements, or escalate to humans using the [Decision Framework](#decision-framework-for-agents).

### Testing Strategy & Guidelines

**Always create comprehensive tests** for new features following the testing hierarchy below:

#### Unit Tests (Always Required)

- **Mock external dependencies** (HTTP requests, file systems, APIs) using `@patch`
- **Test business logic** and data validation thoroughly
- **Test error handling** for all failure modes and edge cases
- **Ensure deterministic behavior** - tests should pass consistently
- Use `pytest` with clear arrange/act/assert structure
- Tests should be created in a `tests/` folder, mirroring the `src/backend/` structure

#### Integration Tests (Required for External Dependencies)

- **Test real external integrations** at least once during implementation
- **Verify actual URLs, APIs, and data formats** work as expected
- **Document any external dependencies** that could change over time
- **Use real test data** when feasible, fallback to representative samples
- **Include in implementation validation** but may be excluded from CI if unreliable

#### When to Mock vs Real Testing

- **Mock for**: Unit tests, CI/CD pipelines, deterministic behavior, fast feedback
- **Real test for**: Initial implementation validation, external API changes, data format verification
- **Always test real integrations** during feature development, then mock for ongoing automated tests
- **Document real test results** in implementation logs for future reference

#### Testing Anti-Patterns to Avoid

- ❌ **Only mocking external dependencies** without ever testing real integration
- ❌ **Assuming external APIs work** without verification during implementation
- ❌ **Testing only happy paths** - always include error cases
- ❌ **Brittle tests** that break with minor changes to implementation details

**To run tests** see the [Unified Command Reference](#unified-command-reference) for all testing commands with error recovery procedures.

## Style, Patterns & Documentation

### Coding Style

- **Use Pydantic** models in `src/backend/models/supplemental.py` for API response validation and data contracts. **Always use or update these models** when modifying API responses.
- Use the predefined error message functions for consistency. Update or create new if necessary.
- When writing complex logic, **add an inline `# Reason:` comment** explaining the *why*, not just the *what*.
- Comment non-obvious code to ensure it is understandable to a mid-level developer.

### Documentation

- Write **docstrings for every file, function, class, and method** using the Google style format. This is critical as the documentation site is built automatically from docstrings.

    ```python
    def example_function(param1: int) -> str:
        """A brief summary of the function.

        Args:
            param1 (int): A description of the first parameter.

        Returns:
            str: A description of the return value.
        """
        return "example"
    ```

- Provide an example usage in regards to the whole project. How would your code be integrated, what entrypoints to use
- Update this `AGENTS.md` file when introducing new patterns or concepts.
- Document significant architectural decisions in the project README or dedicated architecture docs.
- Document all significant changes, features, and bug fixes following conventional commit format.

### Code Pattern Examples

**FastAPI Endpoint Patterns:**

✅ **Proper endpoint structure:**
```python
@app.get("/tournaments", response_model=List[Tournaments])
async def list_tournaments(
    page_index: int = 0,
    count: int = 10,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    statement = select(Tournaments).offset(page_index * count).limit(count)
    return db.exec(statement).all()
```

❌ **Avoid missing dependencies:**
```python
@app.get("/tournaments")  # Missing response_model
async def list_tournaments():  # Missing auth and db dependencies
    # Direct database access without session management
```

**Database Operation Patterns:**

✅ **SQLModel with proper session management:**
```python
# Create
user = ensure_user_exists(db, user_id)
context = UserChallengeContexts(user_id=user.id, challenge_id=challenge_id)
db.add(context)
db.commit()
db.refresh(context)

# Query
statement = select(Model).where(Model.field == value)
results = db.exec(statement).all()
```

❌ **Avoid bypassing validation:**
```python
# Direct SQL or missing session management
db.execute("INSERT INTO...")  # No validation
```

**Authentication Patterns:**

✅ **Consistent user handling:**
```python
async def endpoint(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user = ensure_user_exists(db, current_user['id'])
    # Use internal user.id for database operations
```

**Quick Reference**: Always use dependency injection, proper error handling, and SQLModel validation.

## API Development Guidelines

### FastAPI Best Practices

- Always include `response_model` for type safety and auto-documentation
- Use dependency injection for authentication (`current_user`) and database sessions (`db`)
- Implement proper pagination with `page_index` and `count` parameters
- Handle errors with appropriate HTTP status codes (404, 400, 401, etc.)
- Use SQLModel for all database operations with proper session management

### Database Integration Patterns

- Always use `ensure_user_exists()` to handle Supabase user ID to internal user ID mapping
- Use `db.commit()` and `db.refresh()` for create/update operations
- Build queries with SQLModel's `select()` and `where()` for type safety
- Handle foreign key relationships properly using internal user IDs

## Agent Integration

### Letta Agent Patterns

- Use `get_letta_client()` with `@cache` decorator for performance
- Follow agent naming convention: `{user_id}_{tournament_id}_{challenge_id}`
- Store agent IDs in `UserChallengeContexts` for persistence
- Use `send_message_and_check_tools()` for agent interactions
- Handle tool calls and responses appropriately in the API layer

## Code Review & PR Guidelines

### Commit and PR Requirements

- **Title Format**: Commit messages and PR titles must follow the **Conventional Commits** specification, as outlined in the `.gitmessage` template.
- Provide detailed PR summaries including the purpose of the changes and the testing performed.

### Pre-commit Checklist

1. **Automated validation**: `make validate` - runs complete sequence (ruff + type_check + test_all)
2. **Quick validation** (development): `make quick_validate` - runs fast checks (ruff + type_check only)
3. Update documentation as described above.

**Manual fallback** (if make commands fail):

1. `uv run ruff format && uv run ruff check --fix`
2. `uv run pyright`
3. `uv run pytest`

## Logging and Documentation Standards

### Logging in FastAPI Applications

- Use structured logging with appropriate log levels (DEBUG, INFO, WARNING, ERROR)
- Include request IDs for tracing API requests
- Log authentication events and database operations
- Use ISO 8601 timestamps for log entries. Use `date -u "+%Y-%m-%dT%H-%M-%SZ"` for TIMESTAMP
- Log entry format: `[TIMESTAMP] Action description`

### Documentation Standards

- Use [markdownlint's Rules.md](https://github.com/DavidAnson/markdownlint/blob/main/doc/Rules.md) for consistent markdown formatting
- Follow conventional commit format for all commits
- Update API documentation when endpoints change
- Document environment variables and configuration requirements

## Unified Command Reference

| Command | Purpose | Prerequisites | Error Recovery |
|---------|---------|---------------|----------------|
| `make setup` | Install all dependencies and CLIs | Makefile exists, uv installed | Try `uv sync --all-groups` directly |
| `make claude_cli` | Setup Claude Code CLI | Node.js and npm installed | Manual: `npm install -g @anthropic-ai/claude-code` |
| `make gemini_cli` | Setup Gemini CLI | Node.js and npm installed | Manual: `npm install -g @google/gemini-cli` |
| `make run` | Run FastAPI backend server | Dev environment setup | Try `uv run python src/backend/server.py` |
| `make ruff` | Format code and fix linting | Ruff installed | Try `uv run ruff format && uv run ruff check --fix` |
| `make type_check` | Run pyright static type checking | Pyright installed | Try `uv run pyright` |
| `make test_all` | Run all tests with pytest | Pytest installed | Try `uv run pytest` |
| `make validate` | Complete pre-commit validation | Above dependencies | Run individual commands manually |
| `make quick_validate` | Fast development validation | Ruff and Pyright installed | Run `make ruff && make type_check` |
| `uv run pytest <path>` | Run specific test file/function | Pytest available | Check test file exists and syntax |

### Standard Workflow Commands

**Initial setup** (one-time):

1. `make setup` - Install dependencies, Claude CLI, and Gemini CLI
2. Set up environment variables in `.env` file (SUPABASE_URL, SUPABASE_SERVICE_KEY, LETTA_API_KEY)
3. `make run` - Start server to verify setup

**Development cycle**:

1. `make quick_validate` - Fast validation (ruff + type_check only) 
2. Make code changes
3. `make run` - Test changes locally
4. Repeat steps 1-3 as needed

**API development workflow**:

1. Add/modify endpoints in `src/backend/server.py`
2. Update database models in `src/backend/database/models.py` if needed
3. Add response models in `src/backend/models/supplemental.py` if needed
4. `make run` - Start server on localhost:8080
5. Test endpoints at `http://localhost:8080/docs` (OpenAPI docs)
6. `make quick_validate` - Check formatting and types

**Pre-commit checklist** (before pushing):

1. `make validate` - Complete validation sequence (ruff + type_check + test_all)
2. Update AGENTS.md if new patterns learned
3. Update documentation if API changes made
4. Commit with descriptive message following conventional commits format

**Agent integration workflow**:

1. Modify `src/backend/agents/letta.py` for agent functionality
2. Test agent interactions via `/challenges/{id}/submit_message` endpoint
3. Verify agent creation and message handling
4. `make validate` - Ensure all checks pass

## Requests to Humans

This section contains a list of questions, clarifications, or tasks that AI agents wish to have humans complete or elaborate on.

### Escalation Process

**When to Escalate:**

- Explicit user instructions conflict with safety/security practices
- Rules in AGENTS.md or otherwise provided context contradict each other
- Required information completely missing from all sources
- Actions would significantly change project architecture
- Critical dependencies or libraries are unavailable

**How to Escalate:**

1. **Add to list below** using checkbox format with clear description
2. **Set priority**: `[HIGH]`, `[MEDIUM]`, `[LOW]` based on blocking impact
3. **Provide context**: Include relevant file paths, error messages, or requirements
4. **Suggest alternatives**: What could be done instead, if anything

**Response Format:**

- Human responses should be added as indented bullet points under each item
- Use `# TODO` for non-urgent items with reminder frequency
- Mark completed items with `[x]` checkbox

### Active Requests

- [ ] **[MEDIUM]** Environment variable validation and documentation needed. The server.py has default values for Supabase credentials that should not be used in production.
  - **Files affected**: `src/backend/server.py:46-47`
  - **Issue**: Default values "YOUR_SUPABASE_URL" and "YOUR_SERVICE_KEY" could cause silent failures
  - **Suggested fix**: Add startup validation or remove defaults to force proper configuration
- [ ] **[LOW]** Challenge agent integration is stubbed out. The `/challenges/{challenge_id}/submit_message` endpoint returns None.
  - **Files affected**: `src/backend/server.py:323-338`
  - **Context**: Integration with Letta agents for challenge workflow
  - **Suggested approach**: Implement full agent message handling and response processing
- [ ] **[LOW]** User tournament enrollment uses external user ID instead of internal user ID, which may cause foreign key issues.
  - **Files affected**: `src/backend/server.py:349-350`
  - **Issue**: Uses `current_user['id']` (Supabase UUID) instead of internal user table ID
  - **Suggested fix**: Use `ensure_user_exists()` pattern like other endpoints
- [ ] **[LOW]** Add comprehensive test coverage for all API endpoints, especially authentication and database operations.
  - **Context**: Current codebase lacks visible test files
  - **Priority**: Important for production readiness but not blocking development
- [ ] **[LOW]** Consider adding API versioning strategy and OpenAPI documentation enhancements.
  - **Context**: FastAPI auto-generates docs but could be enhanced with better descriptions and examples

## Agent Learning Documentation

When agents discover new patterns, solutions, or important insights, document them here using this template:

### Template for New Learnings

When documenting a new pattern, use this format:

**Structure:**

- **Date**: [ISO timestamp - use `date -u "+%Y-%m-%dT%H:%M:%SZ"`]
- **Context**: [When/where this pattern applies]
- **Problem**: [What issue this solves]
- **Solution**: [Implementation approach]
- **Example**: [Code example with language specified]
- **Validation**: [How to verify this works]
- **References**: [Related files, documentation, or PRs]

**Example Entry:**

```markdown
### Learned Pattern: SQLModel Database Session Management

- **Date**: 2025-07-29T00:00:00Z
- **Context**: FastAPI endpoints with database operations
- **Problem**: Need consistent database session management across all endpoints
- **Solution**: Use dependency injection with `db: Session = Depends(get_db)` pattern
- **Example**: See `src/backend/database/connection.py` for session factory and `src/backend/server.py` for usage
- **Validation**: All database operations properly managed with automatic session cleanup
- **References**: Pattern used consistently across all database endpoints
```

### Active Learning Entries

Agents should add new patterns discovered during development here.

#### Learned Pattern: FastAPI Authentication Integration

- **Date**: 2025-07-29T00:00:00Z
- **Context**: Supabase JWT authentication with FastAPI dependency injection
- **Problem**: Need to handle JWT token verification with performance optimization and proper error handling
- **Solution**: Implement caching layer in SupabaseAuth class with TTL-based token validation to reduce API calls while maintaining security
- **Example**: See `src/backend/server.py:52-111` for SupabaseAuth implementation with cache
- **Validation**: Authentication works with 10-second cache TTL, reducing Supabase API calls during rapid requests
- **References**: Pattern used consistently across all authenticated endpoints

## Agent Quick Reference - Critical Reminders

**Before ANY task, verify:**

- File structure follows `src/backend/` organization
- Libraries exist in `pyproject.toml` dependencies
- No missing context assumptions

**Documentation tasks:**

- Apply [markdownlint rules](https://github.com/DavidAnson/markdownlint/blob/main/doc/Rules.md)
- Use ISO 8601 timestamps (`YYYY-mm-DDTHH:MM:SSZ`)
- Update AGENTS.md when learning new patterns

**Code tasks:**

- Max 500 lines/file - refactor if approaching limit
- Create tests mirroring `src/backend/` structure
- Write Google-style docstrings for all functions
- Verify imports exist in `pyproject.toml` before using
- Use SQLModel for all database operations
- Include `response_model` in all FastAPI endpoints

**Always finish with:**

- Follow [pre-commit checklist](#standard-workflow-commands)
- Update AGENTS.md if learned something new

**🛑 STOP if blocked:** Add to "Requests to Humans" rather than assume or proceed with incomplete info
