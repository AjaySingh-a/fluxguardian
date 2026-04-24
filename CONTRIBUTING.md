# Contributing to FluxGuardian

Thanks for your interest! FluxGuardian is built for the OpenMetadata community.

## Quick Start for Contributors

1. Fork the repo
2. Clone your fork: `git clone https://github.com/YOUR-HANDLE/fluxguardian.git`
3. Follow [SETUP.md](./SETUP.md) to get a local environment running
4. Create a feature branch: `git checkout -b feature/my-feature`
5. Make changes and add tests
6. Run tests: `cd backend && pytest`
7. Submit a pull request

## Areas We'd Love Help With

- **More SQL dialect support** (BigQuery, Snowflake-specific syntax)
- **More connector types** (dbt, Fivetran, Airbyte integration)
- **Better LLM prompts** for edge cases and rare change types
- **More OM feature coverage** (data quality tests, alerts, glossary)
- **Frontend UX improvements** (charts, trends, alert history)
- **Persistent PR analysis store** (database-backed feed instead of demo data)

## Code Quality

- **Python:** PEP 8, type hints throughout, pytest for all new logic
- **TypeScript:** ESLint + Prettier, strict mode
- **Commit messages:** Conventional commits (`feat:`, `fix:`, `docs:`, `refactor:`, etc.)

## Running Tests

```bash
# Backend
cd backend
pip install -e ".[dev]"
pytest

# Frontend
cd frontend
npm install
npm run build   # type-check + build
```

## Reporting Issues

Use GitHub Issues with:
- **Title:** Clear one-liner describing the bug or feature
- **Description:** What you expected vs what happened
- **Reproduction:** Step-by-step instructions
- **Environment:** OS, Python version, OpenMetadata version

---

**Built with ❤️ for OpenMetadata OUTATIME 2026**
