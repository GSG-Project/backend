GEMINI_MODELS = [
    {
        "id": "gemini-3.8-flash",
        "name": "Gemini 3.8 Flash",
        "provider": "gemini",
        "is_active": True,
    },
    {
        "id": "gemini-3.6-flash",
        "name": "Gemini 3.6 Flash",
        "provider": "gemini",
        "is_active": True,
    },
    {
        "id": "gemini-3.5-flash-lite",
        "name": "Gemini 3.5 Flash-Lite",
        "provider": "gemini",
        "is_active": True,
    },
    {
        "id": "gemini-3.1-flash-lite",
        "name": "Gemini 3.1 Flash-Lite",
        "provider": "gemini",
        "is_active": True,
    },
]


def get_available_models() -> list[dict]:
    """Return active models that can be selected by API consumers."""
    return [
        model
        for model in GEMINI_MODELS
        if model["is_active"]
    ]


def get_model_by_id(model_id: str) -> dict | None:
    """Return an active model by its public identifier."""
    return next(
        (
            model
            for model in get_available_models()
            if model["id"] == model_id
        ),
        None,
    )