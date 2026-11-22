# AI Model Arena — Backend

The backend of **ModelJudge**, a tool for comparing AI language models. A user sends one prompt to two models, reads both answers side by side with their latency, token usage and estimated cost, and gets an evaluation from a separate **judge model**. Signed-in users keep their comparisons and can open, rerun or delete them later.

It is a Django REST API backed by PostgreSQL, deployed on Render. The React frontend lives in the `frontend` repository and only talks to this API.

## 1. What It Does

- Sends the same prompt to two chosen models **concurrently** and keeps each answer, its latency, its token counts and its estimated cost.
- Asks a judge model to score the successful answers on accuracy, relevance, clarity and completeness, pick a winner and explain why. Model names are hidden from the judge to reduce bias.
- If one model fails, the other answer is kept and the failure is reported separately; the judge only runs when at least two answers succeeded.
- Accounts with email and password (JWT). Anonymous users can compare but cannot read their comparisons back; signed-in users get a history, can rerun an experiment as a new run, and can delete it.
- Retries temporary provider failures and reports failures with a specific, user-facing error code.
- Documents every endpoint in Swagger at `/api/docs/`.

## 2. Technology Stack

| Technology | Purpose |
|---|---|
| Python 3.12 | Language |
| Django 5.2 + Django REST Framework | Web framework, ORM, admin, API layer and validation |
| drf-spectacular | OpenAPI schema, Swagger (`/api/docs/`) and ReDoc (`/api/redoc/`) |
| djangorestframework-simplejwt | JWT sign-in (access 30 min, refresh 7 days) |
| django-environ | Settings from environment variables (`.env`) |
| django-cors-headers | CORS for the frontend |
| PostgreSQL (psycopg 3) | Database |
| google-genai, groq | SDKs for the Gemini and Groq providers |
| httpx | HTTP client for the OpenAI-compatible providers (OpenRouter, NVIDIA, OVHcloud, Together) |
| gunicorn | Production server on Render |
| pytest + pytest-django, ruff | Tests and linting |

## 3. AI Providers and Models

Every provider implements the same interface (`providers/base.py`). Which one a model uses is stored on the model itself (`AIModel.provider`) and picked by `providers/factory.py`.

| Provider | Class | Key setting | Notes |
|---|---|---|---|
| `gemini` | `GeminiProvider` (google-genai) | `GEMINI_API_KEY` | Preview models often answer "high demand" (503). |
| `groq` | `GroqProvider` (groq SDK) | `GROQ_API_KEY` | Also runs the judge, so compared Groq models share its quota. |
| `openrouter` | `OpenRouterProvider` | `OPENROUTER_API_KEY` | Free `:free` models. Free limits are account wide (20 requests/min, 50/day). |
| `nvidia` | `NvidiaProvider` | `NVIDIA_API_KEY` | Free NIM endpoints; NVIDIA retires models without notice, so re-test them. |
| `together` | `TogetherProvider` | `TOGETHER_API_KEY` | Pay per token (no free tier, no rate limit at normal use). Prices are stored, so costs are real. Only models on Together's serverless API work; streaming-only models fail because the client does not stream. |
| `ovhcloud` | `OvhCloudProvider` | `OVH_AI_ENDPOINTS_API_KEY` (optional) | Works without a key: 2 requests/min per IP and per model, shared by everyone using the deployed backend. |

OpenRouter, NVIDIA, OVHcloud and Together share `providers/openai_compatible.py` (the OpenAI chat completions protocol over HTTP); a provider there only sets its name, endpoint and key setting.

**Resilience (in `providers/base.py`).** Overloaded (5xx) and rate-limited (429) answers are retried up to `AI_MAX_RETRIES` times (default 2) with growing delays; timeouts, authentication and model errors are not retried. Every request has a timeout (`AI_REQUEST_TIMEOUT_SECONDS`, default 60).

**Models seeded by `seed_models`** (only missing ones are created; admin edits are never overwritten):

