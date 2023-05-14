def deep_update(mapping, updating_mapping):
    """Recursively merge updating_mapping into mapping."""
    updated_mapping = mapping.copy()
    for k, v in updating_mapping.items():
        if k in updated_mapping and isinstance(updated_mapping[k], dict) and isinstance(v, dict):
            updated_mapping[k] = deep_update(updated_mapping[k], v)
        else:
            updated_mapping[k] = v
    return updated_mapping
