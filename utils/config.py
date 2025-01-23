import pathlib
import yaml
from typing import Any, Dict, List

def load_configuration(config_file: str) -> Dict[str, Any]:
    """Load and merge configurations from multiple YAML files."""
    config = {}
    with pathlib.Path(config_file).expanduser().open(encoding="utf-8") as stream:
        config = yaml.safe_load(stream)
    return config