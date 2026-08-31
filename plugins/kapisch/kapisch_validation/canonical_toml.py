from __future__ import annotations
import json, math

def _value(value: object) -> str:
    if isinstance(value, str): return json.dumps(value, ensure_ascii=False)
    if isinstance(value, bool): return 'true' if value else 'false'
    if isinstance(value, int): return str(value)
    if isinstance(value, float):
        if not math.isfinite(value): raise ValueError('non-finite float')
        return repr(value)
    if isinstance(value, list): return '[' + ', '.join(_value(v) for v in value) + ']'
    if isinstance(value, dict):
        if not all(isinstance(k, str) for k in value): raise ValueError('non-string key')
        return '{' + ', '.join(f'{k} = {_value(value[k])}' for k in sorted(value)) + '}'
    raise ValueError(f'unsupported TOML value: {type(value).__name__}')

def render_toml(data: dict[str, object], *, key_order: tuple[str, ...] = ()) -> bytes:
    if not isinstance(data, dict) or not all(isinstance(k, str) for k in data): raise ValueError('root must use string keys')
    keys = [k for k in key_order if k in data] + sorted(k for k in data if k not in key_order)
    return (''.join(f'{key} = {_value(data[key])}\n' for key in keys)).encode('utf-8')
