# Zororo Local Form - Claude Code Rules

## Stack
- FastAPI / Python
- Railway deployment
- PDF generation (branded policy booklets)
- PostgreSQL on Railway

## Commands
- Install: pip install -r requirements.txt
- Dev server: uvicorn main:app --reload
- Tests: pytest
- Lint: flake8 . or ruff check .

## Rules - never break these
- Never commit .env files - this project had a token incident, be extra vigilant
- Always write files using [System.IO.File]::WriteAllText with UTF8 encoding - never open() in write mode without explicit UTF-8, BOM issues have occurred here before
- Never hardcode API keys, tokens, or credentials anywhere in code
- Railway start commands must be shell-wrapped - do not put raw Python commands as start command
- Always run pytest before considering any task done
- Always run flake8 before considering any task done
- Never expose PII in logs
- Additive changes only - never remove existing endpoints

## Easipol API Notes
- Uses token-based auth - headers: access-token, expiry, uid
- DocumentTypesV2 returns document categories not PDFs
- All Easipol calls must use TLS (sslmode=require)

## Handoff Rule
Never consider a task complete until:
1. pytest passes - all green
2. flake8 passes - zero errors
3. No .env files staged - run: git diff --cached --name-only
4. No hardcoded tokens or keys in changed files
5. Written a 3-line summary of what changed
Only then say: Ready for your review Mike

## When you fail
- Document what failed and what fixed it below
- Do not stop until tests and lint both pass

## Lessons learned
- BOM issue fix: always use [System.IO.File]::WriteAllText() not plain open() for file writes
- Railway port fix: shell-wrap start commands, expand port binding
- Git security: .env was committed once - always check .gitignore before first commit