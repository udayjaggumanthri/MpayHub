import { useCallback, useState } from 'react';
import FeedbackModal from '../../../components/common/FeedbackModal';

/**
 * Modal + optional inline message for AEPS setup flows.
 */
export function useAepsFeedback() {
  const [modal, setModal] = useState({ open: false, title: '', description: '', primaryAction: null });
  const [inline, setInline] = useState({ type: '', text: '' });

  const closeModal = useCallback(() => setModal((m) => ({ ...m, open: false })), []);

  const showError = useCallback((message, title = 'Something went wrong') => {
    const text = String(message || 'Request failed.');
    setInline({ type: 'error', text });
    setModal({ open: true, title, description: text, primaryAction: null });
  }, []);

  const showSuccess = useCallback((message, { title = 'Success', onCloseNavigate = null } = {}) => {
    const text = String(message || 'Done.');
    setInline({ type: 'success', text });
    setModal({
      open: true,
      title,
      description: text,
      primaryAction: onCloseNavigate
        ? { label: 'Continue', onClick: onCloseNavigate }
        : null,
    });
  }, []);

  const showInfo = useCallback((message, title = 'Notice') => {
    const text = String(message || '');
    setInline({ type: 'info', text });
    setModal({ open: true, title, description: text, primaryAction: null });
  }, []);

  const clearInline = useCallback(() => setInline({ type: '', text: '' }), []);

  const FeedbackPortal = (
    <FeedbackModal
      open={modal.open}
      onClose={closeModal}
      title={modal.title}
      description={modal.description}
      primaryAction={modal.primaryAction}
    />
  );

  return {
    inline,
    clearInline,
    showError,
    showSuccess,
    showInfo,
    closeModal,
    FeedbackPortal,
  };
}