| Models | Provider | Price |
|---|---|---|
| Gemini 3.8 Flash, 3.6 Flash, 3.5 Flash-Lite, 3.1 Flash-Lite | gemini | not seeded, set in the admin |
| Nemotron 3 Ultra (free), ERNIE 5.5 Flash (free) | openrouter | 0 |
| Qwen 3.8 27B, GPT-OSS 20B, ALLaM 2 7B (Arabic focused, 4,096-token context) | groq | 0 |
| DeepSeek V4.1 Flash | ovhcloud | 0 |
| `openai/gpt-oss-120b` (the judge, configurable with `JUDGE_MODEL`) | groq | not offered for comparison |

Free models disappear or become unreliable without notice. The seed switches off retired ones (`RETIRED_MODELS` in `seed_models.py`: North Mini Code, Ling 3.2 Flash, Gemma 4 31B) instead of deleting them, because past experiments refer to them.

Free models cost nothing, so their price is stored as `0` and the cost shows `$0`. For models with no price, cost is reported as unavailable (`null`), never as zero.

## 4. Project Structure

```text
backend/
├── config/                     # Django project configuration
│   ├── settings/               # base.py, development.py, production.py
│   ├── urls.py                 # Root URLs (/api/, /admin/, API docs)
│   ├── health.py               # GET /api/health/
│   ├── asgi.py
│   └── wsgi.py
├── apps/
│   ├── accounts/               # Custom user (email + password), JWT auth, profile
│   ├── ai_models/              # Model catalog, pricing, cost calculation, seed_models
│   ├── comparisons/            # Workflow, experiments, runs, answers, history endpoints
│   │   └── services/           # comparison_service, metrics_service, persistence, history
│   └── evaluations/            # Judge: rubric, scores, verdict, seed_criteria
│       └── services/           # judge_service, persistence
├── providers/                  # One module per AI provider (+ shared base, retries, errors)
│   ├── base.py                 # Interface and retry logic
│   ├── openai_compatible.py    # Shared code for OpenRouter, NVIDIA, OVHcloud, Together
│   ├── gemini.py, groq.py, openrouter.py, nvidia.py, ovhcloud.py, together.py
│   ├── exceptions.py           # Provider errors and the user-facing error codes
│   └── factory.py              # Chooses the provider for a model
├── tests/                      # Tests grouped by feature: tests/<feature>/test_*.py
├── scripts/                    # Manual checks against the real provider APIs (not tests)
├── docs/                       # database.md, erd.html, django-for-express-devs.md
├── render.yaml                 # Render deployment blueprint
├── manage.py, pytest.ini, requirements.txt, requirements-dev.txt, .env.example
```

### Directory Responsibilities

- **`config/`** — Settings split into `base`, `development` and `production`; root URLs; the health endpoint.
- **`apps/accounts/`** — The `User` model (sign in with email) and the register, login, refresh, profile and change-password endpoints.
- **`apps/ai_models/`** — The catalog of models, their prices, cost calculation (`pricing_service.py`) and the `seed_models` command.
- **`apps/comparisons/`** — The comparison workflow and the experiment history endpoints. `comparison_service.py` runs the models concurrently and orchestrates the judge, `metrics_service.py` normalizes latency and tokens (unavailable is `null`, never zero), `persistence.py` saves experiments, runs and answers, `history.py` builds the history responses.
- **`apps/evaluations/`** — The AI judge: the rubric (`EvaluationCriterion`), per-criterion scores (`Evaluation`) and the judge's verdict per answer (`ResponseEvaluation`). `judge_service.py` sends the answers to the judge, validates its JSON and maps the anonymous labels back to models.
- **`providers/`** — All provider-specific code. Nothing else talks to a provider API.
- **`tests/<feature>/`** — Tests for new work live in a folder named after the feature. Older unit tests still sit in `apps/<app>/tests/`.

### Database

PostgreSQL, nine tables across four apps: `User` (`accounts`); `AIModel` (`ai_models`); `Experiment`, `ExperimentModel`, `Run`, `ModelResponse` (`comparisons`); `EvaluationCriterion`, `Evaluation`, `ResponseEvaluation` (`evaluations`). See [`docs/database.md`](docs/database.md) for every table and rule, and open `docs/erd.html` for the diagram. After changing a model, run `python manage.py makemigrations` and commit the migration with the code.

