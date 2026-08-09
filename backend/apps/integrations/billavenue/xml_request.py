"""Build BillAvenue inner plaintext for XML API variant (encrypted body)."""

from __future__ import annotations

from xml.etree.ElementTree import Element, SubElement, fromstring, tostring


def _fill_biller_response_subtree(parent_el: Element, data: dict) -> None:
    """
    Emit BillAvenue ``billerResponse`` children including nested dicts/lists.

    The previous implementation only wrote scalar fields and **skipped** nested
    structures; BillAvenue then rejects pay with **E211 billerResponse value mismatch**
    when the echoed snapshot does not match fetch (e.g. ``additionalInfo`` inside
    ``billerResponse``).
    """
    if not isinstance(data, dict):
        return
    for raw_k, raw_v in data.items():
        k = str(raw_k)
        if raw_v is None:
            continue
        if isinstance(raw_v, dict):
            child = SubElement(parent_el, k)
            _fill_biller_response_subtree(child, raw_v)
        elif isinstance(raw_v, list):
            for item in raw_v:
                if isinstance(item, dict):
                    if any(x in item for x in ('infoName', 'info_name')):
                        row_tag = 'info'
                    elif any(x in item for x in ('paramName', 'param_name')):
                        row_tag = 'input'
                    else:
                        row_tag = 'item'
                    row_el = SubElement(parent_el, row_tag)
                    for ik, iv in item.items():
                        if isinstance(iv, dict):
                            sub = SubElement(row_el, str(ik))
                            _fill_biller_response_subtree(sub, iv)
                        elif isinstance(iv, list):
                            _fill_biller_response_subtree(row_el, {str(ik): iv})
                        else:
                            SubElement(row_el, str(ik)).text = '' if iv is None else str(iv).strip()
                else:
                    leaf = SubElement(parent_el, k)
                    leaf.text = str(item).strip()
        elif isinstance(raw_v, bool):
            SubElement(parent_el, k).text = 'true' if raw_v else 'false'
        else:
            # Emit empty-string leaves too; skipping them breaks echo vs BillAvenue fetch (E211).
            SubElement(parent_el, k).text = '' if raw_v is None else str(raw_v).strip()


def build_biller_info_plain_xml(payload: dict) -> str:
    """
    MDM biller_info inner body for /mdmRequestNew/xml.

    BillAvenue expects XML inside encRequest when the URL variant is /xml, not JSON.
    """
    root = Element('billerInfoRequest')
    agent_id = str((payload or {}).get('agentId') or '').strip()
    if agent_id:
        SubElement(root, 'agentId').text = agent_id

    bids = (payload or {}).get('billerId')
    if isinstance(bids, (list, tuple)):
        for bid in bids:
            t = str(bid or '').strip()
            if t:
                SubElement(root, 'billerId').text = t
    elif bids is not None and str(bids).strip():
        SubElement(root, 'billerId').text = str(bids).strip()

    body = tostring(root, encoding='unicode')
    return '<?xml version="1.0" encoding="UTF-8"?>' + body


def build_plan_pull_plain_xml(payload: dict) -> str:
    """Plan MDM inner body for /extPlanMDM/planMdmRequest/xml."""
    root = Element('planDetailsRequest')
    agent_id = str((payload or {}).get('agentId') or '').strip()
    if agent_id:
        SubElement(root, 'agentId').text = agent_id
    bids = (payload or {}).get('billerId')
    if isinstance(bids, (list, tuple)):
        for bid in bids:
            t = str(bid or '').strip()
            if t:
                SubElement(root, 'billerId').text = t
    elif bids is not None and str(bids).strip():
        SubElement(root, 'billerId').text = str(bids).strip()
    body = tostring(root, encoding='unicode')
    return '<?xml version="1.0" encoding="UTF-8"?>' + body


