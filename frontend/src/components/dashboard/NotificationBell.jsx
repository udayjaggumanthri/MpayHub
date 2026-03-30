import React, { useState, useEffect, useCallback } from 'react';
import { FaBell } from 'react-icons/fa6';
import { useAuth } from '../../context/AuthContext';
import { adminAPI } from '../../services/api';
import {
  flattenAnnouncementsPayload,
  mapAnnouncementForConsumer,
  markAnnouncementDismissedInClient,
  openAnnouncementModal,
  sortAnnouncementsNewestFirst,
  EVENT_ANNOUNCEMENT_READ_CHANGED,
} from '../../utils/announcements';

const priorityLabel = (p) => {
  if (p === 'high') return 'High';
  if (p === 'medium') return 'Medium';
  return 'Low';
};

const priorityStyles = (p) => {
  if (p === 'high')
    return 'bg-red-50 text-red-800 border-red-200';
  if (p === 'medium')
    return 'bg-amber-50 text-amber-900 border-amber-200';
  return 'bg-slate-50 text-slate-700 border-slate-200';
};

const NotificationBell = () => {
  const { user } = useAuth();
  const [notifications, setNotifications] = useState([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const [listLoading, setListLoading] = useState(false);

  const refresh = useCallback(async () => {
    if (!user) return;
    setListLoading(true);
    try {
      const result = await adminAPI.listAnnouncements({ page_size: 100 });
      if (!result.success) return;
      const list = flattenAnnouncementsPayload(result.data)
        .map(mapAnnouncementForConsumer)
        .filter((n) => n.isActive);
      setNotifications(sortAnnouncementsNewestFirst(list));
    } finally {
      setListLoading(false);
    }
  }, [user]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    const onReadChanged = () => refresh();
    window.addEventListener(EVENT_ANNOUNCEMENT_READ_CHANGED, onReadChanged);
    return () => window.removeEventListener(EVENT_ANNOUNCEMENT_READ_CHANGED, onReadChanged);
  }, [refresh]);

  const unreadCount = notifications.filter((n) => !n.read).length;
  const hasUnread = unreadCount > 0;

  const markOneRead = (e, notificationId) => {
    e?.stopPropagation?.();
    markAnnouncementDismissedInClient(notificationId);
    setNotifications((prev) =>
      prev.map((n) => (n.id === notificationId ? { ...n, read: true } : n))
    );
  };

  const showAgain = (e, notification) => {
    e?.stopPropagation?.();
    openAnnouncementModal(notification);
    setShowDropdown(false);
  };

  const markAllAsRead = (e) => {
    e?.stopPropagation?.();
    notifications.forEach((n) => {
      if (!n.read) markAnnouncementDismissedInClient(n.id);
    });
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
  };

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => {
          setShowDropdown(!showDropdown);
          if (!showDropdown) refresh();
        }}
        className="relative p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
        aria-label="Notifications"
        aria-expanded={showDropdown}
      >
        <FaBell
          size={24}
          className={`transition-all duration-300 ${
            hasUnread
              ? 'text-blue-600 animate-bell-flash animate-bell-zoom'
              : 'text-gray-600'
          }`}
        />
        {hasUnread && (
          <span className="absolute top-0 right-0 min-w-[1.25rem] h-5 px-1 bg-red-500 text-white text-xs font-bold rounded-full flex items-center justify-center animate-pulse">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      {showDropdown && (
        <>
          <div
            className="fixed inset-0 z-10"
            onClick={() => setShowDropdown(false)}
            aria-hidden="true"
          />
          <div
            className="absolute right-0 mt-2 w-[22rem] max-w-[calc(100vw-1rem)] bg-white rounded-xl shadow-xl border border-gray-200 z-20 flex flex-col max-h-[min(32rem,calc(100vh-6rem))]"
            role="dialog"
            aria-label="Notifications list"
          >
            <div className="p-4 border-b border-gray-200 flex items-start justify-between gap-2 shrink-0">
              <div className="min-w-0">
                <h3 className="font-semibold text-gray-900">Notifications</h3>
                <p className="text-xs text-gray-500 mt-1">
                  {notifications.length === 0
                    ? 'No active announcements'
                    : `${notifications.length} announcement${notifications.length !== 1 ? 's' : ''} · Newest first`}
                  {listLoading ? ' · Updating…' : ''}
                </p>
                {hasUnread && (
                  <p className="text-sm text-blue-600 font-medium mt-1">
                    {unreadCount} unread
                  </p>
                )}
              </div>
              {hasUnread && (
                <button
                  type="button"
                  onClick={markAllAsRead}
                  className="text-xs text-blue-600 hover:text-blue-700 font-semibold transition-colors shrink-0 whitespace-nowrap"
                >
                  Mark all read
                </button>
              )}
            </div>

            <div className="overflow-y-auto flex-1 min-h-0 overscroll-contain">
              {notifications.length === 0 && !listLoading ? (
                <div className="p-6 text-center text-gray-500 text-sm">No notifications</div>
              ) : (
                <div className="divide-y divide-gray-100">
                  {notifications.map((notification) => (
                    <div
                      key={notification.id}
                      className={`p-4 transition-colors ${
                        !notification.read ? 'bg-blue-50/60' : 'bg-white'
                      }`}
                    >
                      <div className="flex items-start gap-3">
                        <div
                          className={`w-2.5 h-2.5 rounded-full mt-1.5 flex-shrink-0 ${
                            !notification.read ? 'bg-blue-600' : 'bg-gray-300'
                          }`}
                          title={notification.read ? 'Read' : 'Unread'}
                        />
                        <div className="flex-1 min-w-0">
                          <div className="flex flex-wrap items-center gap-2 mb-1">
                            <p
                              className={`font-semibold text-sm ${
                                !notification.read ? 'text-gray-900' : 'text-gray-700'
                              }`}
                            >
                              {notification.title}
                            </p>
                            <span
                              className={`text-[10px] uppercase tracking-wide font-bold px-1.5 py-0.5 rounded border ${priorityStyles(
                                notification.priority
                              )}`}
                            >
                              {priorityLabel(notification.priority)}
                            </span>
                          </div>
                          {notification.imageUrl && (
                            <img
                              src={notification.imageUrl}
                              alt=""
                              className="mt-1 w-full max-h-28 object-contain rounded-lg border border-gray-100 bg-gray-50"
                            />
                          )}
                          {(notification.message || '').trim() ? (
                            <p className="text-sm text-gray-600 mt-2 whitespace-pre-wrap line-clamp-4">
                              {notification.message}
                            </p>
                          ) : null}
                          <p className="text-xs text-gray-400 mt-2">
                            {notification.date
                              ? new Date(notification.date).toLocaleDateString('en-IN', {
                                  year: 'numeric',
                                  month: 'short',
                                  day: 'numeric',
                                })
                              : ''}
                          </p>
                          <div className="flex flex-wrap gap-2 mt-3">
                            {!notification.read ? (
                              <button
                                type="button"
                                onClick={(e) => markOneRead(e, notification.id)}
                                className="text-xs font-semibold px-2.5 py-1.5 rounded-lg bg-white border border-gray-200 text-gray-800 hover:bg-gray-50 hover:border-gray-300 transition-colors"
                              >
                                Mark as read
                              </button>
                            ) : (
                              <span className="text-xs text-gray-500 py-1.5">Read</span>
                            )}
                            <button
                              type="button"
                              onClick={(e) => showAgain(e, notification)}
                              className="text-xs font-semibold px-2.5 py-1.5 rounded-lg bg-blue-600 text-white hover:bg-blue-700 transition-colors"
                            >
                              {notification.priority === 'high'
                                ? 'Show as pop-up'
                                : 'Show full screen'}
                            </button>
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {notifications.length >= 100 && (
              <div className="px-4 py-2 border-t border-gray-100 bg-gray-50 text-[11px] text-gray-500 shrink-0">
                Showing the latest 100 announcements. Older items are not listed here.
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
};

export default NotificationBell;
