# LLM Integration with Direct LiteLLM

This document describes how to set up and use the LLM integration in the TrustBuilder Wargames AI Backend using direct LiteLLM library calls.

## Architecture Overview

The LLM integration uses direct LiteLLM library integration with proper separation of concerns:

```bash
Frontend → FastAPI Backend → LiteLLM Library → Multiple LLM Providers
```

### Components

1. **LiteLLM Library**: Direct Python library integration for unified LLM provider access
2. **Backend LLM Module**: Separated modules following SoC and SRP principles
   - `config.py`: Model configuration and environment management
   - `client.py`: LLM API client implementation  
   - `models.py`: Pydantic data models and type definitions
3. **FastAPI Endpoints**: RESTful API endpoints for frontend integration
4. **Frontend Config**: TypeScript configuration for available models

### Separation of Concerns

- **Configuration Management** (`config.py`): Model definitions, API key validation, environment setup
- **Client Logic** (`client.py`): LLM API calls, error handling, response conversion
- **Data Models** (`models.py`): Type definitions, validation, serialization
- **API Layer** (`server.py`): HTTP endpoints, authentication, request routing

## Quick Start

### 1. Install Dependencies

The required dependencies are included in `pyproject.toml`:

```bash
# Install/update dependencies  
uv sync --all-groups

# Verify installation
make setup  # Installs uv, dependencies, Claude CLI, and Gemini CLI
```

### 2. Set Up API Keys

The backend uses **pydantic-settings** to automatically load API keys from `.env.litellm` files:

```bash
# Copy the example file
cp .env.litellm.example .env.litellm

# Edit .env.litellm with your actual API keys
nano .env.litellm
```

**Example .env.litellm file:**
```bash
# OpenAI API Key (for GPT models)
OPENAI_API_KEY=sk-your-actual-openai-key

# Anthropic API Key (for Claude models)  
ANTHROPIC_API_KEY=sk-ant-your-actual-anthropic-key

# Hugging Face API Token (for HF models)
HUGGINGFACE_API_KEY=hf_your-actual-token

# GitHub Token (for GitHub Models)
GITHUB_TOKEN=ghp_your-actual-token
```

**Alternative**: Environment variables still work:
```bash
export OPENAI_API_KEY="sk-your-key"
export ANTHROPIC_API_KEY="sk-ant-your-key"
```

### 3. Start Backend Server

```bash
make run
# Backend API available at http://localhost:8080
```

### 4. Test the Integration

```bash
# Run automated API tests
scripts/test_api.sh

# Or test manually:
# Check LLM service health
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     http://localhost:8080/llm/health

# List available models
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     http://localhost:8080/llm/models

# Send a chat message using Claude
curl -X POST \
     -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "model": "claude-3-5-sonnet-20241022",
       "messages": [{"role": "user", "content": "Hello!"}]
     }' \
     http://localhost:8080/llm/chat/completions
```

## Configuration

### Available Models

Models are configured in `llm_config.yaml` and loaded automatically:

| Provider | Models | API Key Required |
|----------|--------|------------------|
| **OpenAI** | `gpt-4o`, `gpt-4o-mini` | `OPENAI_API_KEY` |
| **Anthropic** | `claude-3-5-sonnet-20241022`, `claude-3-5-haiku-20241022` | `ANTHROPIC_API_KEY` |
| **Hugging Face** | `huggingface/meta-llama/Llama-2-7b-chat-hf`, `huggingface/microsoft/DialoGPT-large` | `HUGGINGFACE_API_KEY` |
| **GitHub** | `github/gpt-4o`, `github/llama-3.1-70b-instruct` | `GITHUB_TOKEN` |

**Only models with valid API keys will appear in the `/llm/models` endpoint.**

### Model Configuration

Models are configured in `llm_config.yaml`. To add new models:

```yaml
your-model-id:
  provider: provider-name
  display_name: "Human Readable Name"
  description: "Model description"
  requires_key: "YOUR_API_KEY_ENV_VAR"
  max_tokens: 4096
```

### API Key Management

**Automatic Loading**: The backend uses **pydantic-settings** to load API keys from:

1. **`.env.litellm` file** (recommended for development)
2. **`.env.litellm.local` file** (for local overrides)  
3. **Environment variables** (for production)

**Priority**: Environment variables override .env.litellm files.

**Required API Keys**:

