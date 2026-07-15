# AI Receptionist Platform

Production-grade, multi-tenant AI Receptionist unifying WhatsApp, Website Live Chat, and
(future) AI Voice Calls behind one backend, one Customer 360, and one Knowledge Intelligence
Engine. See [docs/Goal.md](docs/Goal.md) for the product vision and [docs/roadmap.md](docs/roadmap.md)
for build phases.

Read [docs/CLAUDE.md](docs/CLAUDE.md) and [docs/rules.md](docs/rules.md) before making changes —
they are the binding engineering and security specifications for this repo.

## Repository layout

```
apps/
  api/          FastAPI backend (modular monolith)
  dashboard/    Next.js staff dashboard
  widget/       Embeddable web-chat widget (Phase 5)
  voice-agent/  LiveKit voice agent (Phase 9)
packages/
  shared-types/   TypeScript types shared by dashboard/widget
  shared-config/  Shared tsconfig/eslint base config
docs/           Living engineering specification (read before coding)
```

## Local development

### Backend (`apps/api`)

Requires Python 3.12 in Docker/CI; local dev may run on a newer interpreter (no 3.12-specific
syntax is used). Dependencies are managed with [uv](https://github.com/astral-sh/uv).

```bash
cd apps/api
uv sync
cp ../../.env.example ../../.env   # fill in real values
uv run alembic upgrade head        # requires DATABASE_URL
uv run uvicorn app.main:app --reload --port 8000
```

Run tests:

```bash
uv run pytest
```

Database-dependent tests automatically skip unless `DATABASE_URL` is set.

### Dashboard (`apps/dashboard`)

```bash
npm install
npm run dashboard:dev
```

## Documentation is not optional

Every change that touches the API, database schema, architecture, or security behavior must
update the corresponding file in `docs/` in the same change. See `docs/CLAUDE.md` for the full
rule.
