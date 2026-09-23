"""Research-only strategy placeholder; no DRI model is frozen by this experiment."""


def predict():
    """Prevent accidental submission before Train-only selection and Freeze."""
    raise RuntimeError("DM-20260910-02 is research-only; no frozen DRI model artifact exists")
