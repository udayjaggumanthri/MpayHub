import React from 'react';
import { Link } from 'react-router-dom';

import bMnemonicPrimary from '../../assets/bbps/b-mnemonic-primary.svg';
import bMnemonicReverse from '../../assets/bbps/b-mnemonic-reverse.svg';
import bharatConnectPrimary from '../../assets/bbps/bharat-connect-primary.svg';
import bharatConnectReverse from '../../assets/bbps/bharat-connect-reverse.svg';
import bAssuredPrimary from '../../assets/bbps/b-assured-primary.svg';
import bAssuredReverse from '../../assets/bbps/b-assured-reverse.svg';
import { bAssuredLogoClass, bharatConnectLogoClass } from './bbpsLogoSizes';

const BharatConnectBranding = ({
  stage = 'stage2',
  title = '',
  surface = 'light',
  mnemonicHref = '/bill-payments/pay',
  mnemonicClickable = true,
  showMnemonic = true,
  logoSize = 'md',
  subtitle = 'Bill Pay · Pay Bill · Bill Payment',
  variant = 'default',
  emphasizeRightLogo = false,
}) => {
  const showBMnemonic = stage === 'stage1' && showMnemonic;
  const showBharatConnect = stage === 'stage1' || stage === 'stage2';
  const showBAssured = stage === 'stage3';
  const useReverse = String(surface || '').toLowerCase() === 'dark';
  const assets = {
    mnemonic: useReverse ? bMnemonicReverse : bMnemonicPrimary,
    bharatConnect: useReverse ? bharatConnectReverse : bharatConnectPrimary,
    bAssured: useReverse ? bAssuredReverse : bAssuredPrimary,
  };
  const isLarge = String(logoSize || '').toLowerCase() === 'lg';
  const isCompact = String(variant || '').toLowerCase() === 'compact';
  const isStage1 = stage === 'stage1';
  const shouldEmphasizeRightLogo = emphasizeRightLogo || stage === 'stage2';
  const mnemonicClass = isStage1
    ? isLarge
      ? 'h-14 w-14 object-contain'
      : 'h-12 w-12 object-contain'
    : isLarge
      ? 'h-11 w-11 object-contain'
      : 'h-9 w-9 object-contain';

  const mnemonicNode = <img src={assets.mnemonic} alt="Bharat Connect mnemonic logo" className={mnemonicClass} />;
  const subtitleText = String(subtitle || '').trim();

  return (
    <div className={`mb-4 flex items-center justify-between gap-4 ${isCompact ? 'flex-wrap' : ''}`}>
      <div className={`flex min-w-0 ${isStage1 ? 'items-start gap-3' : 'items-center gap-2'}`}>
        {showBMnemonic &&
          (mnemonicClickable ? (
            <Link to={mnemonicHref} aria-label="Go to BBPS categories">
              {mnemonicNode}
            </Link>
          ) : (
            mnemonicNode
          ))}
        <div className="min-w-0">
          {title && <h1 className="text-xl font-semibold text-gray-900">{title}</h1>}
          {isStage1 && subtitleText && (
            <p className="mt-1 text-xs font-medium tracking-wide text-slate-600 sm:text-sm">{subtitleText}</p>
          )}
        </div>
      </div>
      {showBharatConnect && (
        <div
          className={
            shouldEmphasizeRightLogo
              ? 'ml-auto rounded-xl border border-blue-200 bg-gradient-to-br from-blue-50 via-indigo-50 to-sky-50 px-3.5 py-2.5 shadow-md'
              : 'ml-auto shrink-0'
          }
        >
          <img src={assets.bharatConnect} alt="Bharat Connect logo" className={bharatConnectLogoClass} />
        </div>
      )}
      {showBAssured && (
        <img src={assets.bAssured} alt="B Assured logo" className={`ml-auto shrink-0 ${bAssuredLogoClass}`} />
      )}
    </div>
  );
};

export default BharatConnectBranding;
