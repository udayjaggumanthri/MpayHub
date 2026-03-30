/**
 * Helpers for announcement API payloads and client-side read state.
 */

/** Set when MPIN succeeds; dashboard modal reads this once. */
export const SESSION_POST_MPIN_ANNOUNCE = 'mpayhub_post_mpin_dashboard';

/** Calendar day we last ran the dashboard announcement fetch (session restore / daily). */
export const LS_DASHBOARD_ANN_DAY = 'mpayhub_dashboard_ann_day';

const READ_PREFIX = 'mpayhub_ann_read_';

export const EVENT_ANNOUNCEMENT_READ_CHANGED = 'mpayhub:announcement-read-changed';

function emitReadChanged() {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(new CustomEvent(EVENT_ANNOUNCEMENT_READ_CHANGED));
}

export function isAnnouncementDismissedInClient(id) {
  return localStorage.getItem(`${READ_PREFIX}${id}`) === '1';
}

export function markAnnouncementDismissedInClient(id) {
  localStorage.setItem(`${READ_PREFIX}${id}`, '1');
  emitReadChanged();
}

/** Remove read/dismissed flag so the item appears unread in the bell again. */
export function clearAnnouncementDismissedInClient(id) {
  localStorage.removeItem(`${READ_PREFIX}${id}`);
  emitReadChanged();
}

/** Open the full-screen announcement modal from anywhere (e.g. bell "Show again"). */
export const EVENT_OPEN_ANNOUNCEMENT_MODAL = 'mpayhub:open-announcement-modal';

export function openAnnouncementModal(announcement) {
  if (typeof window === 'undefined' || !announcement) return;
  window.dispatchEvent(
    new CustomEvent(EVENT_OPEN_ANNOUNCEMENT_MODAL, {
      detail: { announcement: { ...announcement } },
    })
  );
}

export function sortAnnouncementsNewestFirst(list) {
  return [...list].sort((a, b) => {
    const ta = a?.date ? new Date(a.date).getTime() : 0;
    const tb = b?.date ? new Date(b.date).getTime() : 0;
    return tb - ta;
  });
}

/** Normalize paginated or raw list responses from the announcements API. */
export function flattenAnnouncementsPayload(data) {
  if (!data) return [];
  if (Array.isArray(data)) return data;
  if (Array.isArray(data.results)) return data.results;
  if (Array.isArray(data.announcements)) return data.announcements;
  return [];
}

/** Paginated admin list: items + total count + DRF next/previous URLs. */
export function parseAnnouncementListResponse(result) {
  const d = result?.data;
  const list = flattenAnnouncementsPayload(d);
  const totalCount = typeof d?.count === 'number' ? d.count : list.length;
  return {
    list,
    totalCount,
    next: d?.next ?? null,
    previous: d?.previous ?? null,
  };
}

const LS_ANNOUNCEMENT_ADMIN_VIEW = 'mpayhub_announcement_admin_view_mode';

export function getStoredAnnouncementAdminViewMode() {
  if (typeof window === 'undefined') return 'list';
  const v = localStorage.getItem(LS_ANNOUNCEMENT_ADMIN_VIEW);
  return v === 'grid' ? 'grid' : 'list';
}

export function setStoredAnnouncementAdminViewMode(mode) {
  if (typeof window === 'undefined') return;
  localStorage.setItem(LS_ANNOUNCEMENT_ADMIN_VIEW, mode === 'grid' ? 'grid' : 'list');
}

/**
 * Map API row to a shape used by banner / notification bell.
 * @param {object} item - Serializer output
 */
export function mapAnnouncementForConsumer(item) {
  const id = item.id;
  return {
    id,
    title: (item.title || '').trim() || (item.image_url ? 'Announcement' : 'Notice'),
    message: (item.message || '').trim(),
    imageUrl: item.image_url || null,
    priority: item.priority,
    date: item.created_at,
    read: isAnnouncementDismissedInClient(id),
    isActive: item.is_active !== false,
  };
}

export const ANNOUNCEMENT_IMAGE_MAX_BYTES = 5 * 1024 * 1024;
