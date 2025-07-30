.SILENT:
.ONESHELL:
.PHONY: setup claude_cli gemini_cli run ruff type_check test_all test_llm test_llm_manual test_llm_verbose test_llm_examples validate quick_validate help
.DEFAULT_GOAL := setup


# MARK: setup


setup:  ## Setup main development env: uv all groups, Claude Code, Gemini 
	echo "Setting up dev environment ..."
	pip install uv -q
	uv sync --all-groups
	$(MAKE) -s claude_cli
	$(MAKE) -s gemini_cli

claude_cli:  ## Setup Claude Code CLI, node.js and npm have to be present
	echo "Setting up claude code ..."
	npm install -g @anthropic-ai/claude-code
	echo "npm version: $$(npm --version)"
	claude --version

gemini_cli:  ## Setup Gemini CLI, node.js and npm have to be present
	echo "Setting up Gemini CLI ..."
	npm install -g @google/gemini-cli
	echo "Gemini CLI version: $$(gemini --version)"


# MARK: run


run:  ## Runs the backend server
	uv run python src/backend/server.py


# MARK: sanity


ruff:  ## Lint: Format and check with ruff
	uv run ruff format
	uv run ruff check --fix

type_check:  ## Check for static typing errors
	uv run pyright

test_all:  ## Run all tests
	uv run pytest

test_llm:  ## Run LLM property-based tests with Hypothesis
	uv run pytest tests/test_llm.py -v

test_llm_manual:  ## Run LLM tests in manual mode (interactive)
	uv run python tests/test_llm.py

test_llm_verbose:  ## Run LLM tests with Hypothesis statistics
	uv run pytest tests/test_llm.py -v -s --tb=short

test_llm_examples:  ## Run LLM tests with more examples (thorough)
	uv run pytest tests/test_llm.py -v

validate:  ## Complete pre-commit validation sequence
	echo "Running complete validation sequence..."
	$(MAKE) -s ruff
	-$(MAKE) -s type_check
	-$(MAKE) -s test_all
	echo "Validation sequence completed (check output for any failures)"

quick_validate:  ## Fast development cycle validation
	echo "Running quick validation..."
	$(MAKE) -s ruff
	-$(MAKE) -s type_check
	echo "Quick validation completed (check output for any failures)"


# MARK: help


help:  ## Displays this message with available recipes
	# TODO add stackoverflow source
	echo "Usage: make [recipe]"
	echo "Recipes:"
	awk '/^[a-zA-Z0-9_-]+:.*?##/ {
		helpMessage = match($$0, /## (.*)/)
		if (helpMessage) {
			recipe = $$1
			sub(/:/, "", recipe)
			printf "  \033[36m%-20s\033[0m %s\n", recipe, substr($$0, RSTART + 3, RLENGTH)
		}
	}' $(MAKEFILE_LIST)
