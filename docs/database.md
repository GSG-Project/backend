# Database

PostgreSQL, managed with Django migrations. Open [`erd.html`](erd.html) in a browser for the diagram.

```
AIModel ──< ExperimentModel >── Experiment ──< Run ──< ModelResponse ──< Evaluation >── EvaluationCriterion
   └────────── judge_model (optional) ─────────────┘          └── ExperimentModel
```

Each app owns its tables:

| App | Tables |
|---|---|
| `accounts` | `User` |
| `ai_models` | `AIModel` |
| `comparisons` | `Experiment`, `ExperimentModel`, `Run`, `ModelResponse` |
| `evaluations` | `EvaluationCriterion`, `Evaluation` |

## Conventions

- **`NULL` means "not available"**, never `0`. This applies to prices, token counts, latency and cost.
- **Models and criteria with history are never deleted**, only deactivated (`is_active`). Deleting them is blocked by the database (`PROTECT`).
- **Deleting an experiment deletes its runs and responses**, and deleting a response deletes its scores.
- **Rules that span tables** (marked "checked in `save()`" below) cannot be enforced by the database. They are skipped by `bulk_create`, `.update()` and raw SQL, so create these rows with `save()` or `objects.create()`.

## `User`

A person with an account (`apps/accounts`). It replaces Django's default user, so it was created before any other migration ran.

| Field | Notes |
|---|---|
| `email` | Unique, stored in lower case. This is the sign-in name |
| `name` | Display name |
| `password` | Hashed by Django, never stored in clear text |
| `is_active`, `is_staff`, `is_superuser`, `date_joined`, `last_login` | Standard Django account fields |

There is no username. Other apps point to it with `settings.AUTH_USER_MODEL`.

## `AIModel`

A model in the catalog: either one users can compare, or a judge.

| Field | Notes |
|---|---|
| `name` | Display name |
| `provider` | `gemini` or `groq` |
| `api_model_identifier` | Unique. The id sent to the provider API |
| `input_price_per_million`, `output_price_per_million` | Price per 1M tokens. `NULL` = unknown, so cost is unavailable |
| `currency` | 3-letter code, default `USD` |
| `is_active` | Inactive models are hidden everywhere but stay in the database |
| `is_judge` | Judges evaluate responses and are not offered for comparison |

Load the starting data with `python manage.py seed_models`. It only creates missing rows and never changes existing ones, so admin edits are kept. Prices are not seeded.

## `Experiment`

One comparison request: the prompt and the models chosen.

| Field | Notes |
|---|---|
| `user` | Who ran it. Empty for anonymous comparisons. Deleting the user deletes their experiments |
| `prompt` | The text sent to every model |
| `created_at` | Indexed, for history listings (also indexed together with `user`) |

Models are linked through `ExperimentModel`. Anonymous experiments are saved but can never be listed or read later, because nothing identifies their owner.

## `ExperimentModel`

Links an experiment to a model it uses.

- Unique per (`experiment`, `ai_model`): the same model cannot be picked twice.
- The MVP allows exactly two models per experiment. This is enforced by the comparison service, not the database, so it can be raised later without a migration.

## `Run`

One execution of an experiment. A rerun adds a run and keeps earlier results.

| Field | Notes |
|---|---|
| `status` | `pending`, `running`, `completed`, `failed` |
| `started_at`, `completed_at` | `completed_at` is required once the run is `completed` or `failed` |
| `judge_model` | Which judge scored this run. Optional until judged. The admin only offers models with `is_judge` |
| `evaluation_status` | `pending`, `completed`, `failed`, `skipped` |
| `evaluation_error` | Required when `evaluation_status` is `failed` |
| `winner` | The judge's pick, an `ExperimentModel` of the same experiment (checked in `save()`). Empty unless the evaluation completed |
| `judge_reasoning` | The judge's explanation. Empty unless the evaluation completed |

`evaluation_status` tells "the judge failed" apart from "not judged yet". `skipped` means fewer than two successful responses, so there was nothing to compare. A `completed` evaluation requires a `judge_model`.

## `ModelResponse`

The result of sending the prompt to one model in one run.

| Field | Notes |
|---|---|
| `run`, `experiment_model` | Unique together: one response per model per run |
| `response_text` | `NULL` for a failed call |
| `input_tokens`, `output_tokens`, `latency_ms` | `NULL` when unavailable |
| `cost` | Calculated from tokens and the model's prices. `NULL` when either is unknown |
| `status` | `success` or `failed` |
| `error_message` | Empty unless failed |

Rules:
- A `success` response must have `response_text` (database check).
- The run and the experiment model must belong to the same experiment (checked in `save()`).

## `EvaluationCriterion`

A rubric criterion the judge scores. All responses in a run are scored against the same criteria, so scores are comparable.

`python manage.py seed_criteria` loads **accuracy, relevance, clarity, completeness**, which are the criteria the judge prompt scores today. If you change the criteria, change the judge prompt in `apps/evaluations/services/judge_service.py` to match.

## `Evaluation`

The judge's score for one response on one criterion.

- Unique per (`response`, `criterion`).
- `score` is 1 to 10 (database check).
- A failed response cannot be scored (checked in `save()`).
- `feedback` is optional text.

`evaluations` refers to `comparisons.ModelResponse` by string, so the `evaluations` app does not import `comparisons`.

## How a comparison is saved

`ComparisonService` (in `apps/comparisons/services/`) saves as it goes, so a failure part-way keeps what already succeeded.

1. The request is validated against the catalog (`AIModel`: active, not a judge). An invalid request saves nothing.
2. An `Experiment` (with the signed-in `user`, if any), its `ExperimentModel` rows and a `Run` (`running`) are created.
3. The models are called concurrently. Worker threads only call the providers; the results are saved afterwards in the request thread.
4. Each result becomes a `ModelResponse` (`success` or `failed`). Cost is calculated from tokens and the model's prices, and is `NULL` when either is unknown.
5. With two or more successful responses the judge is called. The scores go to `Evaluation`, and the winner and reasoning to `Run`. Otherwise the evaluation is `skipped`, or `failed` with the error.
6. The run is closed: `failed` if no model answered, `completed` otherwise. If an unexpected error stops the process, the run is closed as `failed` and is never left `running`.

Models are called through the provider named on `AIModel.provider` (`providers/factory.py`). The judge model row is created from the `JUDGE_MODEL` setting if it is missing, and missing criteria are created from `apps/evaluations/criteria.py`, so scores are never dropped.

## Known limitations

- **Part of the judge output is not stored.** The winner and its reasoning are saved on `Run`, and the per-criterion scores in `Evaluation`. The overall score (the average of the criteria), and the per-answer strengths and weaknesses, are returned by the API but not saved.
- **No rubric or prompt history.** Editing a criterion changes what older scores mean, and the judge prompt is not stored per run. Needed for FR-20 and FR-21.
- **No price history.** `cost` is stored on each response, but the prices used are not. Needed if prices change often (FR-22).
- **Anonymous experiments cannot be claimed.** If someone compares without signing in and registers afterwards, those experiments stay ownerless. Claiming them is planned as a later task.
