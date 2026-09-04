"""
Masked BillAvenue credential health + live biller_info probe.

  python manage.py billavenue_health --env prod
  python manage.py billavenue_health --env uat --no-probe
"""

from __future__ import annotations

import json
import re
from html import unescape

from django.core.management.base import BaseCommand, CommandError

from apps.bbps.models import BbpsApiAuditLog
from apps.integrations.billavenue.client import BillAvenueClient
from apps.integrations.billavenue.errors import BillAvenueAuthError, BillAvenueClientError, BillAvenueEntitlementError
from apps.integrations.billavenue.registry import get_billavenue_config_for_mode, normalize_billavenue_mode
from apps.integrations.models import BillAvenueAgentProfile, BillAvenueConfig


def _mask_tail(value: str, keep: int = 4) -> str:
    s = str(value or '')
    if not s:
        return '(empty)'
    if len(s) <= keep:
        return '*' * len(s)
    return f"{'*' * (len(s) - keep)}{s[-keep:]}"


def _strip_html(text: str, limit: int = 400) -> str:
    raw = unescape(str(text or ''))
    raw = re.sub(r'<[^>]+>', ' ', raw)
    raw = re.sub(r'\s+', ' ', raw).strip()
    return raw[:limit]


def _outbound_ip() -> str:
    try:
        import urllib.request

        with urllib.request.urlopen('https://api.ipify.org', timeout=5) as resp:
            return resp.read().decode('utf-8').strip()
    except Exception as exc:
        return f'(unavailable: {exc})'


def _latest_audit_raw(request_id: str) -> str:
    if not request_id:
        return ''
    row = (
        BbpsApiAuditLog.objects.filter(request_id=request_id, endpoint_name='biller_info')
        .order_by('-created_at')
        .first()
    )
    if not row:
        return ''
    meta = row.response_meta if isinstance(row.response_meta, dict) else {}
    norm = meta.get('normalized') if isinstance(meta.get('normalized'), dict) else {}
    return _strip_html(str(norm.get('raw') or row.error_message or ''))


