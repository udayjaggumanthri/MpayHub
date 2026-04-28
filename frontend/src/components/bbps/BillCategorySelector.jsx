import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { bbpsAPI } from '../../services/api';
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

const CATEGORY_ICONS = {
  'credit-card': FaCreditCard,
  electricity: FaBolt,
  insurance: FaShield,
  'mobile-recharge': FaMobileScreenButton,
  dth: FaTv,
  fasttag: FaTag,
  water: FaDroplet,
  gas: FaFireFlameSimple,
  'municipal-tax': FaBuilding,
  education: FaGraduationCap,
  'loan-emi': FaLoan,
  broadband: FaWifi,
  landline: FaPhone,
  housing: FaHouse,
  subscriptions: FaMoneyBillWave,
};

const BillCategorySelector = ({ selectedCategory }) => {
  const navigate = useNavigate();
  const [categories, setCategories] = useState([]);

  useEffect(() => {
    const loadCategories = async () => {
      const res = await bbpsAPI.getCategories();
      const rows = Array.isArray(res.data?.categories) ? res.data.categories : [];
      if (res.success && rows.length > 0) {
        const mapped = rows.map((r) => {
          const id = String(r.id || '').trim();
          return {
            id,
            name: r.name || id,
            icon: CATEGORY_ICONS[id] || FaMoneyBillWave,
          };
        });
        setCategories(mapped);
      } else {
        setCategories([]);
      }
    };
    loadCategories();
  }, []);

  const handleCategoryClick = (categoryId) => {
    navigate(`/bill-payments/pay/${categoryId}`);
  };

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
      {categories.length === 0 && (
        <div className="col-span-full text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded-lg p-3">
          No active BBPS categories found. Complete admin governance setup and MDM sync first.
        </div>
      )}
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