## 5. How a Comparison Works

1. `POST /api/comparisons/` receives a prompt and two or more model ids. It is validated before anything is saved (empty prompt, unknown or inactive model, duplicates → `400`).
2. An **experiment** and its first **run** are saved. The experiment belongs to the signed-in user, or to nobody for an anonymous request. (`POST /api/experiments/{id}/rerun/` adds a new run to an existing experiment instead.)
3. The models are called **concurrently**, each with retries and a timeout. Every outcome is saved, success or failure, with latency, tokens and cost.
4. If at least two answers succeeded, the judge scores them (accuracy, relevance, clarity, completeness, overall), picks a winner and explains it. The judge's output is validated: decimal criterion scores are rounded, and unusable output (invalid JSON or format) is retried once. Otherwise the evaluation is skipped.
5. The run is closed with a status and an `evaluation_status`, and the response is returned.

| Run `status` | Meaning |
|---|---|
| `pending`, `running` | Created, or still being processed. |
| `completed` | The run finished (some answers may still have failed). |
| `failed` | The run stopped on an unexpected error. |

| `evaluation_status` | Meaning |
|---|---|
| `completed` | The judge produced a verdict. |
| `skipped` | Fewer than two successful answers, so nothing to compare. |
| `failed` | The judge could not evaluate (for example its provider or key failed). |
| `pending` | Not evaluated yet. |

**Why a model failed.** A failed answer has `error.code` and a message the user can act on. The provider's own text is only kept in the stored error detail.

| `error.code` | Meaning | Worth retrying |
|---|---|---|
| `provider_overloaded` | The provider is overloaded (5xx). | Yes |
| `provider_rate_limited` | The provider's rate limit was hit (429). | Yes, later |
| `provider_timeout` | No answer within the timeout. | Yes |
| `provider_error` | Anything else (bad key, unknown model, ...). | Not without a fix |

## 6. Setup and Installation

### Prerequisites

- Python 3.12, PostgreSQL and Git.
- API keys for the providers you want to use (see section 3). Gemini, Groq and OpenRouter have free tiers; OVHcloud needs no key.

### Clone and install

```bash
git clone git@github.com:GSG-Project/backend.git
cd backend
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

In Windows PowerShell, if scripts are disabled, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` first and activate with `. .\.venv\Scripts\Activate.ps1`.

### Create the database and configure

```bash
createdb llm_sandbox
cp .env.example .env
```

Edit `.env`. **Never commit `.env` or real API keys**; both `.env` and `.venv/` are in `.gitignore`.

| Variable | Purpose |
|---|---|
| `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS` | Django basics. |
| `DATABASE_URL` | For example `postgres://user:password@localhost:5432/llm_sandbox`. |
| `CORS_ALLOWED_ORIGINS` | Frontend origins allowed to call the API. |
| `GEMINI_API_KEY`, `GROQ_API_KEY`, `OPENROUTER_API_KEY`, `NVIDIA_API_KEY`, `TOGETHER_API_KEY` | Provider keys. A missing key only makes that provider's models fail. |
| `OVH_AI_ENDPOINTS_API_KEY` | Optional; raises the OVHcloud rate limit. |
| `BREVO_API_KEY` | Brevo key used to email password reset links and sign-in codes (HTTPS API, because free Render blocks SMTP). Without it, development prints emails to the console and production sends none. |
| `EMAIL_FROM` | Verified sender, for example `ModelJudge <you@example.com>`. |
| `FRONTEND_URL` | Frontend address used in reset links. |
| `JUDGE_MODEL` | The judge's model id on Groq (default `openai/gpt-oss-120b`). |
| `AI_REQUEST_TIMEOUT_SECONDS` | Timeout per provider request (default 60). |
| `AI_MAX_RETRIES`, `AI_RETRY_BASE_DELAY_SECONDS` | Retries for overloaded or rate-limited answers (default 2 and 1). |

