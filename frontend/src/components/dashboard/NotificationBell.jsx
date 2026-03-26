import React, { useState, useEffect } from 'react';
import { FaBell } from 'react-icons/fa6';
import { useAuth } from '../../context/AuthContext';
import { getAnnouncements } from '../../services/mockData';

const NotificationBell = () => {
  const { user } = useAuth();
  const [notifications, setNotifications] = useState([]);
  const [showDropdown, setShowDropdown] = useState(false);

  useEffect(() => {
    if (user) {
      const result = getAnnouncements(user.id);
      if (result.success) {
        setNotifications(result.announcements || []);
      }
    }
  }, [user]);

  // Calculate unread count and status - updates immediately when notifications change
  const unreadCount = notifications.filter((n) => !n.read).length;
  const hasUnread = unreadCount > 0;

  const handleNotificationClick = (notificationId) => {
    // Mark notification as read immediately
    setNotifications((prev) => {
      const updated = prev.map((n) =>
        n.id === notificationId ? { ...n, read: true } : n
      );
      // In real app, this would call an API to mark as read
      return updated;
    });
  };

  const markAllAsRead = () => {
    // Mark all notifications as read immediately
    setNotifications((prev) => {
      const updated = prev.map((n) => ({ ...n, read: true }));
      // In real app, this would call an API to mark all as read
      return updated;
    });
  };

  return (
    <div className="relative">
      <button
        onClick={() => setShowDropdown(!showDropdown)}
        className="relative p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
        aria-label="Notifications"
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
          <span className="absolute top-0 right-0 w-5 h-5 bg-red-500 text-white text-xs font-bold rounded-full flex items-center justify-center animate-pulse">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      {/* Dropdown */}
      {showDropdown && (
        <>
          <div
            className="fixed inset-0 z-10"
            onClick={() => setShowDropdown(false)}
          ></div>
          <div className="absolute right-0 mt-2 w-80 bg-white rounded-lg shadow-xl border border-gray-200 z-20 max-h-96 overflow-y-auto">
            <div className="p-4 border-b border-gray-200 flex items-center justify-between">
              <div>
                <h3 className="font-semibold text-gray-900">Notifications</h3>
                {hasUnread && (
                  <p className="text-sm text-gray-500 mt-1">
                    {unreadCount} unread notification{unreadCount > 1 ? 's' : ''}
                  </p>
                )}
              </div>
              {hasUnread && (
                <button
                  onClick={markAllAsRead}
                  className="text-xs text-blue-600 hover:text-blue-700 font-medium transition-colors"
                >
                  Mark all read
                </button>
              )}
            </div>

            {notifications.length === 0 ? (
              <div className="p-6 text-center text-gray-500">
                No notifications
              </div>
            ) : (
              <div className="divide-y divide-gray-200">
                {notifications.map((notification) => (
                  <div
                    key={notification.id}
                    onClick={() => handleNotificationClick(notification.id)}
                    className={`p-4 hover:bg-gray-50 cursor-pointer transition-colors ${
                      !notification.read ? 'bg-blue-50' : ''
                    }`}
                  >
                    <div className="flex items-start space-x-3">
                      <div
                        className={`w-2 h-2 rounded-full mt-2 flex-shrink-0 ${
                          !notification.read ? 'bg-blue-600' : 'bg-gray-300'
                        }`}
                      ></div>
                      <div className="flex-1 min-w-0">
                        <p className={`font-medium ${
                          !notification.read ? 'text-gray-900' : 'text-gray-700'
                        }`}>
                          {notification.title}
                        </p>
                        <p className="text-sm text-gray-600 mt-1">
                          {notification.message}
                        </p>
                        <p className="text-xs text-gray-400 mt-2">
                          {new Date(notification.date).toLocaleDateString('en-IN', {
                            year: 'numeric',
                            month: 'short',
                            day: 'numeric',
                          })}
                        </p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
};

export default NotificationBell;
