import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { bbpsAPI } from '../../services/api';
import { BBPS_CANONICAL_CATEGORIES, normalizeCategorySlug } from '../../constants/bbpsCanonicalCategories';
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
  FaCreditCard as FaLoan,
  FaRoad,
} from 'react-icons/fa6';

const CATEGORY_ICONS = {
  'agent-collection': FaMoneyBillWave,
  'broadband-postpaid': FaWifi,
  'cable-tv': FaTv,
  'clubs-and-associations': FaBuilding,
  'credit-card': FaCreditCard,
  dth: FaTv,
  echallan: FaMoneyBillWave,
  'education-fees': FaGraduationCap,
  electricity: FaBolt,
  'ev-recharge': FaBolt,
  fastag: FaRoad,
  'fleet-card-recharge': FaMoneyBillWave,
  gas: FaFireFlameSimple,
  'housing-society': FaHouse,
  insurance: FaShield,
  'landline-postpaid': FaPhone,
  'loan-repayment': FaLoan,
  'lpg-gas': FaFireFlameSimple,
  'mobile-postpaid': FaMobileScreenButton,
  'mobile-prepaid': FaMobileScreenButton,
  'municipal-services': FaBuilding,
  'municipal-taxes': FaBuilding,
  'national-pension-system': FaMoneyBillWave,
  'ncmc-recharge': FaTag,
  'prepaid-meter': FaBolt,
  rental: FaHouse,
  subscription: FaMoneyBillWave,
  water: FaDroplet,
};

function isCategoryAvailable(category, availableSlugSet) {
  const primary = normalizeCategorySlug(category.primarySlug);
  if (availableSlugSet.has(primary)) return true;
  return (category.slugAliases || []).some((alias) => availableSlugSet.has(normalizeCategorySlug(alias)));
}

const BillCategorySelector = ({ selectedCategory }) => {
  const navigate = useNavigate();
  const [availableSlugSet, setAvailableSlugSet] = useState(new Set());
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');

  useEffect(() => {
    const loadCategories = async () => {
      const res = await bbpsAPI.getCategories();
      const rows = Array.isArray(res.data?.categories) ? res.data.categories : [];
      const next = new Set(rows.map((r) => normalizeCategorySlug(r.id)));
      setAvailableSlugSet(next);
    };
    loadCategories();
  }, []);

  const handleCategoryClick = (categoryId) => {
    navigate(`/bill-payments/pay/${categoryId}`);
  };

  const orderedCategories = useMemo(() => {
    const q = String(searchQuery || '').trim().toLowerCase();
    const rows = BBPS_CANONICAL_CATEGORIES.map((category) => ({
      ...category,
      isAvailable: isCategoryAvailable(category, availableSlugSet),
    }));
    const filtered = rows.filter((row) => {
      if (statusFilter === 'active' && !row.isAvailable) return false;
      if (statusFilter === 'coming-soon' && row.isAvailable) return false;
      if (!q) return true;
      return row.displayName.toLowerCase().includes(q);
    });
    return filtered.sort((a, b) => {
      if (a.isAvailable !== b.isAvailable) return a.isAvailable ? -1 : 1;
      return a.displayName.localeCompare(b.displayName);
    });
  }, [availableSlugSet, searchQuery, statusFilter]);

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search category"
          className="border rounded-lg px-3 py-2 text-sm md:col-span-2"
        />
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="border rounded-lg px-3 py-2 text-sm"
        >
          <option value="all">All categories</option>
          <option value="active">Active categories</option>
          <option value="coming-soon">Coming Soon</option>
        </select>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
        {orderedCategories.map((category) => {
          const Icon = CATEGORY_ICONS[category.primarySlug] || FaMoneyBillWave;
          const isSelected = selectedCategory === category.primarySlug;
          const isAvailable = category.isAvailable;
          return (
            <button
              key={category.primarySlug}
              type="button"
              onClick={() => handleCategoryClick(category.primarySlug)}
              disabled={!isAvailable}
              title={isAvailable ? '' : 'Coming soon: operators are not active for this category yet.'}
              className={`group relative overflow-hidden p-6 border-2 rounded-2xl transition-all transform hover:scale-105 hover:-translate-y-1 ${
                !isAvailable
                  ? 'border-slate-200 bg-slate-50 cursor-not-allowed opacity-75'
                  : isSelected
                    ? 'border-transparent bg-gradient-to-br from-blue-500 to-indigo-600 shadow-xl shadow-blue-200'
                    : 'border-blue-200 bg-white hover:border-blue-300 hover:shadow-lg hover:bg-blue-50'
              }`}
            >
              {!isAvailable && (
                <span className="absolute right-2 top-2 rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-semibold text-amber-800">
                  Coming Soon
                </span>
              )}
              <div className={`flex flex-col items-center ${isSelected ? 'text-white' : 'text-gray-700'}`}>
                <div
                  className={`p-3 rounded-xl mb-3 ${
                    isSelected
                      ? 'bg-white/20 backdrop-blur-sm'
                      : isAvailable
                        ? 'bg-blue-100 group-hover:bg-blue-200 transition-colors'
                        : 'bg-slate-200'
                  }`}
                >
                  <Icon size={32} className={isSelected ? 'text-white' : isAvailable ? 'text-blue-600' : 'text-slate-500'} />
                </div>
                <p className={`text-sm font-bold text-center leading-snug ${isSelected ? 'text-white' : 'text-gray-700'}`}>
                  {category.displayName}
                </p>
                {!isAvailable && <p className="mt-1 text-[11px] text-slate-500">No operators active</p>}
              </div>
            </button>
          );
        })}
      </div>

      {orderedCategories.length === 0 && (
        <div className="text-sm text-slate-600 border rounded-lg p-3 bg-slate-50">
          No categories matched your current search/filter.
        </div>
      )}
    </div>
  );
};

export default BillCategorySelector;
