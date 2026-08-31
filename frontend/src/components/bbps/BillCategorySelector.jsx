import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { bbpsAPI } from '../../services/api';
import { buildCategoryCatalog } from '../../constants/bbpsCanonicalCategories';
import SelectField from '../common/SelectField';
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

const BillCategorySelector = ({
  selectedCategory,
  viewMode: controlledViewMode,
  onViewModeChange,
  scrollCategoriesOnly = false,
}) => {
  const navigate = useNavigate();
  const [apiCategories, setApiCategories] = useState([]);
  const [selectedSlug, setSelectedSlug] = useState('');
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
    return [...catalog].sort((a, b) => a.displayName.localeCompare(b.displayName));
  }, [catalog]);

  const categoryOptions = useMemo(
    () =>
      orderedCategories.map((row) => ({
        value: row.primarySlug,
        label: row.displayName,
      })),
    [orderedCategories]
  );

  const handleCategorySelect = (slug) => {
    if (!slug) return;
    setSelectedSlug(slug);
    navigate(`/bill-payments/pay/${slug}`);
  };

  const renderCategoryCard = (category) => {
    const Icon = CATEGORY_ICONS[category.primarySlug] || FaMoneyBillWave;
    const isSelected = selectedCategory === category.primarySlug;
    const isList = viewMode === 'list';

    return (
      <button
        key={category.primarySlug}
        type="button"
        onClick={() => handleCategorySelect(category.primarySlug)}
        className={`group relative w-full overflow-hidden rounded-xl border text-left transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 ${
          isList ? 'flex items-center gap-3 px-3 py-2.5 sm:px-4 sm:py-3' : 'flex min-h-[5.25rem] flex-col items-center justify-center px-2 py-3 sm:min-h-[5.5rem] sm:py-3.5'
        } ${
          isSelected
            ? 'border-transparent bg-gradient-to-br from-blue-500 to-indigo-600 shadow-md shadow-blue-200/80'
            : 'border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 hover:border-blue-300 dark:hover:border-blue-700 hover:bg-blue-50/80 dark:hover:bg-blue-950/60 hover:shadow-sm'
        }`}
      >
        <div
          className={`shrink-0 rounded-lg p-2 ${
            isList ? '' : 'mb-1.5'
          } ${isSelected ? 'bg-white/20 dark:bg-slate-900/20' : 'bg-blue-50 dark:bg-blue-950/40 group-hover:bg-blue-100 transition-colors'}`}
        >
          <Icon size={isList ? 22 : 24} className={isSelected ? 'text-white' : 'text-blue-600 dark:text-blue-400'} />
        </div>
        <div className={isList ? 'min-w-0 flex-1' : 'w-full px-0.5'}>
          <p
            className={`font-semibold leading-snug ${
              isList ? 'text-sm sm:text-base' : 'text-center text-xs sm:text-[13px]'
            } ${isSelected ? 'text-white' : 'text-gray-800 dark:text-slate-200'}`}
          >
            {category.displayName}
          </p>
          {isList && category.fromApi && (
            <p className={`mt-0.5 text-[11px] ${isSelected ? 'text-blue-100' : 'text-slate-400 dark:text-slate-500'}`}>
              From biller catalog
            </p>
          )}
        </div>
      </button>
    );
  };

  const categoryCountLabel =
    orderedCategories.length === 1 ? '1 category' : `${orderedCategories.length} categories`;

  const toolbar = (
    <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end sm:gap-2.5">
      <div className="min-w-0 flex-1 sm:max-w-md">
        <SelectField
          searchable
          label="Select category"
          value={selectedSlug || selectedCategory || ''}
          onChange={handleCategorySelect}
          options={categoryOptions}
          placeholder="Choose a bill category…"
          includeEmptyOption
          emptyOptionLabel="Choose a bill category…"
        />
      </div>
      <div className="flex items-center justify-between gap-2 sm:justify-end sm:gap-3 sm:pb-0.5">
        <span className="text-xs font-medium text-slate-500 dark:text-slate-400 tabular-nums" aria-live="polite">
          {categoryCountLabel}
        </span>
        <div className="inline-flex shrink-0 rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50 p-0.5">
        <button
          type="button"
          onClick={() => setViewMode('grid')}
          className={`inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors sm:px-3 sm:text-sm ${
            viewMode === 'grid' ? 'bg-white dark:bg-slate-900 text-blue-700 dark:text-blue-300 shadow-sm' : 'text-gray-600 dark:text-slate-400 hover:text-gray-900 dark:hover:text-slate-100'
          }`}
          aria-pressed={viewMode === 'grid'}
        >
          <FaGrip size={13} />
          Grid
        </button>
        <button
          type="button"
          onClick={() => setViewMode('list')}
          className={`inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors sm:px-3 sm:text-sm ${
            viewMode === 'list' ? 'bg-white dark:bg-slate-900 text-blue-700 dark:text-blue-300 shadow-sm' : 'text-gray-600 dark:text-slate-400 hover:text-gray-900 dark:hover:text-slate-100'
          }`}
          aria-pressed={viewMode === 'list'}
        >
          <FaList size={13} />
          List
        </button>
        </div>
      </div>
    </div>
  );

  const categoryGrid = (
    <div
      className={
        viewMode === 'grid'
          ? 'grid grid-cols-2 gap-2 sm:grid-cols-3 sm:gap-2.5 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6'
          : 'flex flex-col gap-2'
      }
    >
      {orderedCategories.map((category) => renderCategoryCard(category))}
    </div>
  );

  const emptyState =
    orderedCategories.length === 0 ? (
      <div className="rounded-lg border border-dashed border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50 px-4 py-8 text-center text-sm text-slate-600 dark:text-slate-400">
        <p className="font-medium text-slate-700 dark:text-slate-300">No categories found</p>
        <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">Try choosing another category from the dropdown above.</p>
      </div>
    ) : null;

  if (scrollCategoriesOnly) {
    return (
      <div className="flex min-h-0 flex-1 flex-col">
        <div className="shrink-0 border-b border-gray-100 dark:border-slate-800 pb-3">{toolbar}</div>
        <div
          className="relative min-h-0 flex-1 overflow-y-auto overscroll-contain scroll-smooth pt-3 [scrollbar-gutter:stable]"
          aria-label="Bill categories"
        >
          {categoryGrid}
          {emptyState}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {toolbar}
      {categoryGrid}
      {emptyState}
    </div>
  );
};

export default BillCategorySelector;
