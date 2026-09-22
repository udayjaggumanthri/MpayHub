import React, { useEffect, useRef, useState } from 'react';
import Card from '../../../components/common/Card';
import Button from '../../../components/common/Button';
import Input from '../../../components/common/Input';
import cmsAPI from '../services/cmsApi';
import CmsReceiptView from '../receipts/CmsReceiptView';
import { getBrowserGeo } from '../../aeps/services/mantraRd';
import { sanitizeCmsUserMessage } from '../utils/cmsUserCopy';

const CmsLaunch = () => {
  const [amount, setAmount] = useState('');
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState('');
  const [launch, setLaunch] = useState(null);
  const [latest, setLatest] = useState(null);
  const pollRef = useRef(null);

  const stopPoll = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  useEffect(() => () => stopPoll(), []);

  const refreshLatest = async () => {
    const res = await cmsAPI.transactions({ limit: 1, offset: 0 });
    if (res.success && res.data?.results?.[0]) {
      setLatest(res.data.results[0]);
    }
  };

  const startPoll = () => {
    stopPoll();
    pollRef.current = setInterval(refreshLatest, 4000);
  };

  const onLaunch = async (e) => {
    e.preventDefault();
    setBusy(true);
    setMsg('');
    setLatest(null);
    const geo = await getBrowserGeo();
    if (geo.status !== 'granted') {
      setMsg('Location is required to open CMS.');
      setBusy(false);
      return;
    }
    const res = await cmsAPI.launch({
      amount: amount || '0',
      latitude: geo.latitude,
      longitude: geo.longitude,
    });
    if (!res.success) {
      setMsg(sanitizeCmsUserMessage(res.message) || 'Launch failed');
      setBusy(false);
      return;
    }
    setLaunch(res.data);
    const opened = window.open(res.data.url, '_blank', 'noopener,noreferrer');
    if (!opened) {
      setMsg('Popup blocked. Allow popups, then use Open again.');
    } else {
      setMsg('CMS opened in a new tab. Complete the collection there — this page will refresh for results.');
      startPoll();
    }
    setBusy(false);
  };

  return (
    <div className="space-y-5">
      <header>
        <h2 className="text-xl font-bold text-slate-900 dark:text-slate-100">Launch CMS</h2>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Opens the network CMS screen in a new tab. Your CMS wallet is debited when the collection succeeds.
        </p>
      </header>

      <Card shadow="sm">
        <form onSubmit={onLaunch} className="space-y-4">
          <Input
            label="Amount (optional prefill)"
            type="number"
            min={0}
            step="0.01"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            className="max-w-[200px]"
          />
          <div className="flex flex-wrap gap-2">
            <Button type="submit" loading={busy}>
              Open CMS
            </Button>
            {launch?.url ? (
              <Button
                type="button"
                variant="secondary"
                onClick={() => window.open(launch.url, '_blank', 'noopener,noreferrer')}
              >
                Open again
              </Button>
            ) : null}
            <Button type="button" variant="secondary" onClick={refreshLatest}>
              Refresh result
            </Button>
          </div>
        </form>
        {msg ? (
          <p className="mt-4 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-800/50">
            {msg}
          </p>
        ) : null}
        {launch?.expires_at ? (
          <p className="mt-2 text-xs text-slate-400">
            Launch session expires {new Date(launch.expires_at).toLocaleString('en-IN')} · BC{' '}
            {launch.bc_login_id}
          </p>
        ) : null}
      </Card>

      {latest ? (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/45 p-3 sm:items-center sm:p-6">
          <div className="max-h-[92vh] w-full max-w-2xl overflow-y-auto rounded-2xl bg-white p-4 shadow-2xl dark:bg-slate-900 sm:p-5">
            <CmsReceiptView
              txn={latest}
              onClose={() => {
                stopPoll();
                setLatest(null);
              }}
              onRefresh={refreshLatest}
            />
          </div>
        </div>
      ) : null}
    </div>
  );
};

export default CmsLaunch;
