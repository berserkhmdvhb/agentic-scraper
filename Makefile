.PHONY: all help install develop \
        fmt fmt-check lint-ruff type-check lint-all lint-all-check \
        test test-file test-file-function test-fast testing \
        test-coverage test-coverage-xml test-cov-html test-coverage-rep test-coverage-file clean-coverage \
        check-all test-watch \
        env-check env-debug env-clear env-show dotenv-debug env-example \
        check-updates check-toml \
        clean clean-logs clean-cache clean-coverage clean-build clean-pyc clean-all \
        build publish publish-test upload-coverage

PYTHON := python

all: help

help::
	@echo "Available Makefile commands:"
	@echo ""
	@echo "  install                Install the package in editable mode"
	@echo "  develop                Install with all dev dependencies"
	@echo "  fmt                    Auto-format code using Ruff"
	@echo "  fmt-check              Check code formatting (dry run)"
	@echo "  lint-ruff              Run Ruff linter"
	@echo "  type-check             Run MyPy static type checker"
	@echo "  lint-all               Run formatter, linter, and type checker"
	@echo "  lint-all-check         Dry run: check formatting, lint, and types"
	@echo "  test                   Run all tests using Pytest"
	@echo "  test-file              Run a single test file or keyword with FILE=..."
	@echo "  test-file-function     Run a specific test function with FILE=... FUNC=..."
	@echo "  test-fast              Run only last failed tests"
	@echo "  test-coverage          Run tests and show terminal coverage summary"
	@echo "  test-coverage-xml      Run tests and generate XML coverage report"
	@echo "  test-cov-html          Run tests with HTML coverage report and open it"
	@echo "  test-coverage-rep      Show full line-by-line coverage report"
	@echo "  test-coverage-file     Show coverage for a specific file: FILE=..."
	@echo "  test-watch             Auto-rerun tests on file changes"
	@echo "  check-all              Run format-check, lint, and full test suite"
	@echo "  env-check              Show Python and environment info"
	@echo "  env-debug              Show debug-related env info"
	@echo "  env-clear              Unset AGENTICSCRAPER_* and DOTENV_PATH variables"
	@echo "  env-show               Show currently set AGENTICSCRAPER_* and DOTENV_PATH"
	@echo "  env-example            Show example env variable usage"
	@echo "  dotenv-debug           Show debug info from dotenv loader"
	@echo "  check-updates          List outdated pip packages"
	@echo "  check-toml             Check pyproject.toml for syntax validity"
	@echo "  clean-logs             Remove logs (logs/DEV/*.log only)"
	@echo "  clean-cache            Remove cache files"
	@echo "  clean-coverage         Remove coverage data"
	@echo "  clean-build            Remove build artifacts"
	@echo "  clean-pyc              Remove .pyc and __pycache__ files"
	@echo "  clean-all              Remove all build, test, cache, and log artifacts"
	@echo "  build                  Build package for distribution"
	@echo "  publish-test           Upload to TestPyPI"
	@echo "  publish                Upload to PyPI"
	@echo "  upload-coverage        Upload coverage report to Coveralls"

install:
	$(PYTHON) -m pip install -e .

develop:
	$(PYTHON) -m pip install -e .[dev]

fmt:
	ruff format src/ tests/

fmt-check:
	ruff format --check src/ tests/

lint-ruff:
	ruff check src/ tests/

type-check:
	mypy src/ tests/

lint-all: fmt lint-ruff type-check

lint-all-check: fmt-check lint-ruff type-check

test:
	$(PYTHON) -m pytest tests/ -v

test-file:
	@$(PYTHON) -c "import sys; f = '$(FILE)'; sys.exit(0) if f else (print('Usage: make test-file FILE=path/to/file.py'), sys.exit(1))"
	$(PYTHON) -m pytest $(FILE) -v

test-file-function:
	@$(PYTHON) -c "import sys; f = '$(FILE)'; func = '$(FUNC)'; sys.exit(0) if f and func else (print('Usage: make test-file-function FILE=path/to/file.py FUNC=function_name'), sys.exit(1))"
	$(PYTHON) -m pytest $(FILE)::$(FUNC) -v

test-fast:
	$(PYTHON) -m pytest --lf -x -v

test-coverage:
	$(PYTHON) -m pytest --cov=agentic_scraper --cov-report=term --cov-fail-under=95

test-coverage-xml:
	$(PYTHON) -m pytest --cov=agentic_scraper --cov-report=term --cov-report=xml

