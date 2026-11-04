# AI Model Arena — Backend

A Python backend for comparing responses from multiple AI language models. Users submit a prompt, receive responses from two selected models, and review an AI-generated evaluation to help them decide which response best meets their needs.

The project is being developed as a training MVP, with an initial focus on model integration, response comparison, evaluation, and performance metrics.

## 1. Project Objectives

- Send the same prompt to two AI models.
- Collect and display both model responses.
- Evaluate response quality using a separate Judge Model.
- Measure response latency and collect token usage when available.
- Allow users to make their own decisions based on the comparison results.
- Provide a modular architecture that supports adding more models in the future.

## 2. Technology Stack

| Technology | Purpose |
|---|---|
| Python 3.12 | Backend programming language |
| Django 5.2 | Web framework, ORM, admin |
| Django REST Framework | REST API layer, serializers, and request/response validation |
| drf-spectacular | OpenAPI schema and Swagger / ReDoc documentation |
| django-environ | Settings loaded from environment variables (`.env`) |
| django-cors-headers | CORS for the React frontend |
| httpx | Async HTTP client for calling AI provider APIs |
| PostgreSQL (psycopg 3) | Database |
| pytest + pytest-django | Automated testing |

The exact AI providers and models will be selected after testing their free-tier availability, rate limits, and API capabilities.

## 3. Project Structure

```text
backend/
├── config/                     # Django project configuration
│   ├── settings/
│   │   ├── base.py             # Shared settings
│   │   ├── development.py
│   │   └── production.py
│   ├── urls.py                 # Root URLs (/api/, /admin/, API docs)
│   ├── asgi.py
│   └── wsgi.py
├── apps/
│   ├── ai_models/              # Supported AI models, pricing, cost calculation
│   │   └── services/
│   │       └── pricing_service.py
│   ├── comparisons/            # Runs the workflow; stores experiments and responses
│   │   └── services/
│   │       ├── comparison_service.py
│   │       └── metrics_service.py
│   └── evaluations/            # AI judge: rubric, evaluation, output validation
│       └── services/
│           └── judge_service.py
├── providers/                  # Provider-specific AI API integrations
│   ├── base.py
│   └── exceptions.py
├── tests/                      # Cross-app / integration tests
├── scripts/                    # Manual checks against the real provider APIs (not tests)
├── docs/                       # ERD, database description, guide for Express developers
├── manage.py
├── pytest.ini
├── requirements.txt
└── .env.example
```

### Database

PostgreSQL, with seven tables across the three apps: `AIModel` (`ai_models`); `Experiment`, `ExperimentModel`, `Run`, `ModelResponse` (`comparisons`); `EvaluationCriterion`, `Evaluation` (`evaluations`). See [`docs/database.md`](docs/database.md) for each table and its rules, and open `docs/erd.html` in a browser for the diagram.

After changing a model, run `python manage.py makemigrations` and commit the migration file with the code.

### Directory Responsibilities

- **`config/`** — Django project configuration. Settings are split into `base`, `development`, and `production`.
- **`apps/ai_models/`** — The catalog of supported AI models and their pricing.
- **`apps/ai_models/services/pricing_service.py`** — Calculates estimated cost from token usage and model pricing.
- **`apps/comparisons/`** — The comparison workflow: API endpoints, serializers, and persisted experiments and model responses.
- **`apps/comparisons/services/comparison_service.py`** — Sends the same prompt to the selected models concurrently, collects metrics, and requests the judge evaluation.
- **`apps/comparisons/services/metrics_service.py`** — Normalizes latency and token usage, and marks metrics as unavailable rather than reporting them as zero.
- **`apps/evaluations/`** — The AI-as-a-Judge: evaluation rubric and stored evaluations.
- **`apps/evaluations/services/judge_service.py`** — Sends responses to the judge model, mitigates bias, and validates its structured JSON output.
- **`providers/`** — Provider-specific API integrations. Each provider implements the shared interface in `base.py`.
- **`docs/`** — `database.md` (tables and rules), `erd.html` (diagram), and `django-for-express-devs.md`.
- **`scripts/`** — Manual scripts that call the real Gemini/Groq APIs. Run from `backend/`, for example `python -m scripts.try_groq`. They are not part of `pytest`.
- **`apps/<app>/tests/`** — Unit tests for each app. **`tests/`** holds cross-app tests.
- **`.env.example`** — Template for local environment variables. Copy it to `.env`.

## 4. How the System Works

The intended comparison workflow is:

1. The user submits a prompt and selects two AI models.
2. The backend validates the request.
3. The Model Service sends the same prompt to both models.
4. The backend collects the responses and measures their execution times.
5. The Judge Service (`evaluations` app) evaluates both responses using predefined quality criteria.
6. The Metrics Service collects available performance and token-usage information.
7. The backend returns a structured comparison result to the frontend.
8. The frontend displays both answers, evaluation results, and metrics so the user can decide which response is more suitable.

