from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    tg_token: str
    tg_webhook_secret: str
    tg_allowed_ids: str
    webhook_url: str
    port: int = 8080

    llm_model: str

    sheet_id: str
    sheet_tab: str
    categories: str
    payment_methods: str
    google_sa_json: str

    tz: str = "Europe/Rome"

    @property
    def allowed_ids(self) -> set[int]:
        return {int(x) for x in self.tg_allowed_ids.split(",")}

    @property
    def category_list(self) -> list[str]:
        return [c.strip() for c in self.categories.split(",") if c.strip()]

    @property
    def payment_method_list(self) -> list[str]:
        return [m.strip() for m in self.payment_methods.split(",") if m.strip()]
