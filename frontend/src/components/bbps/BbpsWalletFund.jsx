import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { walletsAPI } from '../../services/api';
import { useWallet } from '../../context/WalletContext';
import Button from '../common/Button';
import Card from '../common/Card';

const BbpsWalletFund = () => {
  const navigate = useNavigate();
  const { loadWallets, wallets } = useWallet();
  const [amount, setAmount] = useState('');
  const [mpin, setMpin] = useState('');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState(null);
  const [error, setError] = useState(null);

  const onSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setMessage(null);
    if (!amount || Number(amount) <= 0) {
      setError('Enter a valid amount');
      return;
    }
    if (!/^\d{6}$/.test(mpin)) {
      setError('MPIN must be 6 digits');
      return;
    }
    setLoading(true);
    try {
      const res = await walletsAPI.transferMainToBbps({ amount: String(amount), mpin });
      if (res.success) {
        setMessage(`Transferred to BBPS wallet. Ref: ${res.data?.service_id || '—'}`);
        setAmount('');
        setMpin('');
        await loadWallets();
      } else {
        setError(res.message || 'Transfer failed');
      }
    } catch (err) {
      setError(err.message || 'Transfer failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-lg mx-auto space-y-6 px-4 py-6">
      <Card title="Fund BBPS wallet" padding="lg">
        <p className="text-sm text-gray-600 mb-4">
          Move money from your <strong>main</strong> wallet to your <strong>BBPS</strong> wallet. Bill
          payments debit only the BBPS wallet.
        </p>
        <div className="grid grid-cols-2 gap-3 mb-4 text-sm">
          <div className="rounded-lg border border-gray-200 p-3">
            <p className="text-gray-500">Main balance</p>
            <p className="font-semibold text-gray-900">
              Rs. {Number(wallets?.main ?? 0).toFixed(2)}
            </p>
          </div>
          <div className="rounded-lg border border-gray-200 p-3">
            <p className="text-gray-500">BBPS balance</p>
            <p className="font-semibold text-gray-900">
              Rs. {Number(wallets?.bbps ?? 0).toFixed(2)}
            </p>
          </div>
        </div>
        <form onSubmit={onSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Amount (Rs.)</label>
            <input
              type="number"
              min="0.01"
              step="0.01"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              className="w-full px-4 py-2.5 border border-gray-300 rounded-lg"
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">MPIN</label>
            <input
              type="password"
              inputMode="numeric"
              maxLength={6}
              value={mpin}
              onChange={(e) => setMpin(e.target.value.replace(/\D/g, '').slice(0, 6))}
              className="w-full px-4 py-2.5 border border-gray-300 rounded-lg tracking-widest"
              placeholder="******"
              required
            />
          </div>
          {error && <p className="text-sm text-red-600">{error}</p>}
          {message && <p className="text-sm text-green-700">{message}</p>}
          <div className="flex flex-wrap gap-3">
            <Button type="submit" disabled={loading}>
              {loading ? 'Processing…' : 'Transfer'}
            </Button>
            <Button type="button" variant="secondary" onClick={() => navigate('/bill-payments/pay')}>
              Pay bills
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
};

export default BbpsWalletFund;
