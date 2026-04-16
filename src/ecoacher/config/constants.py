SPELL_SERVER_NAME = "ecoacher-spell"
DEFAULT_LOG_LEVEL = "DEBUG"
OPENCODE_PING_ENABLED = False
OPENCODE_PING_INTERVAL_MS = 5000
DEFAULT_PROFILE = "normal"
SUPPORTED_PROFILES = ("normal", "dev")


def app_id_for_profile(profile: str) -> str:
    if profile == "dev":
        return "ecoacher-dev"
    return "ecoacher"


def spell_server_name_for_profile(profile: str) -> str:
    if profile == "dev":
        return f"{SPELL_SERVER_NAME}-dev"
    return SPELL_SERVER_NAME

CHECK_SCHEMA = {
    "type": "object",
    "properties": {
        "corrected_phrase": {
            "type": "string",
            "description": "Corrected English phrase or natural English translation",
        },
        "understood_meaning_ru": {
            "type": "string",
            "description": (
                "Russian translation of how the agent understood the original English input; "
                "must be an empty string for Russian input"
            ),
        },
        "summary_ru": {
            "type": "string",
            "description": "Short Russian summary",
        },
        "corrections": {
            "type": "array",
            "description": "Detailed correction items in Russian for English input; empty for Russian input",
            "items": {
                "type": "object",
                "properties": {
                    "original_fragment": {
                        "type": "string",
                        "description": "Original fragment with the issue",
                    },
                    "corrected_fragment": {
                        "type": "string",
                        "description": "Corrected fragment",
                    },
                    "category": {
                        "type": "string",
                        "description": (
                            "Correction category such as grammar, article, preposition, "
                            "word_choice, word_order, punctuation, or unnatural_phrasing"
                        ),
                    },
                    "explanation_ru": {
                        "type": "string",
                        "description": "Detailed explanation in Russian with the relevant English rule",
                    },
                },
                "required": [
                    "original_fragment",
                    "corrected_fragment",
                    "category",
                    "explanation_ru",
                ],
            },
        },
    },
    "required": ["corrected_phrase", "understood_meaning_ru", "summary_ru", "corrections"],
}
