.PHONY: install test run clean

install:
	pip install -r requirements.txt

test:
	ENV=test GEMINI_API_KEY=test-key pytest tests/ -v

run:
	GEMINI_API_KEY=$${GEMINI_API_KEY:-test-key} \
	uvicorn app.main:app --reload --port 8080

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache
