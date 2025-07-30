# TrustBuilder Wargames AI Backend

[![CodeFactor](https://www.codefactor.io/repository/github/trustbuilder-ai/wargames-ai-backend/badge)](https://www.codefactor.io/repository/github/trustbuilder-ai/wargames-ai-backend)

A FastAPI-based backend service for the TrustBuilder Wargames platform featuring tournament management, challenge systems, and integrated AI agents through Letta and LiteLLM.

## 🚀 Features

- **Tournament System**: Time-gated tournaments with user enrollment and progress tracking
- **Challenge Framework**: AI-powered challenges testing tool call capabilities
- **LLM Integration**: Direct integration with multiple AI providers (OpenAI, Anthropic, GitHub, Hugging Face)
- **Agent System**: Letta-based AI agents for interactive challenges
- **Authentication**: Supabase JWT-based authentication
- **Database**: PostgreSQL with SQLModel ORM
- **Testing**: Comprehensive test suite with property-based testing
- **Documentation**: Full OpenAPI 3.1.0 specification

## 🏗️ Architecture

```
Frontend → FastAPI Backend → PostgreSQL (Supabase)
                          ↓
                    LiteLLM → Multiple AI Providers
                          ↓
                    Letta Agents → Challenge Interactions
```

### Core Components

- **FastAPI Server**: RESTful API with automatic documentation
- **Database Layer**: SQLModel models with Supabase integration
- **LLM Module**: Direct LiteLLM integration with multiple providers
- **Agent Framework**: Letta client for AI challenge interactions
- **Authentication**: JWT token validation with Supabase

## 📋 Prerequisites

- **Python**: 3.12.x (exact version required)
- **Node.js**: For Claude CLI and Gemini CLI
- **uv**: Python package manager
- **PostgreSQL**: Via Supabase or local instance

## 🛠️ Development Setup

### Quick Start

```bash
# Complete setup (recommended)
make setup

# Manual setup
pip install uv
uv sync --all-groups
npm install -g @anthropic-ai/claude-code
npm install -g @google/gemini-cli
```

### Environment Configuration

Create `.env.litellm` file for LLM API keys:

```bash
# Copy example and edit
cp .env.litellm.example .env.litellm

# Add your API keys
OPENAI_API_KEY=sk-your-openai-key
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key
GITHUB_TOKEN=ghp_your-github-token
HUGGINGFACE_API_KEY=hf_your-hf-token
```

### Database Setup

Configure Supabase connection (or local PostgreSQL):

```bash
# Set in environment or .env file
SUPABASE_URL=your-supabase-project-url
SUPABASE_SERVICE_KEY=your-service-key
```

## 🚀 Running the Application

### Development Server

```bash
# Start backend server
make run
# Server available at http://localhost:8080

# Alternative
uv run python src/backend/server.py
```

### Interactive Documentation

With server running:
- **Swagger UI**: http://localhost:8080/docs
- **ReDoc**: http://localhost:8080/redoc

## 🧪 Testing

### Test Suite

```bash
# Run all tests
make test_all

# LLM-specific tests
make test_llm                    # Standard test run
make test_llm_verbose           # Verbose output with logging
make test_llm_manual            # Interactive manual testing

# API integration tests
scripts/test_api.sh
```

### Validation

```bash
# Quick validation (development)
make quick_validate

# Complete validation (pre-commit)
make validate
```

### Test Coverage

- **Property-based testing** with Hypothesis
- **Integration tests** with real API calls
- **Unit tests** for all core functionality
- **API endpoint testing** with authentication
- **Model availability validation**

## 🔧 Development Workflow

### Code Quality

```bash
# Format and lint
make ruff

# Type checking
make type_check

# Complete validation
make validate
```

### API Documentation

```bash
# Generate OpenAPI documentation
uv run python scripts/generate_openapi.py              # JSON (default)
uv run python scripts/generate_openapi.py --format yaml # YAML
```

## 📚 API Endpoints

### Core Tournament API

- `GET /tournaments` - List tournaments with filtering
- `GET /tournaments/{id}` - Get tournament details
- `POST /tournaments/{id}/join` - Join tournament
- `GET /challenges` - List challenges
- `POST /challenges/{id}/start` - Start challenge
- `POST /challenges/{id}/submit_message` - Submit to challenge agent
- `GET /badges` - List user badges

### LLM Integration

- `POST /llm/chat/completions` - Create chat completions
- `GET /llm/models` - List available models
- `GET /llm/health` - Check LLM service health

### Utility

- `GET /health_check` - Service health check
- `GET /users/me` - Current user info

## 🤖 LLM Integration

### Supported Providers

| Provider | Models | API Key |
|----------|--------|---------|
| **OpenAI** | `gpt-4o`, `gpt-4o-mini` | `OPENAI_API_KEY` |
| **Anthropic** | `claude-3-5-sonnet-20241022`, `claude-3-5-haiku-20241022` | `ANTHROPIC_API_KEY` |
| **GitHub** | `github/gpt-4o`, `github/llama-3.1-70b-instruct` | `GITHUB_TOKEN` |
| **Hugging Face** | `huggingface/meta-llama/Llama-2-7b-chat-hf` | `HUGGINGFACE_API_KEY` |

### Usage Example

```bash
curl -X POST http://localhost:8080/llm/chat/completions \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-3-5-sonnet-20241022",
    "messages": [{"role": "user", "content": "Hello!"}],
    "temperature": 0.7,
    "max_tokens": 1000
  }'
```

## 🗂️ Project Structure

```
src/backend/
├── server.py              # FastAPI application and routes
├── db_api.py              # Database utility functions
├── database/
│   ├── connection.py      # Database connection management
│   ├── models.py          # SQLModel database models
│   └── locking.py         # Database locking utilities
├── llm/
│   ├── client.py          # LLM API client (LiteLLM integration)
│   ├── config.py          # Model configuration management
│   └── settings.py        # API key management with pydantic-settings
├── models/
│   ├── llm.py             # LLM Pydantic models
│   └── supplemental.py    # API response models
├── agents/
│   └── letta.py           # Letta client integration
└── util/
    └── log.py             # Logging configuration with loguru

tests/
└── test_llm.py            # Comprehensive LLM test suite

scripts/
├── generate_openapi.py    # OpenAPI documentation generator
└── test_api.sh           # API integration tests

docs/
├── API.md                 # API documentation
└── LLM_INTEGRATION.md     # LLM integration guide
```

## 🔒 Security

- **JWT Authentication**: All protected endpoints require valid Supabase JWT
- **API Key Management**: Secure environment variable handling
- **Input Validation**: Pydantic models for request/response validation
- **Error Handling**: Comprehensive error handling without information leakage

## 🐳 Docker Support

```bash
# Build image
docker build -t wargames-ai-backend .

# Run container
docker run -p 8080:8080 --env-file .env.litellm wargames-ai-backend
```

## 📖 Documentation

- **[API Documentation](docs/API.md)** - Complete API reference
- **[LLM Integration Guide](docs/LLM_INTEGRATION.md)** - LLM setup and usage
- **[Agent Documentation](AGENTS.md)** - Development patterns and guidelines

## 🤝 Contributing

1. Follow the development workflow in `AGENTS.md`
2. Run `make validate` before committing
3. Use conventional commit format
4. Update documentation for new features
5. Add tests for new functionality

## 📝 License

[Add your license information here]

## 🆘 Troubleshooting

### Common Issues

**No models available:**
```bash
# Check API keys
echo $ANTHROPIC_API_KEY
curl http://localhost:8080/llm/health
```

**Import errors:**
```bash
uv sync --all-groups
uv run python -c "from backend.llm.client import LLMClient; print('OK')"
```

**Test failures:**
```bash
make test_llm_verbose  # Detailed test output
scripts/test_api.sh    # API integration tests
```

For more troubleshooting, see [LLM Integration Guide](docs/LLM_INTEGRATION.md#troubleshooting).

---

Built with ❤️ by the TrustBuilder team
