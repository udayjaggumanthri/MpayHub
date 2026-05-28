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

  // If no category selected, show category selector
  if (!category) {
    return (
      <div className="max-w-6xl mx-auto space-y-6">
        <MaintenanceBanner maintenance={maintenance} moduleKey="bbps" />
        <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-200">
          <BharatConnectBranding
            stage="stage1"
            title="Bill Payment"
            subtitle=""
            showMnemonic={false}
            logoSize="lg"
          />

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

  if (showCategoryPicker) {
    return (
      <div className="max-w-6xl mx-auto space-y-6">
        <button
          type="button"
          onClick={() => navigate('/bill-payments/pay')}
          className="flex items-center space-x-2 text-gray-600 hover:text-blue-600 transition-colors"
        >
          <FaArrowLeft size={18} />
          <span className="font-medium">Back to Categories</span>
        </button>
        <div className="bg-amber-50 border border-amber-200 rounded-lg px-4 py-3 text-sm text-amber-900">
          We could not match &quot;{category}&quot; to a bill category. Select one below from all available
          categories.
        </div>
        <BillCategorySelector selectedCategory={null} />
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
    <div className="max-w-6xl mx-auto space-y-6">
      <button
        type="button"
        onClick={() => navigate('/bill-payments/pay')}
        className="flex items-center space-x-2 text-gray-600 hover:text-blue-600 transition-colors"
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