def build_bill_fetch_plain_xml(payload: dict) -> str:
    """
    billFetchRequest inner body for /extBillCntrl/billFetchRequest/xml.
    Mirrors BillAvenue PHP sample field structure.
    """
    p = payload or {}
    root = Element('billFetchRequest')

    agent_id = str(p.get('agentId') or '').strip()
    if agent_id:
        SubElement(root, 'agentId').text = agent_id

    if 'billerAdhoc' in p:
        SubElement(root, 'billerAdhoc').text = 'true' if bool(p.get('billerAdhoc')) else 'false'

    dev = p.get('agentDeviceInfo') or {}
    if isinstance(dev, dict):
        dev_node = SubElement(root, 'agentDeviceInfo')
        for k in ('ip', 'initChannel', 'mac', 'imei', 'os', 'app'):
            v = str(dev.get(k) or '').strip()
            if v:
                SubElement(dev_node, k).text = v

    customer = p.get('customerInfo') or {}
    if isinstance(customer, dict):
        cust = SubElement(root, 'customerInfo')
        for k in ('customerMobile', 'customerName', 'customerEmail', 'customerAdhaar', 'customerPan'):
            v = str(customer.get(k) or '').strip()
            if v:
                SubElement(cust, k).text = v

    biller_id = str(p.get('billerId') or '').strip()
    if biller_id:
        SubElement(root, 'billerId').text = biller_id

    input_params = p.get('inputParams') or {}
    rows = []
    if isinstance(input_params, dict):
        rows = input_params.get('input') or []
    if isinstance(rows, list):
        ip = SubElement(root, 'inputParams')
        for row in rows:
            if not isinstance(row, dict):
                continue
            name = str(row.get('paramName') or '').strip()
            value = str(row.get('paramValue') or '').strip()
            if not name:
                continue
            inp = SubElement(ip, 'input')
            SubElement(inp, 'paramName').text = name
            SubElement(inp, 'paramValue').text = value

    body = tostring(root, encoding='unicode')
    return '<?xml version="1.0" encoding="UTF-8"?>' + body


def build_bill_pay_plain_xml(payload: dict) -> str:
    """
    billPaymentRequest inner body for /extBillPayCntrl/billPayRequest/xml.

    BillAvenue UAT validates element order and expects a root-level ``paymentRefId``
    matching the prior bill-fetch correlation (same value as ``requestId`` / PaymentRefId in paymentInfo).
    """
    p = payload or {}
    root = Element('billPaymentRequest')

    pay_ref = str(p.get('paymentRefId') or p.get('requestId') or '').strip()
    if pay_ref:
        SubElement(root, 'paymentRefId').text = pay_ref

    agent_id = str(p.get('agentId') or '').strip()
    if agent_id:
        SubElement(root, 'agentId').text = agent_id

    if 'billerAdhoc' in p:
        SubElement(root, 'billerAdhoc').text = 'true' if bool(p.get('billerAdhoc')) else 'false'

    dev = p.get('agentDeviceInfo') or {}
    if isinstance(dev, dict):
        dev_node = SubElement(root, 'agentDeviceInfo')
        for k in ('ip', 'initChannel', 'mac', 'imei', 'os', 'app'):
            v = str(dev.get(k) or '').strip()
            if v:
                SubElement(dev_node, k).text = v

    customer = p.get('customerInfo') or {}
    if isinstance(customer, dict):
        cust = SubElement(root, 'customerInfo')
        for k in ('customerMobile', 'customerName', 'customerEmail', 'customerAdhaar', 'customerPan'):
            v = str(customer.get(k) or '').strip()
            if v:
                SubElement(cust, k).text = v

    biller_id = str(p.get('billerId') or '').strip()
    if biller_id:
        SubElement(root, 'billerId').text = biller_id

    plan_id = str(p.get('planId') or '').strip()
    if plan_id:
        SubElement(root, 'planId').text = plan_id

    input_params = p.get('inputParams') or {}
    rows = input_params.get('input') if isinstance(input_params, dict) else []
    if isinstance(rows, list) and rows:
        ip = SubElement(root, 'inputParams')
        for row in rows:
            if not isinstance(row, dict):
                continue
            name = str(row.get('paramName') or '').strip()
            value = str(row.get('paramValue') or '').strip()
            if not name:
                continue
            inp = SubElement(ip, 'input')
            SubElement(inp, 'paramName').text = name
            SubElement(inp, 'paramValue').text = value

    biller_response = p.get('billerResponse') or {}
    br_xml = str(p.get('billerResponseXml') or '').strip()
    if br_xml:
        try:
            frag_el = fromstring(br_xml)
            root.append(frag_el)
        except Exception:
            if isinstance(biller_response, dict) and biller_response:
                br = SubElement(root, 'billerResponse')
                _fill_biller_response_subtree(br, biller_response)
    elif isinstance(biller_response, dict) and biller_response:
        br = SubElement(root, 'billerResponse')
        _fill_biller_response_subtree(br, biller_response)

    ai_xml = str(p.get('additionalInfoXml') or '').strip()
    additional_info = p.get('additionalInfo') or {}
    infos = additional_info.get('info') if isinstance(additional_info, dict) else []
    if ai_xml:
        try:
            root.append(fromstring(ai_xml))
        except Exception:
            if isinstance(infos, list) and infos:
                ai = SubElement(root, 'additionalInfo')
                for row in infos:
                    if not isinstance(row, dict):
                        continue
                    name = str(row.get('infoName') or '').strip()
                    if not name:
                        continue
                    # Preserve exact infoValue text from fetch (no strip / falsy coalescing) — E212.
                    raw_val = row.get('infoValue') if 'infoValue' in row else row.get('info_value')
                    i = SubElement(ai, 'info')
                    SubElement(i, 'infoName').text = name
                    SubElement(i, 'infoValue').text = '' if raw_val is None else str(raw_val)
    elif isinstance(infos, list) and infos:
        ai = SubElement(root, 'additionalInfo')
        for row in infos:
            if not isinstance(row, dict):
                continue
            name = str(row.get('infoName') or '').strip()
            if not name:
                continue
            raw_val = row.get('infoValue') if 'infoValue' in row else row.get('info_value')
            i = SubElement(ai, 'info')
            SubElement(i, 'infoName').text = name
            SubElement(i, 'infoValue').text = '' if raw_val is None else str(raw_val)

    amount_info = p.get('amountInfo') or {}
    if isinstance(amount_info, dict) and amount_info:
        am = SubElement(root, 'amountInfo')
        for k in ('amount', 'currency', 'custConvFee', 'CCF1'):
            v = str(amount_info.get(k) or '').strip()
            if v:
                SubElement(am, k).text = v

    payment_method = p.get('paymentMethod') or {}
    if isinstance(payment_method, dict) and payment_method:
        pm = SubElement(root, 'paymentMethod')
        for k in ('paymentMode', 'quickPay', 'splitPay'):
            v = str(payment_method.get(k) or '').strip()
            if v:
                SubElement(pm, k).text = v

    payment_info = p.get('paymentInfo') or {}
    p_infos = payment_info.get('info') if isinstance(payment_info, dict) else []
    if isinstance(p_infos, dict):
        p_infos = [p_infos]
    if isinstance(p_infos, list) and p_infos:
        pi = SubElement(root, 'paymentInfo')
        for row in p_infos:
            if not isinstance(row, dict):
                continue
            name = str(row.get('infoName') or '').strip()
            value = str(row.get('infoValue') or '').strip()
            if not name:
                continue
            i = SubElement(pi, 'info')
            SubElement(i, 'infoName').text = name
            SubElement(i, 'infoValue').text = value

    body = tostring(root, encoding='unicode')
    return '<?xml version="1.0" encoding="UTF-8"?>' + body


