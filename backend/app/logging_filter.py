import logging
import re

SECRET_RE = re.compile(
    r"sk-ant-[A-Za-z0-9_-]{8,}|sk-[A-Za-z0-9_-]{8,}"
    r"|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}"
)


def mask(value: object) -> object:
    return SECRET_RE.sub("***", value) if isinstance(value, str) else value


class SecretMaskingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = mask(record.msg)
        if isinstance(record.args, tuple):
            record.args = tuple(mask(a) for a in record.args)
        elif isinstance(record.args, dict):
            record.args = {k: mask(v) for k, v in record.args.items()}
        return True


def install_logging() -> None:
    """Mask secrets on every record at creation, whatever logger or handler emits it."""
    base = logging.getLogRecordFactory()
    if getattr(base, "_masks_secrets", False):
        return
    f = SecretMaskingFilter()

    def factory(*args, **kwargs):
        record = base(*args, **kwargs)
        f.filter(record)
        return record

    factory._masks_secrets = True  # type: ignore[attr-defined]
    logging.setLogRecordFactory(factory)
