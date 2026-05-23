import React from 'react';
import { Link } from 'react-router-dom';

import bMnemonicPrimary from '../../assets/bbps/b-mnemonic-primary.svg';
import bMnemonicReverse from '../../assets/bbps/b-mnemonic-reverse.svg';
import { BharatConnectLogo, BAssuredLogo } from './BbpsPartnerLogos';
import { bAssuredLogoSlotStyle, bharatConnectLogoSlotStyle } from './bbpsLogoSizes';

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
}) => {
  const showBMnemonic = stage === 'stage1' && showMnemonic;
  const showBharatConnect = stage === 'stage1' || stage === 'stage2';
  const showBAssured = stage === 'stage3';
  const useReverse = String(surface || '').toLowerCase() === 'dark';
  const isLarge = String(logoSize || '').toLowerCase() === 'lg';
  const isCompact = String(variant || '').toLowerCase() === 'compact';
  const isStage1 = stage === 'stage1';

  const logoSlotStyle = showBAssured ? bAssuredLogoSlotStyle : bharatConnectLogoSlotStyle;
  const gridColsClass = showBAssured
    ? 'sm:grid-cols-[minmax(0,1fr)_130px]'
    : 'sm:grid-cols-[minmax(0,1fr)_83px]';

  const mnemonicClass = isStage1
    ? isLarge
      ? 'h-14 w-14 shrink-0 object-contain'
      : 'h-12 w-12 shrink-0 object-contain'
    : isLarge
      ? 'h-11 w-11 shrink-0 object-contain'
      : 'h-9 w-9 shrink-0 object-contain';

  const mnemonicSrc = useReverse ? bMnemonicReverse : bMnemonicPrimary;
  const mnemonicNode = (
    <img src={mnemonicSrc} alt="" aria-hidden className={mnemonicClass} draggable={false} />
  );
  const subtitleText = String(subtitle || '').trim();

  const rightLogo = showBharatConnect ? (
    <BharatConnectLogo reverse={useReverse} isolated />
  ) : showBAssured ? (
    <BAssuredLogo reverse={useReverse} isolated />
  ) : null;

  return (
    <header
      className={`mb-4 grid w-full gap-x-4 gap-y-3 grid-cols-1 ${
        rightLogo ? `${gridColsClass} sm:items-center` : ''
      } ${isCompact ? '' : ''}`}
    >
      <div className={`flex min-w-0 items-center gap-3 ${isStage1 ? 'items-start' : ''}`}>
        {showBMnemonic &&
          (mnemonicClickable ? (
            <Link to={mnemonicHref} aria-label="Go to BBPS categories" className="shrink-0">
              {mnemonicNode}
            </Link>
          ) : (
            mnemonicNode
          ))}
        <div className="min-w-0 flex-1">
          {title ? <h1 className="text-xl font-semibold text-gray-900 leading-tight">{title}</h1> : null}
          {isStage1 && subtitleText ? (
            <p className="mt-1 text-xs font-medium tracking-wide text-slate-600 sm:text-sm">{subtitleText}</p>
          ) : null}
        </div>
      </div>

      {rightLogo ? (
        <div className="flex shrink-0 items-center justify-end sm:justify-self-end" style={logoSlotStyle}>
          {rightLogo}
        </div>
      ) : null}
    </header>
  );
};

export default BharatConnectBranding;