def build_complaint_register_plain_xml(payload: dict) -> str:
    """
    Inner plaintext for ``/billpay/extComplaints/register/xml`` per BillAvenue integration samples.

    BillAvenue documents query-string envelope fields with XML inside ``encRequest`` (not JSON on /json
    for this flow on many UAT stacks — JSON + /json can return 205 FAILURE).

    Expected root: ``complaintRegistrationReq`` with ``txnRefId``, ``complaintDesc``, ``complaintDisposition``
    (and optional ``complaintType``, ``agentId``, ``billerId``, ``paymentRefId``). Disposition strings must
    match NPCI/BillAvenue’s official disposition list (same strings as the partner portal / API samples).
    """
    p = payload or {}
    root = Element('complaintRegistrationReq')
    tid = str(p.get('txnRefId') or '').strip()
    if tid:
        SubElement(root, 'txnRefId').text = tid
    desc = str(p.get('complaintDesc') or p.get('complainDesc') or p.get('complaintDescription') or '').strip()
    if desc:
        SubElement(root, 'complaintDesc').text = desc
    disp = str(p.get('complaintDisposition') or '').strip()
    if disp:
        SubElement(root, 'complaintDisposition').text = disp
    ctype = str(p.get('complaintType') or '').strip()
    if ctype:
        SubElement(root, 'complaintType').text = ctype
    for tag in ('agentId', 'billerId', 'paymentRefId'):
        v = str(p.get(tag) or '').strip()
        if v:
            SubElement(root, tag).text = v
    body = tostring(root, encoding='unicode')
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' + body


def build_complaint_track_plain_xml(payload: dict) -> str:
    """Inner plaintext for ``/billpay/extComplaints/track/xml`` (complaintId in request body)."""
    p = payload or {}
    root = Element('complaintTrackingReq')
    cid = str(p.get('complaintId') or '').strip()
    if cid:
        SubElement(root, 'complaintId').text = cid
    body = tostring(root, encoding='unicode')
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' + body
