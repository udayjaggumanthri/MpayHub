from __future__ import annotations

from apps.bbps.models import BbpsComplaint, BbpsComplaintEvent, BbpsPaymentAttempt
from apps.bbps.service_flow.compliance import enforce_complaint_cooling
from apps.integrations.bbps_client import BBPSClient


def register_complaint(*, user, txn_ref_id: str, complaint_desc: str, complaint_disposition: str) -> BbpsComplaint:
    client = BBPSClient()
    attempt = BbpsPaymentAttempt.objects.filter(txn_ref_id=txn_ref_id, is_deleted=False).first()
    enforce_complaint_cooling(attempt=attempt)
    payload = {
        'txnRefId': txn_ref_id,
        'complaintDesc': complaint_desc,
        'complaintDisposition': complaint_disposition,
    }
    resp = client.register_complaint(payload)
    body = resp.get('complaintRegistrationResp', resp)
    c = BbpsComplaint.objects.create(
        user=user,
        attempt=attempt,
        txn_ref_id=txn_ref_id,
        complaint_id=str(body.get('complaintId') or ''),
        complaint_desc=complaint_desc,
        complaint_disposition=complaint_disposition,
        complaint_status=str(body.get('complaintStatus') or 'ASSIGNED'),
        response_code=str(body.get('responseCode') or ''),
        response_reason=str(body.get('responseReason') or ''),
        raw_payload=resp,
    )
    return c


def track_complaint(*, complaint: BbpsComplaint) -> dict:
    client = BBPSClient()
    payload = {'complaintId': complaint.complaint_id}
    resp = client.track_complaint(payload)
    body = resp.get('complaintTrackingResp', resp)
    complaint.complaint_status = str(body.get('complaintStatus') or complaint.complaint_status)
    complaint.response_code = str(body.get('responseCode') or body.get('complaintResponseCode') or '')
    complaint.response_reason = str(body.get('responseReason') or body.get('complaintResponseReason') or '')
    complaint.raw_payload = resp
    complaint.save(update_fields=['complaint_status', 'response_code', 'response_reason', 'raw_payload', 'updated_at'])
    BbpsComplaintEvent.objects.create(
        complaint=complaint,
        complaint_status=complaint.complaint_status,
        remarks=str(body.get('complaintRemarks') or ''),
        response_payload=resp,
    )
    return resp