## 7. Running the Application

```bash
python manage.py migrate
python manage.py seed_models      # supported models and the judge
python manage.py seed_criteria    # evaluation criteria
python manage.py runserver
```

Enter prices for models that have none (Gemini) in the admin, in USD per 1M tokens; until then their cost is reported as unavailable.

- API base URL: `http://127.0.0.1:8000/api/`
- Swagger: `http://127.0.0.1:8000/api/docs/` — ReDoc: `/api/redoc/` — Admin: `/admin/`

`manage.py` uses `config.settings.development`; `wsgi.py` and `asgi.py` use `config.settings.production`. Override with `DJANGO_SETTINGS_MODULE`.

### Render deployment

[`render.yaml`](render.yaml) installs dependencies and starts the service with:

```text
python manage.py migrate --noinput && python manage.py seed_models && python manage.py seed_criteria && gunicorn config.wsgi:application --timeout 120
```

So every deploy applies pending migrations and creates missing models before accepting requests. The 120-second Gunicorn timeout leaves room for slow providers and retries (Gunicorn's default of 30 seconds would kill them). The health check path is `/api/health/`.

Set these environment variables on the service: `DATABASE_URL` (the Render PostgreSQL internal URL), `SECRET_KEY`, `CORS_ALLOWED_ORIGINS`, and the provider keys (`GEMINI_API_KEY`, `GROQ_API_KEY`, `OPENROUTER_API_KEY`, optionally `NVIDIA_API_KEY`, `TOGETHER_API_KEY` and `OVH_AI_ENDPOINTS_API_KEY`). Redeploy after changing them. If the service was created manually instead of from the blueprint, set its Start Command to the line above.

## 8. API Overview

Interactive documentation is generated from the code and served at `/api/docs/` (Swagger) and `/api/redoc/`. It shows every endpoint with its description, request and response schemas, and examples. The examples below mirror it.

### Health Check

`GET /api/health/` (also `HEAD`) needs no token. It returns `200` with `{"status": "ok", "database": "ok"}` when the service can reach the database, and `503` with `{"status": "error", "database": "unavailable"}` when it cannot. It returns nothing private. Render uses it as the service health check (`render.yaml`).

**Keeping the free Render service awake:** a free web service sleeps after about 15 minutes without traffic, and the next request waits for it to wake up. Call `https://<your-service>.onrender.com/api/health/` every 10 minutes from an external scheduler, for example cron-job.org or UptimeRobot (free, `GET` or `HEAD`, expect `200`). A GitHub Actions schedule is not recommended here: the repository is private, so a 10-minute schedule would use more than the free monthly minutes.

### Authentication

Users sign in with email and password and receive JWTs. Comparisons stay open to anonymous users, so a token is optional on the other endpoints (but an invalid or expired token returns `401`, so drop it and refresh when that happens).

| Endpoint | Purpose |
|---|---|
| `POST /api/auth/register/` | Create an account (`email`, `first_name`, optional `last_name`, `password`). Returns the user and the tokens. |
| `POST /api/auth/login/` | `email` + `password` → `access` (30 min) and `refresh` (7 days). |
| `POST /api/auth/refresh/` | `refresh` → a new `access`. |
| `GET /api/auth/me/` | The signed-in user (`id`, `email`, `first_name`, `last_name`). Needs `Authorization: Bearer <access>`. |
| `PATCH /api/auth/me/` | Update the profile: send `first_name` and/or `last_name`. The email cannot be changed. |
| `POST /api/auth/change-password/` | `old_password` + `new_password` → `204`. Tokens already issued keep working until they expire. |

Emails are stored in lower case and are unique. Passwords are checked with Django's strength rules.

### Experiment History

Signed-in users can come back to their saved comparisons. Every endpoint here needs `Authorization: Bearer <access>`; a comparison made while signed in is saved under that user, and one made anonymously is saved but cannot be read back. Each returns `404` when the experiment does not exist or is not yours.

| Endpoint | Purpose |
|---|---|
| `GET /api/experiments/` | Your experiments, newest first, 20 per page (`?page=`, `?page_size=` up to 50). Each has its models, `run_count` and the `latest_run` with its winner. |
| `GET /api/experiments/{id}/` | One experiment with every run: each model's answer, metrics and error, per-criterion `scores`, and `evaluation` (winner, reasoning, and per answer: label, the four scores, `overall_score`, `strengths`, `weaknesses`). |
| `DELETE /api/experiments/{id}/` | Deletes the experiment with all its runs, answers and scores. Returns `204`. |
| `POST /api/experiments/{id}/rerun/` | Runs the same prompt against the same models again as a **new run of the same experiment** (no new experiment; earlier runs are kept). No request body. Returns `201` with the same shape as `POST /api/comparisons/`, or `400` if one of the models has been deactivated. |

The results use the same shape as a comparison response (`answer`, `metadata`, `status`, `error`), plus `scores`. Each run's `evaluation` has the same shape as `evaluation` in a comparison response, so one frontend component can show both; the judge's own usage fields are `null`. Runs judged before the verdict was stored have `label`, `strengths` and `weaknesses` as `null`, and an `overall_score` computed from the four scores.

### List Models

`GET /api/models/` returns the models users can compare (active and not a judge). The `id` is what you send back when comparing.

```json
{
  "models": [
    { "id": "gemini-3.8-flash", "name": "Gemini 3.8 Flash", "provider": "gemini", "is_active": true }
  ]
}
```

### Compare Models

`POST /api/comparisons/`

**Request:**

```json
{
  "prompt": "Explain REST APIs in simple terms.",
  "model_ids": ["gemini-3.8-flash", "gemini-3.6-flash"]
}
```

Select at least two different models (the frontend offers two). A request that fails validation returns `400` and saves nothing.

**Response (illustrative values):**

```json
{
  "experiment_id": 12,
  "run_id": 12,
  "prompt": "Explain REST APIs in simple terms.",
  "results": [
    {
      "model_id": "gemini-3.8-flash",
      "answer": "Example response A",
      "metadata": {
        "latency_ms": 1200.4,
        "input_tokens": 15,
        "output_tokens": 80,
        "total_tokens": 95,
        "cost": 0.000212,
        "cost_currency": "USD"
      },
      "status": "success",
      "error": null
    },
    {
      "model_id": "gemini-3.6-flash",
      "answer": null,
      "metadata": null,
      "status": "failed",
      "error": { "code": "provider_overloaded", "message": "This model is overloaded right now. Please try again in a moment." }
    }
  ],
  "evaluation": null,
  "evaluation_error": "At least two successful model responses are required for evaluation."
}
```

- Each comparison is saved as an experiment with one run, and `experiment_id` / `run_id` identify it.
- If one model fails, the other response is kept and the failure is reported separately. The judge needs at least two successful responses, otherwise `evaluation` is `null` and `evaluation_error` says why.
- `cost` is calculated from the token counts and the model's price (set in the admin). `input_tokens`, `output_tokens` and `cost` are `null` when the provider reports no usage or the price is unknown; they are never reported as zero.
- When two or more responses succeed, `evaluation` holds the judge's result: `winner`, `winner_model_id`, `reasoning`, and per-answer scores.

## 9. Evaluation and Metrics

The judge scores every successful answer from 1 to 10 on four criteria (accuracy, relevance, clarity, completeness), gives an overall score, a label (`A`, `B`, ...), strengths and weaknesses, picks a winner and explains why. The answers are anonymized (labels `A`, `B`, ... instead of model names), and the judge is asked not to prefer longer or more confident answers. Its verdict is saved with the run, so history shows exactly what the live result showed.

The judge is an automated assessment, not objective truth. It supports the user's decision; it does not decide for them. A model from the judge's own family may be slightly favored, which is why `gpt-oss-120b` is never offered for comparison.

Performance metrics are measured separately from quality:

- **Latency:** measured by the backend, for the successful attempt (waiting between retries is not counted).
- **Token usage:** read from the provider's usage data when it reports it, otherwise `null`.
- **Cost:** calculated from tokens and the model's price; `null` when either is unknown.
- **Reliability:** every failure is stored with its error code, so it can be analyzed later.

## 10. Testing

```bash
pytest                                        # needs PostgreSQL via DATABASE_URL
DATABASE_URL=sqlite:///:memory: pytest -q     # fast, no PostgreSQL needed
```

About 265 tests cover the comparison workflow, providers and their error mapping, retries, the judge (valid, invalid and decimal output), authentication, history and rerun, the health endpoint, seeding, migrations and the Swagger schema. External providers are never called: tests use fakes (`apps/comparisons/tests/fakes.py`) or patch the HTTP client, so they cost nothing and do not depend on free-tier limits. Manual checks against the real APIs are in `scripts/` (for example `python -m scripts.try_groq`) and are not part of `pytest`.

## 11. Development Guidelines

- Document every endpoint with `@extend_schema` (summary, description, request and response serializers, examples). `tests/test_api_docs.py` fails if the schema has errors, an endpoint is undocumented, or an example no longer matches its schema.
- Lint with `ruff check .` (install `requirements-dev.txt`). A few older files still have findings (import order) to clean up separately.
- Keep provider-specific code inside `providers/`, business logic inside the app `services/` packages, and views thin (validate input, delegate to services).
- Keep dependencies one-directional: `comparisons` may import from `evaluations`, `ai_models` and `providers`, never the reverse. Database links may point the other way (`Evaluation` references `comparisons.ModelResponse`); use a string reference there, not an import.
- Put tests for new work in `tests/<feature_name>/` (with an `__init__.py`).
- Never expose API keys or internal credentials in responses or logs.
- Use conventional commits (`feat:`, `fix:`, `docs:`, `chore:`).

### Adding a model

For a model on an existing provider, add it to `seed_models.py` (and set `is_active`, price) or create it in the admin. The `api_model_identifier` must be exactly what the provider expects.

### Adding a provider

If it speaks the OpenAI chat completions protocol, subclass `OpenAICompatibleProvider` (set `name`, `url`, `api_key_setting`, and `key_required = False` if no key is needed), add the key to `config/settings/base.py`, `.env.example` and `render.yaml`, add a branch in `providers/factory.py`, add the value to `AIModel.Provider` and run `makemigrations`. Otherwise subclass `BaseProvider` and implement `_generate_once`, raising the errors in `providers/exceptions.py` so retries and error codes work.

### Retiring a model

Add its identifier to `RETIRED_MODELS` in `seed_models.py`. The next deploy switches it off without deleting its history.

## 12. Known Limitations

- **Free tiers are fragile.** Gemini preview models are often overloaded, OpenRouter free models can be rate limited upstream or disappear, and OVHcloud's anonymous limit (2 requests/minute per model) is shared by all users. Failures are retried and reported clearly, but cannot be prevented.
- **The judge depends on Groq.** If `GROQ_API_KEY` is missing or invalid, comparisons still run but the evaluation fails (`evaluation_status: failed`). There is no fallback judge yet.
- Comparisons made while signed out are saved but cannot be read back, and cannot be claimed after signing in.
- Experiments created before accounts existed have no owner and are unreachable through history.
- Gemini models have no price seeded, so their cost is unavailable until prices are entered.
- The test suite is run on SQLite in quick checks; the full suite has not been verified on PostgreSQL in CI.

## 13. Future Improvements

- A fallback judge, and judge selection.
- Claiming anonymous experiments after sign-in; comparing runs of the same experiment.
- Pricing management in the API, and more than two models per comparison.
- More providers and models once their free tiers are verified (NVIDIA and Together AI are wired in and seeded).
- More detailed analytics, configurable evaluation criteria, and comparison by quality, speed and cost.

## 14. Project Status

The backend is deployed and in use by the frontend team. Authentication, comparisons with a judge, per-user history with rerun and delete, a health endpoint and five providers are implemented and tested. The current focus is reliability of the free providers and the quality of the judge's evaluation.
