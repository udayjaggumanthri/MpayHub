import React from 'react';
import { FaClock, FaArrowLeft } from 'react-icons/fa6';
import BharatConnectBranding from './BharatConnectBranding';

const BbpsCategoryComingSoon = ({ categoryName, onBack }) => {
  const title = String(categoryName || 'This service').trim() || 'This service';

  return (
    <div className="max-w-2xl mx-auto">
      <button
        type="button"
        onClick={onBack}
        className="flex items-center space-x-2 text-gray-600 hover:text-blue-600 transition-colors mb-6"
      >
        <FaArrowLeft size={18} />
        <span className="font-medium">Back to Categories</span>
      </button>

      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
        <div className="p-6 border-b border-gray-100">
          <BharatConnectBranding
            stage="stage1"
            title={title}
            subtitle="Bill payment"
            showMnemonic={false}
            emphasizeRightLogo
            logoSize="md"
          />
        </div>

        <div className="px-6 py-12 text-center">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-amber-100 text-amber-700 mb-5">
            <FaClock size={28} />
          </div>
          <h2 className="text-2xl font-bold text-gray-900 mb-2">Coming Soon</h2>
          <p className="text-gray-600 max-w-md mx-auto">
            {title} is not available yet. Billers for this category will be enabled after catalog sync.
            Please check back later or choose another category.
          </p>
        </div>
      </div>
    </div>
  );
};

export default BbpsCategoryComingSoon;
