from .dictionary import router as dictionary_router
from .history import router as history_router
from .models import router as models_router
from .session import router as session_router
from .settings import router as settings_router
from .snippets import router as snippets_router
from .style import router as style_router
from .system import router as system_router

__all__ = [
    "dictionary_router",
    "history_router",
    "models_router",
    "session_router",
    "settings_router",
    "snippets_router",
    "style_router",
    "system_router",
]
