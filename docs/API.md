# Surface Core API

Default endpoint: `http://127.0.0.1:47890`

Set `SIMULATION_AI_TOKEN` to require `Authorization: Bearer <token>` on every
route. Non-loopback binding is refused unless `SIMULATION_AI_ALLOW_REMOTE=1`.

## Read routes

- `GET /health`
- `GET /v1/snapshot`
- `GET /v1/events?limit=50`
- `GET /v1/branches`
- `GET /v1/render/jobs`
- `GET /v1/credentials/openai` — redacted configuration and lock status
- `GET /v1/model-execution/status`
- `GET /v1/prompt-runs?limit=50`
- `GET /v1/prompt-runs/{run_id}`
- `GET /v1/prompt-workflow-runs?limit=25`

## Write and proposal routes

- `POST /v1/interact` — full observation → proposal → commit → memory → render flow
- `POST /v1/observe` — evidence-only observation
- `POST /v1/propose` — produce and persist a patch proposal
- `POST /v1/commit` — validate and commit a supplied proposal
- `POST /v1/branch/create`
- `POST /v1/branch/switch`
- `POST /v1/memory/query`
- `POST /v1/render/verify`
- `POST /v1/replay`

## OpenAI credential-control routes

- `POST /v1/credentials/openai/save` — body: `api_key`, `password`
- `POST /v1/credentials/openai/import-env` — imports server-side `OPENAI_API_KEY`; body: `password`
- `POST /v1/credentials/openai/unlock` — body: `password`
- `POST /v1/credentials/openai/lock`
- `POST /v1/credentials/openai/test`
- `POST /v1/credentials/openai/clear` — body: `password`

Credential responses never return the key. These operational routes bypass the
semantic event pipeline and do not create world history.

The full interaction route is convenient, but the split routes exist so local
and remote adapters can be tested independently without granting them commit
authority.

## Prompt pack

```text
GET  /v1/prompts
GET  /v1/prompts/{prompt_id}
GET  /v1/prompt-workflows
POST /v1/prompts/render
POST /v1/prompts/route
POST /v1/prompts/validate
POST /v1/prompts/validate-output
POST /v1/prompts/execute
POST /v1/prompt-runs/review
POST /v1/prompt-workflows/execute
```

`validate-output` checks a candidate model result against the role's JSON Schema and returns an evidence-safe validation artifact with no commit authority.

Prompt rendering returns a content-addressed `nmsr.prompt-invocation/1` with shared policy layers, the output schema, provider strict-compatibility metadata, and authority hashes. Rendering does not call a model. Execution calls OpenAI only when the committed privacy policy allows cloud use and a credential is available. Model and workflow traces never commit state; see `MODEL_EXECUTION.md`.