class Command(BaseCommand):
    help = 'Report masked BillAvenue config health and optionally probe biller_info (MDM).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--env',
            default='prod',
            choices=['prod', 'uat'],
            help='BillAvenue mode to inspect (default: prod).',
        )
        parser.add_argument(
            '--no-probe',
            action='store_true',
            help='Skip live biller_info call (config/decrypt/agents/audit only).',
        )
        parser.add_argument(
            '--audit-limit',
            type=int,
            default=5,
            help='How many recent biller_info audit rows to show (default: 5).',
        )

    def handle(self, *args, **options):
        env = normalize_billavenue_mode(options['env'])
        do_probe = not options['no_probe']
        audit_limit = max(1, min(int(options['audit_limit'] or 5), 50))

        outbound = _outbound_ip()
        self.stdout.write(self.style.MIGRATE_HEADING(f'BillAvenue health — env={env}'))
        self.stdout.write(f'Outbound IP: {outbound}')
        self.stdout.write('')

        cfg = get_billavenue_config_for_mode(env, require_enabled=False)
        if cfg is None:
            # Fall back to any row for that mode (including disabled) for diagnostics.
            cfg = BillAvenueConfig.objects.filter(mode=env, is_deleted=False).order_by('-is_active', '-updated_at').first()
        if cfg is None:
            raise CommandError(f'No BillAvenueConfig row for mode={env}')

        wk = cfg.get_working_key()
        iv = cfg.get_iv()
        wk_ok = bool(wk and len(wk) >= 16)
        report = {
            'id': cfg.id,
            'mode': cfg.mode,
            'enabled': bool(cfg.enabled),
            'is_active': bool(cfg.is_active),
            'base_url': cfg.base_url,
            'api_format': getattr(cfg, 'api_format', ''),
            'request_version': getattr(cfg, 'request_version', ''),
            'crypto_key_derivation': getattr(cfg, 'crypto_key_derivation', ''),
            'enc_request_encoding': getattr(cfg, 'enc_request_encoding', ''),
            'institute_id': cfg.institute_id,
            'access_code_len': len(cfg.access_code or ''),
            'access_code_tail': _mask_tail(cfg.access_code, 4),
            'working_key_decrypt_ok': wk_ok,
            'working_key_len': len(wk or ''),
            'iv_decrypt_len': len(iv or ''),
            'iv_note': '(empty → PHP default IV at encrypt time)' if not iv else 'present',
            'updated_at': str(cfg.updated_at),
        }
        self.stdout.write('Config:')
        self.stdout.write(json.dumps(report, indent=2))
        if not wk_ok:
            self.stdout.write(
                self.style.ERROR(
                    'Working Key decrypt FAILED or too short. Check INTEGRATION_SECRET_KEY matches the key used when secrets were saved.'
                )
            )
        else:
            self.stdout.write(self.style.SUCCESS('Working Key decrypt: OK'))

        agents = list(
            BillAvenueAgentProfile.objects.filter(config=cfg, enabled=True, is_deleted=False).order_by('name', 'id')
        )
        self.stdout.write('')
        self.stdout.write('Enabled agents (sync order):')
        if not agents:
            self.stdout.write('  (none)')
        for a in agents:
            self.stdout.write(f'  id={a.id} name={a.name!r} agent_id={a.agent_id}')

        self.stdout.write('')
        self.stdout.write(f'Recent biller_info audits (last {audit_limit}):')
        audits = list(
            BbpsApiAuditLog.objects.filter(endpoint_name='biller_info').order_by('-created_at')[:audit_limit]
        )
        if not audits:
            self.stdout.write('  (none)')
        for row in audits:
            raw = ''
            meta = row.response_meta if isinstance(row.response_meta, dict) else {}
            norm = meta.get('normalized') if isinstance(meta.get('normalized'), dict) else {}
            raw = _strip_html(str(norm.get('raw') or row.error_message or ''), 180)
            self.stdout.write(
                f'  {row.created_at.isoformat()} requestId={row.request_id} '
                f'status={row.status_code} success={row.success} raw={raw!r}'
            )

        probe_result = {
            'skipped': not do_probe,
            'ok': False,
            'billavenue_request_id': '',
            'error': '',
            'ba_raw_denial': '',
            'agent_id_used': '',
        }
        if do_probe:
            self.stdout.write('')
            self.stdout.write(self.style.MIGRATE_HEADING('Live biller_info probe'))
            if not cfg.enabled:
                self.stdout.write(self.style.WARNING('Config enabled=False — probe may still run against this row.'))
            if not wk_ok:
                raise CommandError('Refusing live probe: Working Key is not decryptable.')
            client = BillAvenueClient(cfg)
            payload = {}
            if agents:
                payload['agentId'] = agents[0].agent_id
                probe_result['agent_id_used'] = agents[0].agent_id
            try:
                result = client.biller_info(payload)
                probe_result['ok'] = True
                probe_result['billavenue_request_id'] = getattr(result, 'request_id', '') or ''
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Probe OK requestId={probe_result["billavenue_request_id"]} '
                        f'response_code={getattr(result, "response_code", "")}'
                    )
                )
            except (BillAvenueAuthError, BillAvenueEntitlementError, BillAvenueClientError) as exc:
                rid = str(getattr(exc, 'billavenue_request_id', '') or '')
                probe_result['billavenue_request_id'] = rid
                probe_result['error'] = str(exc)
                probe_result['ba_raw_denial'] = _latest_audit_raw(rid)
                self.stdout.write(self.style.ERROR(f'Probe FAILED: {exc}'))
                if rid:
                    self.stdout.write(f'BillAvenue requestId: {rid}')
                if probe_result['ba_raw_denial']:
                    self.stdout.write(f'BA raw denial: {probe_result["ba_raw_denial"]}')
            except Exception as exc:
                probe_result['error'] = str(exc)
                self.stdout.write(self.style.ERROR(f'Probe unexpected error: {exc}'))

        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING('BillAvenue support packet'))
        packet = {
            'outbound_ip': outbound,
            'environment': env,
            'institute_id': cfg.institute_id,
            'access_code_tail': _mask_tail(cfg.access_code, 4),
            'agent_id': probe_result.get('agent_id_used') or (agents[0].agent_id if agents else ''),
            'endpoint': f"billpay/extMdmCntrl/mdmRequestNew/{getattr(cfg, 'api_format', 'xml') or 'xml'}",
            'base_url': cfg.base_url,
            'working_key_decrypt_ok': wk_ok,
            'billavenue_request_id': probe_result.get('billavenue_request_id') or '',
            'ba_raw_denial': probe_result.get('ba_raw_denial') or '',
            'probe_error': probe_result.get('error') or '',
            'ask_billavenue': (
                'Please confirm MDM (biller_info / mdmRequestNew) entitlement and IP whitelist '
                'for this institute/agent on the outbound IP above (MDM is separate from payment/fetch).'
            ),
        }
        self.stdout.write(json.dumps(packet, indent=2))
