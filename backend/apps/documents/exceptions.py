class TransientProcessingError(Exception):
    """A temporary problem (network, API limit). Worth retrying."""


class PermanentProcessingError(Exception):
    """The document itself is bad (empty, corrupt, unreadable). Retrying will not help."""
