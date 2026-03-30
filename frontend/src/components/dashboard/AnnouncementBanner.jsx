import React, { useState, useEffect, useCallback, useRef } from 'react';
import { FiX } from 'react-icons/fi';
import { FaCircleExclamation } from 'react-icons/fa6';
import { useAuth } from '../../context/AuthContext';
import { adminAPI } from '../../services/api';
import {
  flattenAnnouncementsPayload,
  mapAnnouncementForConsumer,
  markAnnouncementDismissedInClient,
  SESSION_POST_MPIN_ANNOUNCE,
  LS_DASHBOARD_ANN_DAY,
  EVENT_OPEN_ANNOUNCEMENT_MODAL,
  sortAnnouncementsNewestFirst,
} from '../../utils/announcements';

/**
 * High-priority announcement modal after MPIN / first dashboard visit of the day.
 * Queues multiple unread "high" items (newest first). Listens for EVENT_OPEN_ANNOUNCEMENT_MODAL
 * for "Show again" from the notification bell.
 */
const AnnouncementBanner = () => {
  const { user, mpinVerified } = useAuth();
  const [showBanner, setShowBanner] = useState(false);
  const [modalQueue, setModalQueue] = useState([]);
  const [queueIndex, setQueueIndex] = useState(0);
  const [source, setSource] = useState('auto'); // 'auto' | 'manual'

  const announcement = modalQueue[queueIndex] ?? null;
  const queueLength = modalQueue.length;
  const queuePosition = queueLength > 0 ? queueIndex + 1 : 0;

  const openQueue = useCallback((items, from) => {
    const sorted = sortAnnouncementsNewestFirst(items);
    if (!sorted.length) return;
    setSource(from);
    setModalQueue(sorted);
    setQueueIndex(0);
    setShowBanner(true);
  }, []);

  const closeAll = useCallback(() => {
    setShowBanner(false);
    setModalQueue([]);
    setQueueIndex(0);
    setSource('auto');
  }, []);

  const advanceOrClose = useCallback(() => {
    if (announcement?.id != null) {
      markAnnouncementDismissedInClient(announcement.id);
    }
    if (queueIndex < modalQueue.length - 1) {
      setQueueIndex((i) => i + 1);
    } else {
      closeAll();
    }
  }, [announcement, queueIndex, modalQueue.length, closeAll]);

  useEffect(() => {
    if (!user || !mpinVerified) return undefined;

    const timer = window.setTimeout(() => {
      const today = new Date().toDateString();

      const postMpin = sessionStorage.getItem(SESSION_POST_MPIN_ANNOUNCE) === '1';
      if (postMpin) {
        sessionStorage.removeItem(SESSION_POST_MPIN_ANNOUNCE);
      }

      const dailyAlreadyHandled = localStorage.getItem(LS_DASHBOARD_ANN_DAY) === today;
      const shouldFetch = postMpin || !dailyAlreadyHandled;

      if (!shouldFetch) return;

      (async () => {
        try {
          const result = await adminAPI.listAnnouncements({ page_size: 100 });
          localStorage.setItem(LS_DASHBOARD_ANN_DAY, today);

          if (!result.success) return;

          const list = flattenAnnouncementsPayload(result.data).map(mapAnnouncementForConsumer);
          const highUnread = list.filter(
            (a) => a.isActive && a.priority === 'high' && !a.read
          );
          if (highUnread.length) {
            openQueue(highUnread, 'auto');
          }
        } catch {
          localStorage.setItem(LS_DASHBOARD_ANN_DAY, today);
        }
      })();
    }, 0);

    return () => window.clearTimeout(timer);
  }, [user, mpinVerified, openQueue]);

  useEffect(() => {
    const handler = (e) => {
      const ann = e.detail?.announcement;
      if (!ann?.id) return;
      openQueue([ann], 'manual');
    };
    window.addEventListener(EVENT_OPEN_ANNOUNCEMENT_MODAL, handler);
    return () => window.removeEventListener(EVENT_OPEN_ANNOUNCEMENT_MODAL, handler);
  }, [openQueue]);

  const handleClose = () => {
    if (source === 'auto') {
      advanceOrClose();
    } else {
      closeAll();
    }
  };

  const handleCloseRef = useRef(handleClose);
  handleCloseRef.current = handleClose;

  useEffect(() => {
    if (!showBanner) return undefined;
    const onKey = (e) => {
      if (e.key === 'Escape') handleCloseRef.current();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [showBanner]);

  const hasText = Boolean((announcement?.message || '').trim());
  const hasImage = Boolean(announcement?.imageUrl);

  if (!showBanner || !announcement) return null;

  const primaryLabel =
    source === 'auto' && queueLength > 1 && queuePosition < queueLength
      ? `Next (${queuePosition} of ${queueLength})`
      : 'Got it';

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/50 backdrop-blur-[1px]"
      role="presentation"
      onClick={handleClose}
    >
      <div
        className="bg-white rounded-2xl shadow-2xl max-w-md w-full max-h-[90vh] overflow-y-auto p-6 relative ring-1 ring-black/5"
        role="dialog"
        aria-modal="true"
        aria-labelledby="announcement-banner-title"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          type="button"
          onClick={handleClose}
          className="absolute top-4 right-4 text-gray-400 hover:text-gray-600 transition-colors rounded-lg p-1 hover:bg-gray-100"
          aria-label="Close announcement"
        >
          <FiX size={24} />
        </button>

        {source === 'auto' && queueLength > 1 && (
          <p className="text-xs font-medium text-blue-600 mb-3 pr-10">
            Important announcement {queuePosition} of {queueLength}
          </p>
        )}

        <div className="flex items-start space-x-4">
          <div className="flex-shrink-0">
            <div className="w-14 h-14 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-full flex items-center justify-center shadow-lg animate-pulse">
              <FaCircleExclamation className="text-white" size={26} />
            </div>
          </div>
          <div className="flex-1 min-w-0">
            <h3
              id="announcement-banner-title"
              className="text-xl font-bold text-gray-900 mb-2 pr-8"
            >
              {announcement.title}
            </h3>
            {announcement.priority === 'high' && (
              <span className="inline-block mb-2 px-2 py-0.5 text-xs font-semibold rounded-full bg-red-100 text-red-800 border border-red-200">
                High priority
              </span>
            )}
            {hasImage && (
              <div className="mb-4 rounded-lg overflow-hidden border border-gray-100 bg-gray-50">
                <img
                  src={announcement.imageUrl}
                  alt=""
                  className="w-full max-h-64 object-contain"
                />
              </div>
            )}
            {hasText && (
              <p className="text-gray-600 mb-4 leading-relaxed whitespace-pre-wrap">
                {announcement.message}
              </p>
            )}
            {!hasText && !hasImage && (
              <p className="text-gray-500 mb-4 text-sm">No content</p>
            )}
            <button
              type="button"
              onClick={handleClose}
              className="w-full bg-blue-600 text-white py-2.5 px-4 rounded-lg font-semibold hover:bg-blue-700 transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
            >
              {primaryLabel}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AnnouncementBanner;