test-cov-html:
	$(PYTHON) -m pytest --cov=agentic_scraper --cov-report=html
	$(PYTHON) -c "import webbrowser; webbrowser.open('htmlcov/index.html')"

test-coverage-rep:
	coverage report -m

test-coverage-file:
	@$(PYTHON) -c "import sys; f = '$(FILE)'; sys.exit(0) if f else (print('Usage: make test-coverage-file FILE=path/to/file.py'), sys.exit(1))"
	coverage report -m $(FILE)

check-all: lint-all-check test-coverage

test-watch:
	ptw --runner "$(PYTHON) -m pytest -v" tests/

env-check:
	@echo "Python: $$(python --version)"
	@$(PYTHON) -c "import sys; print('Virtualenv:', sys.executable)"
	@echo "Environment: $${AGENTICSCRAPER_ENV:-not set}"

env-debug:
	@echo "Debug: $${AGENTICSCRAPER_DEBUG_ENV_LOAD:-not set}"

env-clear:
	@echo "Clearing selected AGENTICSCRAPER-related and DOTENV_PATH environment variables..."
	@$(PYTHON) -c "import os; vars = ['ENV','DEBUG','OPENAI_API_KEY','OPENAI_PROJECT_ID','LLM_MAX_TOKENS','LLM_TEMPERATURE','MAX_CONCURRENT_REQUESTS','SCREENSHOT_ENABLED','SCREENSHOT_DIR','LOG_LEVEL','LOG_DIR','LOG_MAX_BYTES','LOG_BACKUP_COUNT','LOG_FORMAT','DOTENV_PATH']; [print(f'  Unsetting {v}') or os.environ.pop(v, None) for v in vars if v in os.environ]"

env-show:
	@echo "Currently set AGENTICSCRAPER_* and DOTENV_PATH environment variables:"
	@$(PYTHON) -c "import os; [print(f'  {k}={v}') for k, v in os.environ.items() if k.startswith('AGENTICSCRAPER_') or k == 'DOTENV_PATH']"

env-example:
	@echo "Example usage:"
	@echo "  export AGENTICSCRAPER_ENV=dev"
	@echo "  export AGENTICSCRAPER_DEBUG_ENV_LOAD=1"

dotenv-debug:
	@echo "==> Debugging dotenv loading via print_dotenv_debug()"
	$(PYTHON) -c "import logging; logging.basicConfig(level=logging.INFO); from agentic_scraper.core.settings import print_dotenv_debug; print_dotenv_debug()"

check-updates:
	$(PYTHON) -m pip list --outdated

check-toml:
	@$(PYTHON) -c "import tomllib; tomllib.load(open('pyproject.toml', 'rb')); print('pyproject.toml syntax is valid')"

clean-logs:
	@echo "Removing DEV log files..."
	$(PYTHON) -c "import pathlib; [p.unlink() for p in pathlib.Path('logs/DEV').rglob('*.log')]"

clean-cache:
	@echo "Removing cache files..."
	$(PYTHON) -c "import pathlib, shutil; [shutil.rmtree(p, ignore_errors=True) for p in map(pathlib.Path, ['.pytest_cache', '.mypy_cache', '.ruff_cache', 'htmlcov']) if p.exists()]"

clean-coverage:
	@echo "Removing coverage data..."
	$(PYTHON) -c "import pathlib; [p.unlink() for p in map(pathlib.Path, ['.coverage', 'coverage.xml']) if p.exists()]"
	coverage erase

clean-build:
	@echo "Removing build artifacts..."
	$(PYTHON) -c "import shutil, pathlib; [shutil.rmtree(p, ignore_errors=True) for p in map(pathlib.Path, ['dist', 'build']) if p.exists()]; [shutil.rmtree(p, ignore_errors=True) for p in pathlib.Path('.').rglob('*.egg-info')]"

clean-pyc:
	@echo "Removing .pyc and __pycache__ files..."
	$(PYTHON) -c "import pathlib, shutil; [p.unlink() for p in pathlib.Path('.').rglob('*.pyc')]; [shutil.rmtree(p, ignore_errors=True) for p in pathlib.Path('.').rglob('__pycache__')]"

clean-all: clean-logs clean-cache clean-coverage clean-build clean-pyc
	@echo ""
	@echo "All build, test, log, and cache artifacts have been removed."

build:
	$(PYTHON) -m build

publish-test:
	twine check dist/*
	twine upload --repository testpypi --skip-existing --non-interactive dist/*

publish:
	twine check dist/*
	twine upload dist/*

upload-coverage:
	coveralls
