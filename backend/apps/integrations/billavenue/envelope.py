from .crypto import encrypt_payload
from .request_id import generate_billavenue_request_id


def build_encrypted_envelope(
    *,
    payload_text: str,
    access_code: str,
    institute_id: str,
    ver: str,
    working_key: str,
    iv: str,
    request_id: str | None = None,
    key_derivation: str = 'rawhex',
    enc_request_encoding: str = 'base64',
):
    rid = request_id or generate_billavenue_request_id()
    return {
        'accessCode': access_code,
        'requestId': rid,
        'encRequest': encrypt_payload(
            payload_text,
            working_key=working_key,
            iv=iv,
            key_derivation=key_derivation,
            output_encoding=enc_request_encoding,
        ),
        'ver': ver,
        'instituteId': institute_id,
    }
