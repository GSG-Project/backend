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

#### `apps/ai_models/`: supported models and pricing
- Stores the list of AI models users can choose from (for example "gpt-x", "claude-y").
- Stores each model's pricing (cost per input token and per output token).
- `services/pricing_service.py` calculates the estimated cost of a request from its token counts.
- Routes are mounted at `/api/models/`.

#### `apps/comparisons/`: the main workflow
- Stores experiments: the prompt, the selected models, and each model's response and metrics.
- `services/comparison_service.py` runs the whole flow: it sends the prompt to both models **at the same time**, collects the results, and asks the judge to evaluate them.
- `services/metrics_service.py` handles latency and token counts. If a provider doesn't return token counts, it stores `null`, never `0`.
- Routes are mounted at `/api/comparisons/`.

#### `apps/evaluations/`: the AI judge
- Stores the evaluation rubric and the judge's results.
- `services/judge_service.py` sends both responses to the judge model, hides model names to reduce bias, and **validates** the JSON the judge returns before it is used.
- Routes are mounted at `/api/evaluations/`.

### `providers/`: talking to AI APIs

This folder is plain Python, not a Django app. Each AI provider (OpenAI, Anthropic, Gemini, and so on) gets its own file.

- **`base.py`**: the shared interface every provider must follow. It's like a TypeScript `interface`, for example "every provider has a `generate(prompt)` method".
- **`exceptions.py`**: common errors (API error, timeout, rate limit) so the rest of the code handles failures the same way for every provider.
- To add a new provider, add a new file here that follows `base.py`. Nothing else needs to change.

### Other files

- **`tests/`**: tests that cover more than one app. Each app also has its own `tests/` folder.
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

Say we want `GET /api/models/` to return the list of supported models.

**Step 1: Model** (`apps/ai_models/models.py`). This defines the table, like a Mongoose schema.
```python
from django.db import models

class AIModel(models.Model):
    name = models.CharField(max_length=100, unique=True)
    provider = models.CharField(max_length=50)
    is_active = models.BooleanField(default=True)
```
Then create and apply the migration:
```bash
python manage.py makemigrations
python manage.py migrate
```

**Step 2: Serializer** (`apps/ai_models/serializers.py`). This defines the JSON shape and validation.
```python
from rest_framework import serializers
from .models import AIModel

class AIModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIModel
        fields = ['id', 'name', 'provider']
```

**Step 3: View** (`apps/ai_models/views.py`). This is the controller.
```python
from rest_framework.generics import ListAPIView
from .models import AIModel
from .serializers import AIModelSerializer

class AIModelListView(ListAPIView):
    queryset = AIModel.objects.filter(is_active=True)
    serializer_class = AIModelSerializer
```

**Step 4: Route** (`apps/ai_models/urls.py`)
```python
from django.urls import path
from .views import AIModelListView

app_name = 'ai_models'

urlpatterns = [
    path('', AIModelListView.as_view(), name='list'),
]
```

That's it. `config/urls.py` already mounts this app at `/api/models/`, and the endpoint appears automatically in Swagger at `/api/docs/`.

> The code above is only an example to show the pattern. The real models will be designed as part of the feature tasks.

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
