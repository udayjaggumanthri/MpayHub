import React from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  FaCreditCard, 
  FaBolt, 
  FaShield, 
  FaMobileScreenButton, 
  FaTag, 
  FaGraduationCap, 
  FaDroplet, 
  FaWifi,
  FaTv,
  FaFireFlameSimple,
  FaBuilding,
  FaMoneyBillWave,
  FaPhone,
  FaHouse,
  FaCreditCard as FaLoan
} from 'react-icons/fa6';

const categories = [
  { id: 'credit-card', name: 'Credit Card', icon: FaCreditCard },
  { id: 'electricity', name: 'Electricity', icon: FaBolt },
  { id: 'insurance', name: 'Insurance', icon: FaShield },
  { id: 'mobile-recharge', name: 'Mobile Recharge', icon: FaMobileScreenButton },
  { id: 'dth', name: 'DTH', icon: FaTv },
  { id: 'fasttag', name: 'FASTag', icon: FaTag },
  { id: 'water', name: 'Water', icon: FaDroplet },
  { id: 'gas', name: 'Piped Gas', icon: FaFireFlameSimple },
  { id: 'municipal-tax', name: 'Municipal Tax', icon: FaBuilding },
  { id: 'education', name: 'Education', icon: FaGraduationCap },
  { id: 'loan-emi', name: 'Loan EMI', icon: FaLoan },
  { id: 'broadband', name: 'Broadband', icon: FaWifi },
  { id: 'landline', name: 'Landline Postpaid', icon: FaPhone },
  { id: 'housing', name: 'Housing', icon: FaHouse },
  { id: 'subscriptions', name: 'Subscriptions', icon: FaMoneyBillWave },
];

const BillCategorySelector = ({ selectedCategory }) => {
  const navigate = useNavigate();

  const handleCategoryClick = (categoryId) => {
    navigate(`/bill-payments/pay/${categoryId}`);
  };

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
      {categories.map((category) => {
        const Icon = category.icon;
        const isSelected = selectedCategory === category.id;
        return (
          <button
            key={category.id}
            onClick={() => handleCategoryClick(category.id)}
            className={`group relative overflow-hidden p-6 border-2 rounded-2xl transition-all transform hover:scale-105 hover:-translate-y-1 ${
              isSelected
                ? 'border-transparent bg-gradient-to-br from-blue-500 to-indigo-600 shadow-xl shadow-blue-200'
                : 'border-blue-200 bg-white hover:border-blue-300 hover:shadow-lg hover:bg-blue-50'
            }`}
          >
            <div className={`flex flex-col items-center ${isSelected ? 'text-white' : 'text-gray-700'}`}>
              <div className={`p-3 rounded-xl mb-3 ${isSelected ? 'bg-white/20 backdrop-blur-sm' : 'bg-blue-100 group-hover:bg-blue-200 transition-colors'}`}>
                <Icon
                  size={32}
                  className={isSelected ? 'text-white' : 'text-blue-600'}
                />
              </div>
              <p className={`text-sm font-bold ${isSelected ? 'text-white' : 'text-gray-700'}`}>
                {category.name}
              </p>
            </div>
          </button>
        );
      })}
    </div>
  );
};

export default BillCategorySelector;
