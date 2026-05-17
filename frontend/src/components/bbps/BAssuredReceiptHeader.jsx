import React from 'react';

import bAssuredPrimary from '../../assets/bbps/b-assured-primary.svg';
import { bAssuredLogoClass } from './bbpsLogoSizes';

/**
 * Receipt / confirmation header: B Assured logo only (130×120), optional title.
 */
const BAssuredReceiptHeader = ({ title = '', className = '', logoAlign = 'end' }) => {
  const alignClass =
    logoAlign === 'center' ? 'justify-center' : logoAlign === 'start' ? 'justify-start' : 'justify-between';

  return (
    <div className={`flex flex-wrap items-center gap-4 ${alignClass} ${className}`}>
      {title ? <h2 className="text-xl font-semibold text-gray-900">{title}</h2> : null}
      <img src={bAssuredPrimary} alt="B Assured logo" className={bAssuredLogoClass} />
    </div>
  );
};

export default BAssuredReceiptHeader;
