import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { billAvenueAdminAPI } from '../../../services/api';
import Badge from '../../common/Badge';
import BbpsAdminTable from './BbpsAdminTable';
import BbpsEnvPageShell from './BbpsEnvPageShell';

const BbpsPartnerCatalog = ({ embedded = false }) => {
  const [liveMode, setLiveMode] = useState('');
  const [rows, setRows] = useState([]);
  const [pagination, setPagination] = useState(null);
  const [loading, setLoading] = useState(true);
  const [cashOnly, setCashOnly] = useState(false);
  const [qInput, setQInput] = useState('');
  const [q, setQ] = useState('');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const debounceRef = useRef(null);

  const load = useCallback(async () => {
    setLoading(true);
    const res = await billAvenueAdminAPI.listBillerMaster({
      view: 'partner',
      page,
      page_size: pageSize,
      q: q || undefined,
    });
    if (res.success) {
      setRows(res.data?.billers || []);
      setPagination(res.data?.pagination || null);
      setLiveMode(res.data?.live_mode || '');
      setCashOnly(!!res.data?.cash_only_for_users);
    }
    setLoading(false);
  }, [page, pageSize, q]);

  useEffect(() => {
    load();
  }, [load]);

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
          <div className="font-medium">{row.biller_name}</div>
          <div className="font-mono text-xs text-slate-500">{row.biller_id}</div>
        </div>
      ),
    },
    { key: 'biller_category', label: 'Category' },
    {
      key: 'status',
      label: 'Status',
      render: (row) => <Badge variant="success" size="sm">{row.biller_status || 'ACTIVE'}</Badge>,
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
      key: 'actions',
      label: '',
      render: (row) => (
        <Link
          to={`/admin/bbps-governance/biller/${row.id}`}
          className="text-sm font-medium text-blue-600 hover:underline dark:text-blue-400"
        >
          Details
        </Link>
      ),
    },
  ];

  const body = (
    <>
      {!embedded ? (
        <div className="rounded-lg border border-blue-200 bg-blue-50 px-4 py-2 text-sm text-blue-900 dark:border-blue-900 dark:bg-blue-950/30 dark:text-blue-200">
          This list mirrors what partners see. To change visibility rules, open the{' '}
          <Link to="/admin/bbps/catalog?tab=visibility" className="font-semibold underline">
            Visibility
          </Link>{' '}
          tab.
        </div>
      ) : null}

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
        emptyMessage="No billers are visible to partners with the current settings."
      />
    </>
  );

  if (embedded) return <div className="space-y-4">{body}</div>;

  return (
    <BbpsEnvPageShell
      environment={liveMode}
      title="Partner catalog"
      subtitle="Read-only view of billers visible to partners on the live environment."
      breadcrumbs={[{ label: 'BBPS Console', to: '/admin/bbps' }, { label: 'Partner catalog' }]}
      actions={
        cashOnly ? (
          <Badge variant="success" size="sm">
            Cash-only ON
          </Badge>
        ) : (
          <Badge variant="default" size="sm">
            Standard mode
          </Badge>
        )
      }
    >
      {body}
    </BbpsEnvPageShell>
  );
};

export default BbpsPartnerCatalog;
