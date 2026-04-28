import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { FaArrowLeft } from 'react-icons/fa6';
import BillCategorySelector from './BillCategorySelector';
import CreditCardBill from './CreditCardBill';
import BharatConnectBranding from './BharatConnectBranding';

const BillPayment = () => {
  const { category } = useParams();
  const navigate = useNavigate();

  const handlePaymentSuccess = () => {
    // Navigate back to category selection after successful payment
    navigate('/bill-payments/pay');
  };

  // If no category selected, show category selector
  if (!category) {
    return (
      <div className="max-w-6xl mx-auto space-y-6">
        <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-200">
          <BharatConnectBranding stage="stage1" title="Bill Payments" />

          {/* Category Selector */}
          <div className="mb-8">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              Select Bill Category
            </h2>
            <BillCategorySelector selectedCategory={null} />
          </div>
        </div>
      </div>
    );
  }

  // Show category-specific form with back button
  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Back Button */}
      <button
        onClick={() => navigate('/bill-payments/pay')}
        className="flex items-center space-x-2 text-gray-600 hover:text-blue-600 transition-colors mb-4"
      >
        <FaArrowLeft size={18} />
        <span className="font-medium">Back to Categories</span>
      </button>

      {/* Category-Specific Forms */}
      <div>
        <CreditCardBill category={category} onPaymentSuccess={handlePaymentSuccess} />
      </div>
    </div>
  );
};

export default BillPayment;
