import json
from xml.etree import ElementTree as ET

# Leading BOM / zero-width chars break `startswith('{')` and XML detection; BillAvenue often UTF-8-BOM-prefixes JSON.
_LEADING_JUNK = frozenset(('\ufeff', '\u200b', '\u2060', '\u200c', '\u200d', '\u00a0'))


def normalize_decrypted_plaintext(payload_text: str) -> str:
    s = (payload_text or '').strip()
    # UTF-8 BOM bytes (EF BB BF) wrongly interpreted as Latin-1 / cp1252 → three chars before real payload.
    if len(s) >= 3 and ord(s[0]) == 0xEF and ord(s[1]) == 0xBB and ord(s[2]) == 0xBF:
        s = s[3:].lstrip()
    while s and s[0] in _LEADING_JUNK:
        s = s[1:].lstrip()
    return s.strip()


def _try_json_raw_decode(s: str):
    """Parse first JSON object/array when the string has prefix/suffix noise or BOM was stripped late."""
    dec = json.JSONDecoder()
    for i, ch in enumerate(s):
        if ch not in '{[':
            continue
        try:
            return dec.raw_decode(s, i)[0]
        except Exception:
            continue
    return None


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


def _try_xml_document_to_dict(s: str):
    """BillAvenue often prefixes XML with whitespace, comments, or non-XML noise; find first '<'."""
    lt = s.find('<')
    if lt < 0:
        return None
    snippet = normalize_decrypted_plaintext(s[lt:])
    if not snippet.startswith('<'):
        return None
    try:
        root = ET.fromstring(snippet)
    except Exception:
        return None
    return {root.tag: _xml_to_obj(root)}


def parse_payload_text(payload_text: str):
    s = normalize_decrypted_plaintext(payload_text)
    if not s:
        return {}
    if s.startswith('{') or s.startswith('['):
        try:
            return json.loads(s)
        except Exception:
            recovered = _try_json_raw_decode(s)
            if recovered is not None:
                return recovered
    else:
        recovered = _try_json_raw_decode(s)
        if recovered is not None:
            return recovered

    xml_dict = _try_xml_document_to_dict(s)
    if xml_dict is not None:
        return xml_dict

    return {'raw': s}


def _get_ci(d: dict, name: str):
    """Case-insensitive key lookup (XML-to-dict often yields PascalCase tags)."""
    if not isinstance(d, dict):
        return None
    want = name.lower()
    for k, v in d.items():
        if str(k).lower() == want:
            return v
    return None


def _xml_local_name(key: str) -> str:
    """ElementTree uses '{namespaceURI}localName'; JSON may use 'ns:localName'."""
    k = str(key)
    if k.startswith('{') and '}' in k:
        return k.split('}', 1)[-1]
    if ':' in k:
        return k.rsplit(':', 1)[-1]
    return k


_RESPONSE_CODE_LOCAL_NAMES = frozenset(
    {
        'responsecode',
        'response_code',
        'complaintresponsecode',
        'respcode',
        'rescode',
        'errorcode',
        'statuscode',
        'bbpsresponsecode',
    }
)


def extract_response_code(normalized: dict, _depth: int = 0) -> str:
    """
    BillAvenue puts responseCode at varying depths and uses XML namespaces on keys.
    Walk the full tree (dicts + lists), not only single-child wrappers.
    """
    if not isinstance(normalized, dict) or not normalized or _depth > 14:
        return ''

    def _scalar_code(val) -> str:
        if val is None or isinstance(val, (dict, list)):
            return ''
        s = str(val).strip()
        return s

    for key, val in normalized.items():
        local = _xml_local_name(key).lower().replace('_', '')
        if local in _RESPONSE_CODE_LOCAL_NAMES:
            hit = _scalar_code(val)
            if hit:
                return hit

    for key in ('responseCode', 'response_code', 'complaintResponseCode'):
        if key in normalized:
            hit = _scalar_code(normalized.get(key))
            if hit:
                return hit

    v = _get_ci(normalized, 'responseCode') or _get_ci(normalized, 'complaintResponseCode')
    hit = _scalar_code(v)
    if hit:
        return hit

    for val in normalized.values():
        if isinstance(val, dict):
            c = extract_response_code(val, _depth + 1)
            if c:
                return c
        if isinstance(val, list):
            for it in val:
                if isinstance(it, dict):
                    c = extract_response_code(it, _depth + 1)
                    if c:
                        return c
    return ''
