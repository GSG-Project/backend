# Backend Guide for Express Developers

This guide explains how our Django backend is organized, using Express concepts you already know.

---

## 1. Django in one minute (compared to Express)

| You know this in Express | In our Django project | Where |
|---|---|---|
| `package.json` | `requirements.txt` | `backend/requirements.txt` |
| `node_modules/` | `.venv/` (virtual environment) | `backend/.venv/` |
| `npm install` | `pip install -r requirements.txt` | — |
| `npm run dev` | `python manage.py runserver` | — |
| `app.js` / `server.js` | `manage.py` + `config/` | `backend/config/` |
| `dotenv` + `.env` | `django-environ` + `.env` | `config/settings/base.py` |
| `app.use(cors())` | `django-cors-headers` | `config/settings/base.py` |
| `app.use(middleware)` | `MIDDLEWARE` list | `config/settings/base.py` |
| Router (`express.Router()`) | `urls.py` | each app + `config/urls.py` |
| Controller | View (`views.py`) | each app |
| `jsonwebtoken` + auth middleware | simplejwt + `@permission_classes` | `apps/accounts/` |
| Joi / Zod validation | Serializer (`serializers.py`) | each app |
| Mongoose / Sequelize / Prisma model | Model (`models.py`) | each app |
| Prisma migrations | Django migrations (`migrations/`) | each app |
| Service layer | `services/` folder | each app |
| Jest / Supertest | pytest + pytest-django | `tests/` folders |
| swagger-jsdoc | drf-spectacular (auto-generated) | `/api/docs/` |

Two libraries do most of the work:

- **Django**: the framework. It handles routing, the ORM (database), settings, the admin panel, and migrations.
- **Django REST Framework (DRF)**: an add-on for building JSON APIs. It handles serializers (validation and JSON conversion) and API views.

---

## 2. What is an "app"?

In Express you might group code by feature: `routes/users.js`, `controllers/users.js`, `models/User.js`.

Django does the reverse. Each feature is a folder called an **app**, and every app has the same set of files inside it:

```
apps/comparisons/
├── models.py        # database tables (like Mongoose schemas)
├── serializers.py   # validation + JSON shape (like Zod schemas)
├── views.py         # request handlers (like controllers)
├── urls.py          # routes (like express.Router())
├── services/        # business logic
├── admin.py         # registers models in the admin panel
├── apps.py          # app config (you rarely touch this)
├── migrations/      # auto-generated DB migration files
└── tests/           # tests for this app
```

Once you understand one app, you understand all of them.

---

## 3. The full folder structure

```
backend/
├── manage.py
├── config/
│   ├── settings/
│   │   ├── base.py
│   │   ├── development.py
│   │   └── production.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── apps/
│   ├── accounts/
│   ├── ai_models/
│   ├── comparisons/
│   └── evaluations/
├── providers/
│   ├── base.py
│   └── exceptions.py
├── tests/
├── pytest.ini
├── requirements.txt
├── .env.example
└── .gitignore
```

### `manage.py`

This is the command-line entry point, similar to the `scripts` section of `package.json`. You don't edit it; you just run commands through it:

```bash
python manage.py runserver        # start dev server (like npm run dev)
python manage.py makemigrations   # create migration files from model changes
python manage.py migrate          # apply migrations to the database
python manage.py createsuperuser  # create an admin user for /admin/
python manage.py shell            # interactive console with the project loaded
```

### `config/`: the project setup (your `app.js`)

- **`settings/base.py`**: the main configuration, shared by all environments. It covers installed apps, middleware, the database, CORS, DRF settings, and AI provider keys. Values come from `.env`, so secrets never go in code.
- **`settings/development.py`**: local overrides, such as `DEBUG = True` and the browsable API.
- **`settings/production.py`**: production overrides, such as `DEBUG = False` and HTTPS security settings.
- **`urls.py`**: the root router, like `app.use('/api/comparisons', comparisonsRouter)` in Express. It mounts each app's routes under `/api/` and serves the API docs.
- **`wsgi.py` / `asgi.py`**: entry points for production servers. You won't touch these.

