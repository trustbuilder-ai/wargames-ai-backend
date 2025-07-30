#!/bin/bash
# Test script for LLM API endpoints using cURL
# Make sure the server is running: make run

API_BASE="http://localhost:8080"
AUTH_TOKEN="dev-token"  # Development token (if auth is disabled)

echo "🔍 Testing LLM API Endpoints"
echo "=================================="

# Test 1: Health Check
echo "1. Testing LLM Health Check..."
curl -s -H "Authorization: Bearer $AUTH_TOKEN" \
     "$API_BASE/llm/health" | jq '.' || echo "Failed or no jq installed"
echo -e "\n"

# Test 2: List Models  
echo "2. Testing Model Listing..."
curl -s -H "Authorization: Bearer $AUTH_TOKEN" \
     "$API_BASE/llm/models" | jq '.' || echo "Failed or no jq installed"
echo -e "\n"

# Test 3: Chat Completion
echo "3. Testing Chat Completion..."
curl -s -X POST \
     -H "Authorization: Bearer $AUTH_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "model": "gpt-4o-mini",
       "messages": [
         {"role": "user", "content": "Hello! Tell me a short joke."}
       ],
       "temperature": 0.7,
       "max_tokens": 100
     }' \
     "$API_BASE/llm/chat/completions" | jq '.' || echo "Failed or no jq installed"
echo -e "\n"

# Test 4: Chat Completion with Different Model
echo "4. Testing with Claude model..."
curl -s -X POST \
     -H "Authorization: Bearer $AUTH_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "model": "claude-3-5-haiku-20241022",
       "messages": [
         {"role": "user", "content": "What is the capital of France?"}
       ],
       "temperature": 0.3
     }' \
     "$API_BASE/llm/chat/completions" | jq '.' || echo "Failed or no jq installed"

echo -e "\nDone! Check server logs for detailed information."