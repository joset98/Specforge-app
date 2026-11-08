import logging

import pytest

from app.logging_filter import SecretMaskingFilter

SECRETS = [
    "sk-ant-api03-AbCdEf123456789_xyz",
    "sk-proj-AbCdEf1234567890abcdef",
    "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123",
    "github_pat_11ABCDEFG0123456789_abcdefghijk",
]


@pytest.mark.parametrize("secret", SECRETS)
def test_masks_secret_in_message_and_args(secret):
    f = SecretMaskingFilter()
    rec = logging.LogRecord("x", logging.INFO, __file__, 1, f"key={secret}", None, None)
    f.filter(rec)
    assert secret not in rec.getMessage() and "***" in rec.getMessage()
    rec = logging.LogRecord("x", logging.INFO, __file__, 1, "key=%s n=%d", (secret, 3), None)
    f.filter(rec)
    assert secret not in rec.getMessage() and rec.getMessage().endswith("n=3")
