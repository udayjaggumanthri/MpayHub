import React, { useEffect, useState } from 'react';
import { assetUrlNeedsAuth, normalizeAssetUrl } from '../../utils/mediaUrl';

const authHeaders = () => {
  const token = localStorage.getItem('access_token') || sessionStorage.getItem('access_token');
  return token ? { Authorization: `Bearer ${token}` } : {};
};

/**
 * Renders images from /media/ (public) or /api/ (JWT) without mixed-content or auth issues.
 */
const AuthenticatedImage = ({ src, alt = '', className = '', fallback = null }) => {
  const [displayUrl, setDisplayUrl] = useState('');
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let objectUrl = '';

    const load = async () => {
      setFailed(false);
      setDisplayUrl('');
      const normalized = normalizeAssetUrl(src);
      if (!normalized) {
        setFailed(true);
        return;
      }
      if (!assetUrlNeedsAuth(normalized)) {
        if (!cancelled) setDisplayUrl(normalized);
        return;
      }
      try {
        const response = await fetch(normalized, { credentials: 'same-origin', headers: authHeaders() });
        if (!response.ok) throw new Error('Image unavailable');
        const blob = await response.blob();
        objectUrl = URL.createObjectURL(blob);
        if (!cancelled) setDisplayUrl(objectUrl);
      } catch {
        if (!cancelled) setFailed(true);
      }
    };

    load();
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [src]);

  if (failed) {
    return fallback || (
      <div className={`flex items-center justify-center bg-gray-100 text-xs text-gray-500 ${className}`}>
        Image unavailable
      </div>
    );
  }
  if (!displayUrl) {
    return (
      <div className={`flex items-center justify-center bg-gray-50 text-xs text-gray-400 ${className}`}>
        Loading…
      </div>
    );
  }
  return <img src={displayUrl} alt={alt} className={className} />;
};

export default AuthenticatedImage;
