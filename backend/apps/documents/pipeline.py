class TransientProcessingError(Exception):
    """A temporary problem (network, API limit). Worth retrying."""


class PermanentProcessingError(Exception):
    """The document itself is bad (empty, corrupt). Retrying will not help."""


def run_pipeline(document):
    """Day 7: only checks that the stored file can be read.

    Day 8 adds PDF parsing, Day 9 chunking, Day 10 embeddings.
    """
    try:
        with document.file.open("rb") as stored:
            first_bytes = stored.read(1024)
    except FileNotFoundError as exc:
        raise PermanentProcessingError("The stored file is missing.") from exc

    if not first_bytes:
        raise PermanentProcessingError("The stored file is empty.")