- **OpenAI**: `OPENAI_API_KEY` (from https://platform.openai.com/api-keys)
- **Anthropic**: `ANTHROPIC_API_KEY` (from https://console.anthropic.com/account/keys)
- **Hugging Face**: `HUGGINGFACE_API_KEY` (from https://huggingface.co/settings/tokens)
- **GitHub**: `GITHUB_TOKEN` (from https://github.com/settings/tokens)

## API Endpoints

### POST /llm/chat/completions

Create a chat completion using any configured model.

**Request Body:**
```json
{
  "model": "gpt-4o-mini",
  "messages": [
    {"role": "user", "content": "Hello, how are you?"}
  ],
  "temperature": 0.7,
  "max_tokens": 4096,
  "user": "optional-user-id"
}
```

**Response:**
```json
{
  "id": "chatcmpl-123",
  "object": "chat.completion",
  "created": 1677652288,
  "model": "gpt-4o-mini",
  "choices": [{
    "index": 0,
    "message": {
      "role": "assistant",
      "content": "Hello! I'm doing well, thank you for asking."
    },
    "finish_reason": "stop"
  }],
  "usage": {
    "prompt_tokens": 9,
    "completion_tokens": 12,
    "total_tokens": 21
  }
}
```

### GET /llm/models

List all available models (those with API keys configured).

**Response:**
```json
{
  "object": "list",
  "data": [
    {
      "id": "gpt-4o-mini",
      "object": "model",
      "created": 0,
      "owned_by": "openai",
      "display_name": "GPT-4o Mini",
      "description": "Faster and more cost-effective version of GPT-4o",
      "max_tokens": 4096,
      "cost_per_1k_tokens": 0.005
    }
  ]
}
```

### GET /llm/health

Check the health status of the LLM service.

**Response:**
```json
{
  "status": "healthy",
  "available_models": 2,
  "missing_keys": [],
  "message": "All models available (2 models)",
  "details": {
    "providers": {
      "openai": true,
      "anthropic": true
    },
    "total_models": 4
  }
}
```

Status values:
- `healthy`: All models available
- `degraded`: Some models available, some missing API keys
- `unhealthy`: No models available

## Error Handling

The system includes comprehensive error handling:

### Client Errors

- **LLMClientError**: Base exception for client errors
- **LLMValidationError**: Request/response validation failures
- **LLMAPIError**: API errors from LLM providers

### HTTP Status Codes

- `200`: Success
- `400`: Bad request (validation error)
- `401`: Unauthorized (authentication required)
- `500`: Internal server error (API unavailable, missing keys, etc.)

### Example Error Response

```json
{
  "detail": "Chat completion failed: API key 'OPENAI_API_KEY' not set for model 'gpt-4o'"
}
```

## Module Structure

### `src/backend/llm/config.py`

**Single Responsibility**: Model configuration and environment management

- `ModelConfig`: Data class for individual model configuration
- `LLMConfig`: Configuration manager with validation methods
- Environment variable validation
- Model availability checking

### `src/backend/llm/client.py`

**Single Responsibility**: LLM API calls and response handling

- `LLMClient`: Main client class for LiteLLM integration
- Direct LiteLLM library calls
- Response format conversion
- Error handling and logging

### `src/backend/models/llm.py`

**Single Responsibility**: Data models and type definitions

- Pydantic models for request/response validation
- OpenAI-compatible API format
- Type safety and serialization
- No business logic - pure data structures

### `src/backend/llm/settings.py`

**Single Responsibility**: API key management using pydantic-settings

- `APIKeySettings`: Secure environment variable loading
- Provider availability checking
- API key validation and retrieval
- Support for .env.litellm files

## Development Workflow

### 1. Environment Setup

```bash
# Set API keys
export OPENAI_API_KEY="your-key"
export ANTHROPIC_API_KEY="your-key"

# Install dependencies
uv sync --all-groups
```

### 2. Development Cycle

```bash
# Start backend
make run

# Test endpoints at http://localhost:8080/docs
# Check health: GET /llm/health
# List models: GET /llm/models  
# Test completion: POST /llm/chat/completions
```

### 3. Testing & Validation

```bash
# Run comprehensive LLM tests
make test_llm                    # Standard test run
make test_llm_verbose           # Verbose output with detailed logging
make test_llm_manual            # Interactive manual testing
make test_llm_examples          # Extended examples testing

# Run automated API tests  
scripts/test_api.sh             # Test all LLM endpoints

# Run linting and type checking
make quick_validate             # Fast validation (ruff + type_check)
make validate                   # Complete validation with tests
```

### 4. Test Coverage

The test suite includes comprehensive coverage:

**Property-Based Testing** (using Hypothesis):
- Valid request generation and validation
- Model name handling for provider versioning (e.g., `github/gpt-4o` → `github/gpt-4o-2024-11-20`)
- Response structure consistency testing
- Error handling for invalid requests

**Integration Testing**:
- Real API calls to Claude, GitHub, and other providers
- API key validation and error handling
- Model availability checking
- Health status reporting

**Unit Testing**:
- Client initialization and configuration
- Response format conversion
- Error exception handling
- Model listing and filtering

## Frontend Integration

### Configuration

The frontend config is already updated in `auth-demo/src/config.ts`:

```typescript
export const LLM_CONFIG = {
  models: {
    'gpt-4o': {
      name: 'GPT-4o',
      provider: 'OpenAI',
      description: 'Most capable OpenAI model'
    },
    // ... other models
  },
  defaultModel: 'gpt-4o-mini',
  defaults: {
    temperature: 0.7,
    max_tokens: 4096
  }
}
```

### Usage Example

```typescript
// Example usage (implement later)
const response = await apiClient.post('/llm/chat/completions', {
  model: 'gpt-4o-mini',
  messages: [{ role: 'user', content: 'Hello!' }]
});
```

## OpenAPI Documentation

The LLM integration is fully documented using OpenAPI 3.1.0 specification:

```bash
# Generate OpenAPI documentation
uv run python scripts/generate_openapi.py            # JSON format (default)
uv run python scripts/generate_openapi.py --format yaml  # YAML format

# Access interactive documentation (server running)
# http://localhost:8080/docs    - Swagger UI
# http://localhost:8080/redoc   - ReDoc interface
```

**Generated files**:
- `openapi.json` - Complete API specification in JSON
- `openapi.yaml` - Complete API specification in YAML

**Includes full documentation for**:
- All LLM endpoints (`/llm/chat/completions`, `/llm/models`, `/llm/health`)
- Request/response schemas (ChatRequest, ChatResponse, ModelInfo, etc.)
- Authentication requirements and error responses
- Model parameters and validation rules

## Security Considerations

1. **API Key Management**: Use secure environment variable management
2. **Authentication**: All endpoints require valid JWT tokens
3. **User Tracking**: Requests are logged with user IDs
4. **Rate Limiting**: Consider implementing rate limits per user
5. **Cost Monitoring**: Track usage per user/model for billing

## Troubleshooting

### Common Issues

**No models available:**
```bash
# Check API keys are set correctly
echo $OPENAI_API_KEY
echo $ANTHROPIC_API_KEY

# Verify .env.litellm file exists and has correct keys
cat .env.litellm

# Check health endpoint
curl -H "Authorization: Bearer TOKEN" http://localhost:8080/llm/health
```

**Test failures:**
```bash
# Common test issues and solutions:

# 1. Model name versioning (e.g., github/gpt-4o vs github/gpt-4o-2024-11-20)
# Tests now handle provider versioning automatically

# 2. Import errors in client.py
# Fixed: Import order corrected for proper API key loading

# 3. Invalid hypothesis flags
# Fixed: Removed --hypothesis-max-examples flag from Makefile
```

**Import errors:**
```bash
# Ensure dependencies are installed
uv sync --all-groups

# Check module structure
ls -la src/backend/llm/
ls -la src/backend/models/

# Verify imports work
uv run python -c "from backend.llm.client import LLMClient; print('OK')"
```

**LiteLLM errors:**
```bash
# Enable debug logging
export LITELLM_LOG=DEBUG

# Check server logs
tail -f logs/*.log

# Test with verbose output
make test_llm_verbose
```

**API Key Integration Issues:**
```bash
# If API keys aren't being passed to LiteLLM:

# 1. Check pydantic-settings is loading keys correctly
uv run python -c "
from backend.llm.settings import api_keys
print(f'Available providers: {api_keys.get_available_providers()}')
"

# 2. Verify server is running and accessible
curl http://localhost:8080/health_check

# 3. Test with working models (Claude has valid key)
scripts/test_api.sh
```

### Debug Mode

Enable verbose logging for troubleshooting:

```python
import logging
logging.getLogger("litellm").setLevel(logging.DEBUG)
```

## Next Steps

- Add streaming support for real-time responses
- Implement conversation persistence in database
- Add model usage analytics and cost tracking
- Create React hooks for frontend integration
- Add model switching and parameter tuning UI