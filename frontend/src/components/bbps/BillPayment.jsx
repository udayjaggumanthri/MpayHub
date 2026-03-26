import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { FaArrowLeft } from 'react-icons/fa6';
import BillCategorySelector from './BillCategorySelector';
import CreditCardBill from './CreditCardBill';

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
          <h1 className="text-2xl font-bold text-gray-900 mb-6">Bill Payments</h1>

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
        {category === 'credit-card' && (
          <CreditCardBill onPaymentSuccess={handlePaymentSuccess} />
        )}

        {category === 'electricity' && (
          <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-200">
            <h2 className="text-xl font-bold text-gray-900 mb-4">Electricity Bill Payment</h2>
            <p className="text-gray-600">Electricity bill payment feature coming soon...</p>
          </div>
        )}

        {category === 'insurance' && (
          <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-200">
            <h2 className="text-xl font-bold text-gray-900 mb-4">Insurance Bill Payment</h2>
            <p className="text-gray-600">Insurance bill payment feature coming soon...</p>
          </div>
        )}

        {category === 'mobile-recharge' && (
          <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-200">
            <h2 className="text-xl font-bold text-gray-900 mb-4">Mobile Recharge</h2>
            <p className="text-gray-600">Mobile recharge feature coming soon...</p>
          </div>
        )}

        {category === 'fasttag' && (
          <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-200">
            <h2 className="text-xl font-bold text-gray-900 mb-4">FastTag Recharge</h2>
            <p className="text-gray-600">FastTag recharge feature coming soon...</p>
          </div>
        )}

        {category === 'water' && (
          <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-200">
            <h2 className="text-xl font-bold text-gray-900 mb-4">Water Bill Payment</h2>
            <p className="text-gray-600">Water bill payment feature coming soon...</p>
          </div>
        )}

        {category === 'education' && (
          <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-200">
            <h2 className="text-xl font-bold text-gray-900 mb-4">Education Fee Payment</h2>
            <p className="text-gray-600">Education fee payment feature coming soon...</p>
          </div>
        )}

        {category === 'broadband' && (
          <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-200">
            <h2 className="text-xl font-bold text-gray-900 mb-4">Broadband Bill Payment</h2>
            <p className="text-gray-600">Broadband bill payment feature coming soon...</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default BillPayment;
