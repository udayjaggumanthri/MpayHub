import json
from xml.etree import ElementTree as ET


def parse_payload_text(payload_text: str):
    s = (payload_text or '').strip()
    if not s:
        return {}
    if s.startswith('{') or s.startswith('['):
        try:
            return json.loads(s)
        except Exception:
            return {'raw': s}
    try:
        root = ET.fromstring(s)
    except Exception:
        return {'raw': s}

    def _xml_to_obj(elem):
        children = list(elem)
        if not children:
            return (elem.text or '').strip()
        out = {}
        for c in children:
            v = _xml_to_obj(c)
            if c.tag in out:
                if not isinstance(out[c.tag], list):
                    out[c.tag] = [out[c.tag]]
                out[c.tag].append(v)
            else:
                out[c.tag] = v
        return out

    return {root.tag: _xml_to_obj(root)}


def _get_ci(d: dict, name: str):
    """Case-insensitive key lookup (XML-to-dict often yields PascalCase tags)."""
    if not isinstance(d, dict):
        return None
    want = name.lower()
    for k, v in d.items():
        if str(k).lower() == want:
            return v
    return None


def extract_response_code(normalized: dict, _depth: int = 0) -> str:
    if not isinstance(normalized, dict) or not normalized or _depth > 6:
        return ''
    for key in ('responseCode', 'response_code', 'complaintResponseCode'):
        if key in normalized:
            return str(normalized.get(key) or '')
    v = _get_ci(normalized, 'responseCode') or _get_ci(normalized, 'complaintResponseCode')
    if v is not None and str(v).strip() != '':
        return str(v)
    if len(normalized) == 1 and isinstance(next(iter(normalized.values())), dict):
        nested = next(iter(normalized.values()))
        if isinstance(nested, dict):
            c = extract_response_code(nested, _depth + 1)
            if c:
                return c
    return ''
