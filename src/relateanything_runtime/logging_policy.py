"""Reject logging of raw case content or provider secrets."""

FORBIDDEN_LOG_SUBSTRINGS = (
    "sourceSignedUrl",
    "signedUrl",
    "Authorization",
    "Bearer ",
    "api_key",
)


def assert_safe_log_message(message: str) -> None:
    lowered = message.lower()
    for token in FORBIDDEN_LOG_SUBSTRINGS:
        if token.lower() in lowered:
            raise ValueError("unsafe_log_content")
