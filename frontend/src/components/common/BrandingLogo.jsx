import React from 'react';
import { useBranding } from '../../context/AppearanceContext';

const BrandingLogo = ({
  className = '',
  alt,
  draggable = false,
  ...props
}) => {
  const { logoUrl, siteTitle } = useBranding();
  return (
    <img
      src={logoUrl}
      alt={alt || siteTitle}
      className={className}
      draggable={draggable}
      {...props}
    />
  );
};

export default BrandingLogo;
