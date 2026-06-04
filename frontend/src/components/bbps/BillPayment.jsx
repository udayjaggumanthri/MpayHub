import React, { useEffect, useMemo, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { FaArrowLeft } from 'react-icons/fa6';
import { bbpsAPI } from '../../services/api';
import { useAuth } from '../../context/AuthContext';
import MaintenanceBanner from '../common/MaintenanceBanner';
import BillCategorySelector from './BillCategorySelector';
import CreditCardBill from './CreditCardBill';
import BbpsCategoryComingSoon from './BbpsCategoryComingSoon';
import BharatConnectBranding from './BharatConnectBranding';
import {
  buildCategoryCatalog,
  categoryMatchesApiSlug,
  findCanonicalCategory,
  normalizeCategorySlug,
  resolveCategoryRouteSlug,
} from '../../constants/bbpsCanonicalCategories';

const BillPayment = () => {
  const { category } = useParams();
  const navigate = useNavigate();
  const { maintenance, refreshMaintenance } = useAuth();
  const [apiCategories, setApiCategories] = useState([]);

  useEffect(() => {
    refreshMaintenance?.();
    const id = setInterval(() => refreshMaintenance?.(), 60000);
    return () => clearInterval(id);
  }, [refreshMaintenance]);

  useEffect(() => {
    const load = async () => {
      const res = await bbpsAPI.getCategories();
      setApiCategories(Array.isArray(res.data?.categories) ? res.data.categories : []);
    };
    load();
  }, []);

  const catalog = useMemo(() => buildCategoryCatalog(apiCategories), [apiCategories]);
  const availableSlugSet = useMemo(
    () => new Set(catalog.filter((c) => c.hasBillers).map((c) => c.apiSlug)),
    [catalog]
  );
  const categoryEntry = useMemo(() => {
    if (!category) return null;
    const n = normalizeCategorySlug(category);
    return (
      catalog.find(
        (row) =>
          normalizeCategorySlug(row.primarySlug) === n || categoryMatchesApiSlug(row, category)
      ) || null
    );
  }, [catalog, category]);

  const resolvedCategory = category
    ? resolveCategoryRouteSlug(categoryEntry?.apiSlug || category, availableSlugSet)
    : null;
  const categoryMeta = category ? findCanonicalCategory(category) : null;
  const showCategoryPicker = Boolean(category && !categoryEntry);

  const handlePaymentSuccess = (receiptRef = {}) => {
    // Redirect to My Bills and auto-open the latest paid transaction receipt.
    navigate('/bill-payments/my-bills', {
      state: {
        openReceipt: {
          paymentId: receiptRef?.paymentId || null,
          serviceId: receiptRef?.serviceId || '',
          requestId: receiptRef?.requestId || '',
        },
      },
    });
  };

  const categoryPickerShell = (selector) => (
    <div className="mx-auto flex w-full max-w-7xl min-h-0 flex-col gap-3">
      <MaintenanceBanner maintenance={maintenance} moduleKey="bbps" />
      <div className="flex max-h-[calc(100dvh-8.25rem)] min-h-[min(24rem,calc(100dvh-10rem))] flex-col overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm sm:max-h-[calc(100dvh-7.75rem)]">
        <div className="shrink-0 border-b border-gray-100 bg-slate-50/60 px-3 py-3 sm:px-5 sm:py-3.5">
          <BharatConnectBranding
            stage="stage1"
            title="Bill Payment"
            subtitle=""
            showMnemonic={false}
            logoSize="md"
            variant="compact"
          />
          <p className="mt-1.5 text-sm text-slate-600 sm:mt-2">Select a category to continue</p>
        </div>
        <div className="flex min-h-0 flex-1 flex-col px-3 pb-3 pt-3 sm:px-5 sm:pb-4 sm:pt-3.5">{selector}</div>
      </div>
    </div>
  );

  // If no category selected, show category selector
  if (!category) {
    return categoryPickerShell(
      <BillCategorySelector selectedCategory={null} scrollCategoriesOnly />
    );
  }

  if (showCategoryPicker) {
    return (
      <div className="mx-auto flex w-full max-w-6xl min-h-0 flex-col gap-4 sm:gap-6">
        <button
          type="button"
          onClick={() => navigate('/bill-payments/pay')}
          className="flex shrink-0 items-center space-x-2 text-gray-600 transition-colors hover:text-blue-600"
        >
          <FaArrowLeft size={18} />
          <span className="font-medium">Back to Categories</span>
        </button>
        <div className="shrink-0 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          We could not match &quot;{category}&quot; to a bill category. Select one below from all available
          categories.
        </div>
        {categoryPickerShell(
          <BillCategorySelector selectedCategory={null} scrollCategoriesOnly />
        )}
      </div>
    );
  }

  const displayTitle =
    categoryEntry?.displayName ||
    categoryMeta?.displayName ||
    String(category || '')
      .replace(/-/g, ' ')
      .replace(/\b\w/g, (c) => c.toUpperCase());

  if (!categoryEntry.hasBillers) {
    return (
      <BbpsCategoryComingSoon
        categoryName={displayTitle}
        onBack={() => navigate('/bill-payments/pay')}
      />
    );
  }

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-3 overflow-visible">
      <button
        type="button"
        onClick={() => navigate('/bill-payments/pay')}
        className="flex shrink-0 items-center space-x-2 text-gray-600 transition-colors hover:text-blue-600"
      >
        <FaArrowLeft size={18} />
        <span className="font-medium">Back to Categories</span>
      </button>

      <CreditCardBill
        category={resolvedCategory || category}
        categoryLabel={displayTitle}
        onPaymentSuccess={handlePaymentSuccess}
      />
    </div>
  );
};

export default BillPayment;
