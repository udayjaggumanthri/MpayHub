import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { bbpsAPI } from '../../services/api';
import { buildCategoryCatalog } from '../../constants/bbpsCanonicalCategories';
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
  FaList,
  FaGrip,
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

const BillCategorySelector = ({ selectedCategory, viewMode: controlledViewMode, onViewModeChange }) => {
  const navigate = useNavigate();
  const [apiCategories, setApiCategories] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [internalViewMode, setInternalViewMode] = useState('grid');
  const viewMode = controlledViewMode || internalViewMode;
  const setViewMode = onViewModeChange || setInternalViewMode;

  useEffect(() => {
    const loadCategories = async () => {
      const res = await bbpsAPI.getCategories();
      const rows = Array.isArray(res.data?.categories) ? res.data.categories : [];
      setApiCategories(rows);
    };
    loadCategories();
  }, []);

  const catalog = useMemo(() => buildCategoryCatalog(apiCategories), [apiCategories]);

  const orderedCategories = useMemo(() => {
    const q = String(searchQuery || '').trim().toLowerCase();
    const filtered = catalog.filter((row) => {
      if (statusFilter === 'with-billers' && !row.hasBillers) return false;
      if (statusFilter === 'no-billers' && row.hasBillers) return false;
      if (!q) return true;
      return row.displayName.toLowerCase().includes(q) || row.primarySlug.toLowerCase().includes(q);
    });
    return filtered.sort((a, b) => {
      if (a.hasBillers !== b.hasBillers) return a.hasBillers ? -1 : 1;
      return a.displayName.localeCompare(b.displayName);
    });
  }, [catalog, searchQuery, statusFilter]);

  const handleCategoryClick = (category) => {
    navigate(`/bill-payments/pay/${category.primarySlug}`);
  };

  const renderCategoryCard = (category) => {
    const Icon = CATEGORY_ICONS[category.primarySlug] || FaMoneyBillWave;
    const isSelected = selectedCategory === category.primarySlug;
    const isList = viewMode === 'list';

    return (
      <button
        key={category.primarySlug}
        type="button"
        onClick={() => handleCategoryClick(category)}
        className={`group relative overflow-hidden border-2 rounded-2xl transition-all text-left w-full ${
          isList ? 'flex items-center gap-4 p-4' : 'p-6 flex flex-col items-center'
        } ${
          isSelected
            ? 'border-transparent bg-gradient-to-br from-blue-500 to-indigo-600 shadow-xl shadow-blue-200'
            : 'border-blue-200 bg-white hover:border-blue-300 hover:shadow-lg hover:bg-blue-50 hover:-translate-y-0.5'
        }`}
      >
        <div
          className={`shrink-0 p-3 rounded-xl ${
            isList ? '' : 'mb-3'
          } ${isSelected ? 'bg-white/20 backdrop-blur-sm' : 'bg-blue-100 group-hover:bg-blue-200 transition-colors'}`}
        >
          <Icon size={isList ? 28 : 32} className={isSelected ? 'text-white' : 'text-blue-600'} />
        </div>
        <div className={isList ? 'flex-1 min-w-0' : ''}>
          <p
            className={`font-bold leading-snug ${isList ? 'text-base' : 'text-sm text-center'} ${
              isSelected ? 'text-white' : 'text-gray-800'
            }`}
          >
            {category.displayName}
          </p>
          {category.fromApi && (
            <p className={`text-[11px] mt-0.5 ${isSelected ? 'text-blue-100' : 'text-slate-400'}`}>
              From biller catalog
            </p>
          )}
        </div>
      </button>
    );
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 flex-1">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search category"
            className="border rounded-lg px-3 py-2 text-sm"
          />
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="border rounded-lg px-3 py-2 text-sm"
          >
            <option value="all">All categories</option>
            <option value="with-billers">With active billers</option>
            <option value="no-billers">Awaiting billers</option>
          </select>
        </div>
        <div className="inline-flex rounded-lg border border-gray-200 p-1 bg-gray-50 self-start">
          <button
            type="button"
            onClick={() => setViewMode('grid')}
            className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
              viewMode === 'grid' ? 'bg-white text-blue-700 shadow-sm' : 'text-gray-600 hover:text-gray-900'
            }`}
            aria-pressed={viewMode === 'grid'}
          >
            <FaGrip size={14} />
            Grid
          </button>
          <button
            type="button"
            onClick={() => setViewMode('list')}
            className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
              viewMode === 'list' ? 'bg-white text-blue-700 shadow-sm' : 'text-gray-600 hover:text-gray-900'
            }`}
            aria-pressed={viewMode === 'list'}
          >
            <FaList size={14} />
            List
          </button>
        </div>
      </div>

      <div
        className={
          viewMode === 'grid'
            ? 'grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4'
            : 'flex flex-col gap-3'
        }
      >
        {orderedCategories.map((category) => renderCategoryCard(category))}
      </div>

      {orderedCategories.length === 0 && (
        <div className="text-sm text-slate-600 border rounded-lg p-3 bg-slate-50">
          No categories matched your search. Try clearing filters or check biller sync in admin.
        </div>
      )}
    </div>
  );
};

export default BillCategorySelector;