`manage.py` uses development settings by default; `wsgi.py` and `asgi.py` use production settings.

### `apps/`: our features

#### `apps/accounts/`: users and sign-in
- Table `User`: replaces Django's default user. Sign in with **email** and password (no username); also stores a `name`. The project sets `AUTH_USER_MODEL = 'accounts.User'`, which must never change after the first migration.
- Auth is JWT via `djangorestframework-simplejwt` (like `jsonwebtoken` in Express): `register`, `login`, `refresh`, `me`. Routes are mounted at `/api/auth/`.
- Make a view require login with `@permission_classes([IsAuthenticated])`; then `request.user` is the signed-in user. Views without it stay public, and a valid token is still accepted.
- Reference users with `settings.AUTH_USER_MODEL` (or `get_user_model()`), never by importing `User` directly in other apps' models.

#### `apps/ai_models/`: supported models and pricing
- Table `AIModel`: the models users can compare, plus the judge model (`is_judge`). Stores each model's price per 1M input and output tokens.
- Load the starting data with `python manage.py seed_models`. Prices are not seeded; enter them in the admin.
- `services/pricing_service.py` calculates the estimated cost of a request from its token counts.
- Routes are mounted at `/api/models/`.

#### `apps/comparisons/`: the main workflow
- Tables `Experiment`, `ExperimentModel`, `Run`, `ModelResponse`: the prompt, the selected models, each execution, and each model's response and metrics.
- `services/comparison_service.py` runs the whole flow: it sends the prompt to both models **at the same time**, collects the results, and asks the judge to evaluate them.
- `services/metrics_service.py` handles latency and token counts. If a provider doesn't return token counts, it stores `null`, never `0`.
- Routes are mounted at `/api/comparisons/`.

#### `apps/evaluations/`: the AI judge
- Tables `EvaluationCriterion` and `Evaluation`: the rubric and the judge's score per response and criterion. Load the criteria with `python manage.py seed_criteria`.
- `services/judge_service.py` sends both responses to the judge model, hides model names to reduce bias, and **validates** the JSON the judge returns before it is used.
- Routes are mounted at `/api/evaluations/`.

### `providers/`: talking to AI APIs

This folder is plain Python, not a Django app. Each AI provider (OpenAI, Anthropic, Gemini, and so on) gets its own file.

- **`base.py`**: the shared interface every provider must follow. It's like a TypeScript `interface`, for example "every provider has a `generate(prompt)` method".
- **`exceptions.py`**: common errors (API error, timeout, rate limit) so the rest of the code handles failures the same way for every provider.
- To add a new provider, add a new file here that follows `base.py`. Nothing else needs to change.

### Other files

- **`tests/`**: tests grouped by feature, one folder per feature (for example `tests/user_history/test_history_api.py`). Older unit tests still live in each app's own `tests/` folder.
- **`pytest.ini`**: pytest config. It tells pytest which Django settings to use.
- **`requirements.txt`**: dependencies with exact versions.
- **`.env.example`**: a template for `.env`. Copy it to `.env` and fill in real values. **Never commit `.env`.**

---

## 4. How a request flows

Express:
```
request → middleware → router → controller → service → model → response
```

Our Django project:
```
request
  → MIDDLEWARE (config/settings/base.py)
  → config/urls.py           # "/api/comparisons/..." → comparisons app
  → apps/comparisons/urls.py # which view handles it
  → views.py                 # thin: validate input, call a service
      → serializers.py       # validates request body (like Zod)
      → services/            # business logic
          → providers/       # calls AI APIs
          → models.py        # saves to PostgreSQL
  → serializer turns the result into JSON
  → response
```

**Golden rule:** keep views thin. Views only receive the request, validate it with a serializer, call a service, and return the response. All logic goes in `services/`.

---

## 5. Example: adding an endpoint

Say we add a made-up `notes` app and want `GET /api/notes/` to return the active notes. (This is only an example of the pattern; the real tables are described in `database.md`.)

