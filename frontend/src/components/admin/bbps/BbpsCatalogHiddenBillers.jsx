import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { bbpsAPI } from '../../../services/api';
import Badge from '../../common/Badge';
import BbpsAdminTable, { formatHiddenReason } from './BbpsAdminTable';
import BbpsEnvPageShell from './BbpsEnvPageShell';

const BbpsCatalogHiddenBillers = () => {
  const [summary, setSummary] = useState(null);
  const [rows, setRows] = useState([]);
  const [pagination, setPagination] = useState(null);
  const [loading, setLoading] = useState(true);
  const [qInput, setQInput] = useState('');
  const [q, setQ] = useState('');
  const [reason, setReason] = useState('');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const debounceRef = useRef(null);

  const loadSummary = useCallback(async () => {
    const res = await bbpsAPI.getCatalogVisibilitySummary();
    if (res.success) setSummary(res.data);
  }, []);

  const loadRows = useCallback(async () => {
    setLoading(true);
    const res = await bbpsAPI.listCatalogHiddenBillers({
      page,
      page_size: pageSize,
      q: q || undefined,
      reason: reason || undefined,
      environment: summary?.environment,
    });
    if (res.success) {
      setRows(res.data?.billers || []);
      setPagination(res.data?.pagination || null);
    }
    setLoading(false);
  }, [page, pageSize, q, reason, summary?.environment]);

  useEffect(() => {
    loadSummary();
  }, [loadSummary]);

  useEffect(() => {
    if (summary) loadRows();
  }, [summary, loadRows]);

  const onSearchChange = (value) => {
    setQInput(value);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setQ(value.trim());
      setPage(1);
    }, 400);
  };

  const columns = [
    {
      key: 'biller',
      label: 'Biller',
      render: (row) => (
        <div>
          <div className="font-medium text-slate-900 dark:text-slate-100">{row.biller_name}</div>
          <div className="font-mono text-xs text-slate-500">{row.biller_id}</div>
        </div>
      ),
    },
    { key: 'biller_category', label: 'Category' },
    {
      key: 'hold',
      label: 'Hold',
      render: (row) => (
        <Badge variant={row.local_visibility_hold === 'admin' ? 'warning' : 'default'} size="sm">
          {row.local_visibility_hold || '—'}
        </Badge>
      ),
    },
    {
      key: 'channels',
      label: 'Channels',
      render: (row) => <span className="text-xs">{row.payment_channels_summary}</span>,
    },
    {
      key: 'modes',
      label: 'Modes',
      render: (row) => <span className="text-xs">{row.payment_modes_summary}</span>,
    },
    {
      key: 'reasons',
      label: 'Reasons',
      render: (row) => (
        <div className="flex flex-wrap gap-1">
          {(row.hidden_reasons || []).map((r) => (
            <Badge key={r} variant="default" size="sm">
              {formatHiddenReason(r)}
            </Badge>
          ))}
        </div>
      ),
    },
  ];

  return (
    <BbpsEnvPageShell
      environment={summary?.environment}
      title="Hidden billers"
      subtitle="Billers excluded from the partner catalog (cash-only policy, admin disable, or eligibility)."
      breadcrumbs={[
        { label: 'BBPS Console', to: '/admin/bbps' },
        { label: 'Catalog visibility', to: '/admin/bbps/catalog-visibility' },
        { label: 'Hidden billers' },
      ]}
    >
      <BbpsAdminTable
        rows={rows}
        columns={columns}
        loading={loading}
        pagination={pagination}
        onPageChange={setPage}
        pageSize={pageSize}
        onPageSizeChange={(size) => {
          setPageSize(size);
          setPage(1);
        }}
        qInput={qInput}
        onSearchChange={onSearchChange}
        filters={
          <select
            value={reason}
            onChange={(e) => {
              setReason(e.target.value);
              setPage(1);
            }}
            className="rounded-lg border border-slate-200 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-950"
          >
            <option value="">All reasons</option>
            <option value="cash_only">Cash-only hold</option>
            <option value="admin">Admin hold</option>
            <option value="no_agt_channel">No AGT</option>
            <option value="no_cash_mode">No Cash</option>
          </select>
        }
        emptyMessage="No hidden billers for the current filters."
      />
      <p className="text-xs text-slate-500">
        <Link to="/admin/bbps/partner-catalog" className="text-blue-600 hover:underline dark:text-blue-400">
          Partner catalog
        </Link>{' '}
        shows only billers partners can pay today.
      </p>
    </BbpsEnvPageShell>
  );
};

export default BbpsCatalogHiddenBillers;
