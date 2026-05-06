"""Application settings loaded from environment.

All third-party credentials (Supabase service role, OpenAI, Google) are
optional at boot time. Endpoints that need them will fail loudly when
called, but the FastAPI process starts cleanly so the frontend can still
exercise the magic-link login flow against Supabase directly.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Supabase
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    SUPABASE_PROJECT_REF: str = ""           # derived from SUPABASE_URL when blank
    SUPABASE_JWT_SECRET: str = ""            # only required for self-verification flows; Supabase verifies tokens by default

    # OpenAI
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    OPENAI_MONTHLY_BUDGET_USD: int = 50

    # Google (Drive Picker — client-side OAuth flow)
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""           # not used by the GIS flow; keep empty unless you switch to server-side OAuth
    GOOGLE_PICKER_API_KEY: str = ""

    # Backend
    BACKEND_PORT: int = 8001
    # Default to localhost dev only. Production deployments MUST set this
    # env var explicitly with the public frontend domain (Railway, custom DNS).
    BACKEND_CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    # Limits
    MAX_DOCUMENT_SIZE_MB: int = 25
    MAX_DOCUMENTS_PER_CASE: int = 200

    @property
    def cors_origins_list(self) -> list[str]:
        if self.BACKEND_CORS_ORIGINS.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.BACKEND_CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()
