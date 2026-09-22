import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import Card from '../../../components/common/Card';
import Button from '../../../components/common/Button';
import { useAuth } from '../../../context/AuthContext';
import { isAdminUser } from '../../../utils/rolePermissions';
import cmsAPI from '../services/cmsApi';
import { formatCmsAmount } from '../utils/cmsUserCopy';

const CmsOverview = () => {
  const { user } = useAuth();
  const isAdmin = isAdminUser(user);
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    cmsAPI.meStatus().then((res) => {
      if (res.success) setStatus(res.data);
      setLoading(false);
    });
  }, []);

  if (loading) {
    return <p className="text-sm text-slate-500">Loading…</p>;
  }

  const next = status?.next_action;
  let title = 'Ready to collect cash';
  let body = 'Fund your CMS wallet if needed, then open CMS to complete a collection.';
  let cta = { to: '/cms/launch', label: 'Open CMS launch' };

  if (isAdmin || next === 'admin_ops') {
    title = 'CMS administration';
    body = 'Configure the Uber CMS provider, enable agents, and review audit logs. Admins do not run collections here.';
    cta = { to: '/admin/cms/provider', label: 'Provider settings' };
  } else if (next === 'request_access') {
    title = 'CMS access required';
    body = 'Ask your Admin to enable CMS for your account (same assignment model as AEPS).';
    cta = null;
  } else if (next === 'await_agent' || next === 'await_provider') {
    title = 'Almost ready';
    body =
      next === 'await_provider'
        ? 'CMS provider is not configured yet. Contact Admin.'
        : 'Your CMS agent profile is not active yet. Contact Admin.';
    cta = null;
  }

  return (
    <div className="space-y-5">
      <header>
        <h2 className="text-xl font-bold text-slate-900 dark:text-slate-100">Cash collection (CMS)</h2>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Collect cash via the network CMS screen. Your CMS wallet funds the debit.
        </p>
      </header>

      <Card shadow="sm">
        <h3 className="text-lg font-bold text-slate-900 dark:text-slate-100">{title}</h3>
        <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">{body}</p>
        {cta ? (
          <Link to={cta.to} className="mt-4 inline-block">
            <Button>{cta.label}</Button>
          </Link>
        ) : null}
      </Card>

      <div className="grid gap-3 sm:grid-cols-3">
        <Card shadow="sm">
          <p className="text-[10px] font-semibold uppercase text-slate-400">Available</p>
          <p className="mt-1 text-2xl font-bold tabular-nums">{formatCmsAmount(status?.wallet?.available)}</p>
        </Card>
        <Card shadow="sm">
          <p className="text-[10px] font-semibold uppercase text-slate-400">Held</p>
          <p className="mt-1 text-2xl font-bold tabular-nums">{formatCmsAmount(status?.wallet?.held_balance)}</p>
        </Card>
        <Card shadow="sm">
          <p className="text-[10px] font-semibold uppercase text-slate-400">Agent</p>
          <p className="mt-1 font-mono text-sm font-semibold">{status?.agent?.bc_login_id || '—'}</p>
          <p className="text-xs capitalize text-slate-500">{status?.agent?.status || 'not set'}</p>
        </Card>
      </div>

      <div className="flex flex-wrap gap-2">
        <Link to="/cms/wallet">
          <Button size="sm" variant="secondary">
            Wallet
          </Button>
        </Link>
        <Link to="/cms/reports">
          <Button size="sm" variant="secondary">
            View reports
          </Button>
        </Link>
        {isAdmin ? (
          <Link to="/admin/cms/agents">
            <Button size="sm" variant="secondary">
              Manage agents
            </Button>
          </Link>
        ) : null}
      </div>
    </div>
  );
};

export default CmsOverview;
