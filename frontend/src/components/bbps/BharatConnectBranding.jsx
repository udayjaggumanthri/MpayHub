import React from 'react';

import bMnemonicPrimary from '../../assets/bbps/b-mnemonic-primary.svg';
import bMnemonicReverse from '../../assets/bbps/b-mnemonic-reverse.svg';
import bharatConnectPrimary from '../../assets/bbps/bharat-connect-primary.svg';
import bharatConnectReverse from '../../assets/bbps/bharat-connect-reverse.svg';
import bAssuredPrimary from '../../assets/bbps/b-assured-primary.svg';
import bAssuredReverse from '../../assets/bbps/b-assured-reverse.svg';

const BharatConnectBranding = ({
  stage = 'stage2',
  title = '',
  surface = 'light',
  mnemonicHref = '/bill-payments/pay',
  mnemonicClickable = true,
  logoSize = 'md',
}) => {
  const showBMnemonic = stage === 'stage1';
  const showBharatConnect = stage === 'stage1' || stage === 'stage2';
  const showBAssured = stage === 'stage3';
  const useReverse = String(surface || '').toLowerCase() === 'dark';
  const assets = {
    mnemonic: useReverse ? bMnemonicReverse : bMnemonicPrimary,
    bharatConnect: useReverse ? bharatConnectReverse : bharatConnectPrimary,
    bAssured: useReverse ? bAssuredReverse : bAssuredPrimary,
  };
  const isLarge = String(logoSize || '').toLowerCase() === 'lg';
  const mnemonicClass = isLarge ? 'h-11 w-11 object-contain' : 'h-9 w-9 object-contain';
  const logoClass = isLarge ? 'h-12 w-auto max-w-[220px] object-contain' : 'h-9 w-auto max-w-[170px] object-contain';

  const mnemonicNode = (
    <img
      src={assets.mnemonic}
      alt="Bharat Connect mnemonic logo"
      className={mnemonicClass}
    />
  );

  return (
    <div className="flex items-center justify-between mb-4">
      <div className="flex items-center gap-2">
        {showBMnemonic && (
          mnemonicClickable ? (
            <a href={mnemonicHref} aria-label="Go to BBPS categories">
              {mnemonicNode}
            </a>
          ) : mnemonicNode
        )}
        {title && <h1 className="text-xl font-semibold text-gray-900">{title}</h1>}
      </div>
      {showBharatConnect && (
        <img
          src={assets.bharatConnect}
          alt="Bharat Connect logo"
          className={logoClass}
        />
      )}
      {showBAssured && (
        <img
          src={assets.bAssured}
          alt="B Assured logo"
          className={logoClass}
        />
      )}
    </div>
  );
};

export default BharatConnectBranding;
