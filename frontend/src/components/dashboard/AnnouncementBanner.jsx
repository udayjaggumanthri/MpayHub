import React, { useState, useEffect } from 'react';
import { FiX } from 'react-icons/fi';
import { FaCircleExclamation } from 'react-icons/fa6';
import { useAuth } from '../../context/AuthContext';
import { getAnnouncements } from '../../services/mockData';

const AnnouncementBanner = () => {
  const { user } = useAuth();
  const [showBanner, setShowBanner] = useState(false);
  const [announcement, setAnnouncement] = useState(null);

  useEffect(() => {
    if (!user) return;

    // Check if announcement was shown today (first login of the day only)
    const today = new Date().toDateString();
    const lastLoginDate = localStorage.getItem('mpayhub_last_login_date');
    const announcementShownToday = localStorage.getItem(`mpayhub_announcement_shown_${today}`);

    // Only show if this is the first login of the day (not just a page refresh)
    if (lastLoginDate !== today && !announcementShownToday) {
      // Get high priority announcements
      const result = getAnnouncements(user.id);
      if (result.success && result.announcements.length > 0) {
        const highPriority = result.announcements.find(
          (a) => a.priority === 'high' && !a.read
        );
        if (highPriority) {
          setAnnouncement(highPriority);
          setShowBanner(true);
          // Mark that announcement was shown today
          localStorage.setItem(`mpayhub_announcement_shown_${today}`, 'true');
        }
      }
    }

    // Update last login date
    localStorage.setItem('mpayhub_last_login_date', today);
  }, [user]);

  const handleClose = () => {
    setShowBanner(false);
    // Mark announcement as read (in real app, this would call an API)
    if (announcement) {
      // This would be handled by backend in real implementation
      console.log('Marking announcement as read:', announcement.id);
    }
  };

  if (!showBanner || !announcement) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black bg-opacity-50">
      <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full p-6 relative">
        <button
          onClick={handleClose}
          className="absolute top-4 right-4 text-gray-400 hover:text-gray-600 transition-colors"
        >
          <FiX size={24} />
        </button>

        <div className="flex items-start space-x-4">
          <div className="flex-shrink-0">
            <div className="w-14 h-14 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-full flex items-center justify-center animate-pulse shadow-lg">
              <FaCircleExclamation className="text-white" size={26} />
            </div>
          </div>
          <div className="flex-1">
            <h3 className="text-xl font-bold text-gray-900 mb-2">
              {announcement.title}
            </h3>
            <p className="text-gray-600 mb-4 leading-relaxed">{announcement.message}</p>
            <div className="flex space-x-3">
              <button
                onClick={handleClose}
                className="flex-1 bg-blue-600 text-white py-2.5 px-4 rounded-lg font-semibold hover:bg-blue-700 transition-colors"
              >
                Got it
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AnnouncementBanner;
