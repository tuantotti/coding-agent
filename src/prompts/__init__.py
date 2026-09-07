"""Load version-controlled prompts without embedding them in Python modules."""

from importlib.resources import files


def load_prompt(name: str, /, **values: object) -> str:
    """Return a prompt template rendered with the supplied values."""
    prompt_path = files(__package__).joinpath(f"{name}.md")
    try:
        template = prompt_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ValueError(f"Unknown prompt template: {name}") from exc
    return template.format(**values)
