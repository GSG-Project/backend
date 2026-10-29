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
| Python | Backend programming language |
| FastAPI | REST API framework |
| Pydantic | Request and response validation |
| AI Model APIs | Generate model responses and evaluate them |
| pytest | Automated testing |
| PostgreSQL (optional for the initial MVP) | Persist comparison history |
| SQLAlchemy (if PostgreSQL is implemented) | Database interaction |

The exact AI providers and models will be selected after testing their free-tier availability, rate limits, and API capabilities.

## 3. Project Structure

```text
backend/
├── app/
│   ├── main.py
│   ├── api/
│   │   └── comparisons.py
│   ├── services/
│   │   ├── model_service.py
│   │   ├── judge_service.py
│   │   └── metrics_service.py
│   ├── providers/
│   │   ├── base.py
│   │   ├── provider_a.py
│   │   └── provider_b.py
│   ├── schemas/
│   │   └── comparison.py
│   └── database/
│       ├── models.py
│       └── session.py
├── tests/
├── requirements.txt
└── .env
```

### Directory Responsibilities

- **`main.py`** — Creates the FastAPI application and registers the API routes.
- **`api/`** — Defines HTTP endpoints and handles incoming requests.
- **`services/model_service.py`** — Coordinates calls to the selected AI models.
- **`services/judge_service.py`** — Sends model responses to the Judge Model and processes its evaluation.
- **`services/metrics_service.py`** — Collects and normalizes latency, token usage, and other available metrics.
- **`providers/`** — Contains provider-specific API integrations. Each provider translates the common interface into the provider's API format.
- **`schemas/`** — Defines validated request and response structures using Pydantic.
- **`database/`** — Contains database models and connection/session management if persistence is enabled.
- **`tests/`** — Contains automated tests for services, API endpoints, and error handling.
- **`requirements.txt`** — Lists Python dependencies.
- **`.env`** — Stores local environment variables and API credentials.

## 4. How the System Works

The intended comparison workflow is:

1. The user submits a prompt and selects two AI models.
2. The backend validates the request.
3. The Model Service sends the same prompt to both models.
4. The backend collects the responses and measures their execution times.
5. The Judge Service evaluates both responses using predefined quality criteria.
6. The Metrics Service collects available performance and token-usage information.
7. The backend returns a structured comparison result to the frontend.
8. The frontend displays both answers, evaluation results, and metrics so the user can decide which response is more suitable.

The two model calls should run concurrently when practical to reduce the overall waiting time.

If one model fails, the backend should preserve the successful response whenever possible and report the failure separately.

## 5. Setup and Installation

### Prerequisites

- Python 3.11 or a compatible version supported by the selected dependencies.
- pip.
- API credentials for the selected AI providers.
- Git.

### Clone the Repository

```bash
git clone <repository-url>
cd <repository-folder>/backend
```

Replace the placeholders with your repository URL and folder name.

### Create a Virtual Environment

**Windows:**

```bash
python -m venv .venv
.venv\Scripts\activate
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

### Configure Environment Variables

Create a `.env` file in the backend directory.

Example:

```env
APP_ENV=development

PROVIDER_A_API_KEY=your_provider_a_api_key
PROVIDER_B_API_KEY=your_provider_b_api_key

# Optional: configure these when database persistence is implemented.
DATABASE_URL=
```

Use the actual environment-variable names required by your implementation. The example names above are placeholders until the providers are finalized.

**Security:** Never commit `.env` or real API keys to Git. Add `.env` and `.venv/` to `.gitignore`, and provide a `.env.example` file containing placeholders for teammates.

## 6. Running the Application

Once `app/main.py` contains the FastAPI application instance named `app`, start the development server with:

```bash
uvicorn app.main:app --reload
```

The local API will be available at:

- API base URL: `http://127.0.0.1:8000`
- Interactive Swagger documentation: `http://127.0.0.1:8000/docs`
- Alternative API documentation: `http://127.0.0.1:8000/redoc`

These URLs become available after the application and routes are implemented.

## 7. API Overview

The main planned endpoint is:

### Compare Models

`POST /api/comparisons`

**Example request:**

```json
{
  "prompt": "Explain REST APIs in simple terms.",
  "models": [
    "model-a",
    "model-b"
  ]
}
```

**Illustrative response:**

```json
{
  "comparison_id": "example-id",
  "responses": [
    {
      "model": "model-a",
      "text": "Example response A",
      "latency_ms": 1200,
      "input_tokens": null,
      "output_tokens": null,
      "error": null
    },
    {
      "model": "model-b",
      "text": "Example response B",
      "latency_ms": 1800,
      "input_tokens": 15,
      "output_tokens": 80,
      "error": null
    }
  ],
  "judge": {
    "score_a": 8,
    "score_b": 7,
    "reason": "Response A is clearer and more complete."
  }
}
```

The example values are illustrative and do not represent real model results. The final schema may change during implementation.

Token counts should be `null` when the provider does not supply reliable usage information; they should not be reported as zero.

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

- Keep provider-specific code inside `providers/`.
- Keep business logic inside `services/`.
- Validate requests and responses using Pydantic schemas.
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