The two model calls should run concurrently when practical to reduce the overall waiting time.

If one model fails, the backend should preserve the successful response whenever possible and report the failure separately.

## 5. Setup and Installation

### Prerequisites

- Python 3.12.
- PostgreSQL.
- API credentials for the selected AI providers.
- Git.

### Clone the Repository

```bash
git clone git@github.com:GSG-Project/backend.git
cd backend
```

### Create a Virtual Environment

**Windows:**

```bash
python -m venv .venv
.venv\Scripts\activate
```

In PowerShell, use the activation script with a process-scoped execution-policy
bypass if scripts are disabled:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
. .\.venv\Scripts\Activate.ps1
```

**Linux/macOS:**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Create the Database

```bash
createdb llm_sandbox
```

### Configure Environment Variables

```bash
cp .env.example .env
```

Then set `SECRET_KEY`, `DATABASE_URL` (for example `postgres://user:password@localhost:5432/llm_sandbox`), and the provider API keys. The provider variable names are placeholders until the providers are finalized.

**Security:** Never commit `.env` or real API keys to Git. Both `.env` and `.venv/` are listed in `.gitignore`.

## 6. Running the Application

```bash
python manage.py migrate
python manage.py seed_models      # supported AI models and the judge
python manage.py seed_criteria    # evaluation criteria
python manage.py runserver
```

Prices are not seeded. Enter each model's price per 1M tokens in the admin; until then, cost is reported as unavailable.

The local API will be available at:

- API base URL: `http://127.0.0.1:8000/api/`
- Swagger documentation: `http://127.0.0.1:8000/api/docs/`
- ReDoc documentation: `http://127.0.0.1:8000/api/redoc/`
- Django admin: `http://127.0.0.1:8000/admin/`

`manage.py` uses `config.settings.development` by default. `wsgi.py` and `asgi.py` use `config.settings.production`. To override either, set `DJANGO_SETTINGS_MODULE`.

## 7. API Overview

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

Select at least two different models. A request that fails validation returns `400` and saves nothing.

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
      "error": { "code": "provider_error", "message": "This model could not generate a response." }
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

## 8. Evaluation Criteria

The Judge Model is intended to evaluate response quality based on criteria such as:

- Accuracy and relevance.
- Clarity.
- Completeness.
- Following the user's instructions.

Performance metrics should be measured separately where possible:

- **Latency:** Measured by the backend.
- **Token usage:** Retrieved from provider usage metadata when available.
- **Cost:** Calculated from usage and applicable pricing if cost comparison is introduced.
- **Reliability:** Tracked through errors, timeouts, and successful responses.

The Judge Model provides an automated assessment, not a guaranteed objective truth. Its results should support the user's decision rather than automatically determine which model is best for every situation.

## 9. Testing

Run the automated test suite using:

```bash
pytest
```

The initial test plan should cover:

- Valid comparison requests.
- Empty or invalid prompts.
- Successful responses from both providers.
- Failure of one provider while the other succeeds.
- API timeouts and rate-limit errors.
- Missing token-usage metadata.
- Valid and invalid Judge Model outputs.
- Correct response structure returned to the frontend.

Unit tests should mock external provider calls where possible to avoid unnecessary API usage and dependence on free-tier limits.

## 10. Development Guidelines

- Lint with `ruff check .` (install with `pip install -r requirements-dev.txt`). The code added with the database tables passes; a few older files still have findings (import order, unused imports) to clean up separately.

- Keep provider-specific code inside `providers/`.
- Keep business logic inside the app `services/` packages.
- Validate requests and responses using DRF serializers.
- Keep views thin; they validate input and delegate to services.
- Keep code dependencies one-directional: `comparisons` may import from `evaluations`, `ai_models`, and `providers`, never the reverse. Database links may point the other way (`Evaluation` references `comparisons.ModelResponse`); use a string reference such as `'comparisons.ModelResponse'` there, not an import.
- Never expose API keys or internal credentials in API responses or logs.
- Handle provider errors consistently.
- Keep the API contract synchronized with the frontend team.
- Add a new provider by implementing the shared provider interface rather than rewriting the comparison workflow.
- Avoid introducing unnecessary infrastructure while the MVP is being developed.

## 11. Future Improvements

Potential extensions after the core MVP is working include:

- Support for additional AI models.
- Persistent comparison history.
- User accounts and personalized history.
- More detailed performance analytics.
- Configurable evaluation criteria.
- Comparison of quality, speed, and cost according to user preferences.

These features are future possibilities, not requirements for the initial MVP.

## 12. Project Status

**Current stage:** MVP planning and implementation.

The immediate development priorities are to:

1. Verify at least two suitable AI model APIs with usable free tiers.
2. Implement and test provider integrations.
3. Build the comparison and evaluation workflow.
4. Connect the backend to the React frontend.
5. Test the complete user journey and prepare a working demonstration.

The project will prioritize a working, testable comparison workflow over advanced features.
