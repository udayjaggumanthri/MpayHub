import React, { useEffect, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';

function reportPath(params) {
  const reference = (params.get('orderId') || params.get('invoice') || '').trim();
  const search = new URLSearchParams();
  if (reference) {
    search.set('service_id', reference);
    search.set('open_receipt', '1');
  }
  const query = search.toString();
  return query ? `/reports/payin?${query}` : '/reports/payin';
}

function PaymentHandoff({ title }) {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const sent = useRef(false);
  const target = reportPath(params);

  useEffect(() => {
    if (sent.current) return;
    sent.current = true;
    navigate(target, { replace: true });
  }, [navigate, target]);

  return (
    <div className="py-16 text-center">
      <div className="mx-auto h-12 w-12 animate-spin rounded-full border-b-2 border-blue-600" />
      <h1 className="mt-4 text-lg font-semibold text-gray-900 dark:text-slate-100">{title}</h1>
      <p className="mt-1 text-sm text-gray-600 dark:text-slate-400">Opening the pay-in receipt.</p>
    </div>
  );
}

export function PaymentSuccess() {
  return <PaymentHandoff title="Payment received" />;
}

export function PaymentFailure() {
  return <PaymentHandoff title="Payment was not completed" />;
}