**Step 1: Model** (`apps/notes/models.py`). This defines the table, like a Mongoose schema.
```python
from django.db import models

class Note(models.Model):
    title = models.CharField(max_length=100)
    is_archived = models.BooleanField(default=False)
```
Then create and apply the migration:
```bash
python manage.py makemigrations
python manage.py migrate
```

**Step 2: Serializer** (`apps/notes/serializers.py`). This defines the JSON shape and validation.
```python
from rest_framework import serializers
from .models import Note

class NoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Note
        fields = ['id', 'title']
```

**Step 3: View** (`apps/notes/views.py`). This is the controller.
```python
from rest_framework.generics import ListAPIView
from .models import Note
from .serializers import NoteSerializer

class NoteListView(ListAPIView):
    queryset = Note.objects.filter(is_archived=False)
    serializer_class = NoteSerializer
```

**Step 4: Route** (`apps/notes/urls.py`)
```python
from django.urls import path
from .views import NoteListView

app_name = 'ai_models'

urlpatterns = [
    path('', NoteListView.as_view(), name='list'),
]
```

Finally, document it so it shows up properly in Swagger. Put `@extend_schema` above `@api_view` and describe what the endpoint does, its request, and its responses:

```python
from drf_spectacular.utils import extend_schema

@extend_schema(
    tags=["Notes"],
    summary="List the active notes",
    responses={200: NoteSerializer(many=True)},
)
@api_view(['GET'])
def note_list(request):
    ...
```

`tests/test_api_docs.py` fails if an endpoint is left undocumented.

That's it. After mounting the app's `urls.py` in `config/urls.py` (for example `path('notes/', include('apps.notes.urls'))`), the endpoint appears automatically in Swagger at `/api/docs/`.

> The `notes` app does not exist in the project. Add apps with `python manage.py startapp <name> apps/<name>` and register them in `LOCAL_APPS` in `config/settings/base.py`.

---

## 6. Running the project

```bash
cd backend
python3 -m venv .venv          # first time only
source .venv/bin/activate      # every new terminal (Windows: .venv\Scripts\activate)
pip install -r requirements.txt
cp .env.example .env           # then fill in SECRET_KEY, DATABASE_URL, API keys
createdb llm_sandbox           # create the PostgreSQL database (first time)
python manage.py migrate
python manage.py seed_models      # supported AI models and the judge
python manage.py seed_criteria    # evaluation criteria
python manage.py runserver
```

Then open:
- API: http://127.0.0.1:8000/api/
- Swagger docs: http://127.0.0.1:8000/api/docs/
- Admin panel: http://127.0.0.1:8000/admin/

Run the tests:
```bash
pytest
```

When you install a new package, update the requirements:
```bash
pip install some-package
pip freeze > requirements.txt
```

---

## 7. Rules for working on the project

1. **Business logic goes in `services/`**, not in views.
2. **Provider-specific code goes in `providers/`.** Services must not know the details of each AI API.
3. **Dependencies go one way.** `comparisons` may use `evaluations`, `ai_models`, and `providers`. Those must never import from `comparisons`.
4. **Validate everything with serializers.** That includes the judge's JSON output.
5. **Never put secrets in code.** Read them from `.env` through settings.
6. **Changed a model? Run `makemigrations` and commit the migration file** with your code.
7. **Use `null` for missing metrics**, never `0`.
8. **Mock AI providers in tests** so tests don't burn API credits or hit rate limits.

---

## 8. Common gotchas coming from Express

- **No `async` by default.** Django views are normally synchronous. We use `httpx` with `asyncio` inside the comparison service to call models in parallel.
- **Migrations are generated, not hand-written.** Change `models.py`, then run `makemigrations`.
- **Trailing slashes matter.** Django routes end with `/`, for example `/api/comparisons/`.
- **Restart isn't needed.** `runserver` auto-reloads on file changes, like nodemon.
- **The admin panel is free.** Register a model in `admin.py` to get a full UI for it at `/admin/`.
