from __future__ import annotations


def _build_onboarding_service():
    from . import admin_bot

    if (
        not admin_bot.BOT_MODULE_AVAILABLE
        or admin_bot.build_postgres_onboarding_repository is None
        or admin_bot.OnboardingService is None
    ):
        return None
    try:
        settings = admin_bot._load_bot_runtime_settings()
        if not settings.database_url:
            return None
        return admin_bot.OnboardingService(
            onboarding_repository=admin_bot.build_postgres_onboarding_repository(
                settings.database_url
            )
        )
    except Exception:
        return None