import React from 'react';

import { BAssuredLogo } from './BbpsPartnerLogos';
import { bAssuredLogoSlotStyle } from './bbpsLogoSizes';

/**
 * Receipt / confirmation header: B Assured logo only (130×120), optional title.
 */
const BAssuredReceiptHeader = ({ title = '', className = '', logoAlign = 'end' }) => {
  if (logoAlign === 'center') {
    return (
      <header className={`flex flex-col items-center gap-4 text-center ${className}`}>
        <div style={bAssuredLogoSlotStyle}>
          <BAssuredLogo isolated />
        </div>
        {title ? <h2 className="text-xl font-semibold text-gray-900">{title}</h2> : null}
      </header>
    );
  }

  const alignClass = logoAlign === 'start' ? 'justify-start' : 'justify-between';

  return (
    <header className={`flex flex-wrap items-center gap-4 ${alignClass} ${className}`}>
      {title ? <h2 className="text-xl font-semibold text-gray-900 min-w-0 flex-1">{title}</h2> : null}
      <div style={bAssuredLogoSlotStyle}>
        <BAssuredLogo isolated />
      </div>
    </header>
  );
};

export default BAssuredReceiptHeader;
