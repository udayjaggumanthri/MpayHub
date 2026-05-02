"""Build BillAvenue inner plaintext for XML API variant (encrypted body)."""

from __future__ import annotations

from xml.etree.ElementTree import Element, SubElement, tostring


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
    if isinstance(biller_response, dict) and biller_response:
        br = SubElement(root, 'billerResponse')
        for k, v in biller_response.items():
            if isinstance(v, (dict, list, tuple)):
                continue
            sv = str(v or '').strip()
            if sv:
                SubElement(br, str(k)).text = sv

    additional_info = p.get('additionalInfo') or {}
    infos = additional_info.get('info') if isinstance(additional_info, dict) else []
    if isinstance(infos, list) and infos:
        ai = SubElement(root, 'additionalInfo')
        for row in infos:
            if not isinstance(row, dict):
                continue
            name = str(row.get('infoName') or '').strip()
            value = str(row.get('infoValue') or '').strip()
            if not name:
                continue
            i = SubElement(ai, 'info')
            SubElement(i, 'infoName').text = name
            SubElement(i, 'infoValue').text = value

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
