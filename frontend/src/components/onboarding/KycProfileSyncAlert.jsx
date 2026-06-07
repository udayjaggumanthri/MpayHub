import React, { useCallback, useEffect, useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { authAPI } from '../../services/api';
import KycProfileSyncModal from './KycProfileSyncModal';

/**
 * Amber banner + review modal when verified KYC differs from the user profile.
 */
const KycProfileSyncAlert = ({ fetchOnMount = true, className = '' }) => {
  const { user, refreshUser } = useAuth();
  const [profileSyncOffer, setProfileSyncOffer] = useState(null);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [statusMessage, setStatusMessage] = useState('');

  useEffect(() => {
    const pending = user?.profile_sync_pending?.[0];
    if (pending?.sync_token) {
      setProfileSyncOffer(pending);
    }
  }, [user]);

  useEffect(() => {
    if (!fetchOnMount) return undefined;
    let active = true;
    const loadPending = async () => {
      const res = await authAPI.getProfileSyncPending();
      if (!active) return;
      if (res.success && res.data?.pending?.length) {
        setProfileSyncOffer(res.data.pending[0]);
      }
    };
    loadPending();
    return () => {
      active = false;
    };
  }, [fetchOnMount]);

  const handleConfirm = useCallback(async () => {
    if (!profileSyncOffer?.sync_token) return;
    setLoading(true);
    setStatusMessage('');
    try {
      const res = await authAPI.confirmProfileSync(profileSyncOffer.sync_token);
      if (res.success) {
        await refreshUser?.();
        setProfileSyncOffer(null);
        setOpen(false);
        setStatusMessage('Profile updated from verified KYC records.');
      } else {
        setStatusMessage(res.message || 'Could not update profile.');
      }
    } finally {
      setLoading(false);
    }
  }, [profileSyncOffer, refreshUser]);

  const handleDecline = useCallback(async () => {
    if (!profileSyncOffer?.sync_token) return { warning: '' };
    setLoading(true);
    try {
      const res = await authAPI.declineProfileSync(profileSyncOffer.sync_token);
      setProfileSyncOffer(null);
      setOpen(false);
      const message = res.message || 'Profile was not updated.';
      setStatusMessage(message);
      return { warning: message };
    } finally {
      setLoading(false);
    }
  }, [profileSyncOffer]);

  if (!profileSyncOffer?.sync_token && !statusMessage) return null;

  return (
    <>
      {profileSyncOffer?.sync_token ? (
        <div
          className={`rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 ${className}`.trim()}
        >
          <p className="text-sm text-amber-900">
            Verified KYC records differ from your profile. Review and choose whether to update your profile.
          </p>
          <button
            type="button"
            onClick={() => setOpen(true)}
            className="shrink-0 px-4 py-2 text-sm font-semibold rounded-lg bg-amber-600 text-white hover:bg-amber-700"
          >
            Review sync
          </button>
        </div>
      ) : null}

      {statusMessage ? (
        <p
          className={`text-sm text-slate-700 bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 ${className}`.trim()}
        >
          {statusMessage}
        </p>
      ) : null}

      <KycProfileSyncModal
        open={open}
        profileSync={profileSyncOffer}
        loading={loading}
        onConfirm={handleConfirm}
        onDecline={handleDecline}
        onClose={() => !loading && setOpen(false)}
      />
    </>
  );
};

export default KycProfileSyncAlert;
