import React, { useEffect, useState } from 'react';
import { bbpsAPI } from '../../../services/api';
import Button from '../../common/Button';
import LoadingSpinner from '../../common/LoadingSpinner';

const CashOnlyImpactModal = ({ open, preview, loading, onConfirm, onCancel }) => {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4">
      <div className="w-full max-w-lg rounded-xl border border-slate-200 bg-white p-5 shadow-xl dark:border-slate-700 dark:bg-slate-900">
        <h3 className="text-lg font-bold text-slate-900 dark:text-slate-100">Enable cash-only partner catalog?</h3>
        <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">
          Partners will only see billers with AGT channel and Cash mode. Non-eligible billers will be auto-hidden
          (reversible when you turn cash-only off).
        </p>

        {loading ? (
          <div className="flex justify-center py-8">
            <LoadingSpinner size="sm" />
          </div>
        ) : preview ? (
          <div className="mt-4 space-y-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm dark:border-amber-900 dark:bg-amber-950/30">
            <div className="grid grid-cols-2 gap-2">
              <div>
                <span className="text-amber-800 dark:text-amber-300">MDM total</span>
                <p className="text-lg font-bold text-amber-950 dark:text-amber-200">{preview.mdm_total ?? 0}</p>
              </div>
              <div>
                <span className="text-amber-800 dark:text-amber-300">Would hide</span>
                <p className="text-lg font-bold text-amber-950 dark:text-amber-200">{preview.would_hide_count ?? 0}</p>
              </div>
            </div>
            {(preview.sample_would_hide || []).length > 0 ? (
              <div>
                <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-amber-800 dark:text-amber-300">
                  Sample billers
                </p>
                <ul className="space-y-1 text-xs text-amber-900 dark:text-amber-200">
                  {preview.sample_would_hide.map((b) => (
                    <li key={b.biller_id}>
                      {b.biller_name} <span className="font-mono text-amber-700">({b.biller_id})</span>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </div>
        ) : null}

        <div className="mt-5 flex justify-end gap-2">
          <Button variant="outline" onClick={onCancel}>
            Cancel
          </Button>
          <Button onClick={onConfirm} disabled={loading}>
            Enable cash-only
          </Button>
        </div>
      </div>
    </div>
  );
};

export default CashOnlyImpactModal;
