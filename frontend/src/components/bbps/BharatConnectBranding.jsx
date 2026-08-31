import React from 'react';
import { Link } from 'react-router-dom';

import bMnemonicPrimary from '../../assets/bbps/b-mnemonic-primary.svg';
import bMnemonicReverse from '../../assets/bbps/b-mnemonic-reverse.svg';
import { BharatConnectLogo, BAssuredLogo } from './BbpsPartnerLogos';
import {
  BBPS_BHARAT_CONNECT_LOGO,
  bAssuredLogoSlotStyle,
  bharatConnectLogoSlotStyle,
  bharatConnectLogoTailwindSize,
} from './bbpsLogoSizes';

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
  /** Pin B-Connect logo (83×30) to viewport top-right; does not scroll with page content */
  fixedLogo = false,
}) => {
  const showBMnemonic = stage === 'stage1' && showMnemonic;
  const showBharatConnect = stage === 'stage1' || stage === 'stage2';
  const showBAssured = stage === 'stage3';
  const useReverse = String(surface || '').toLowerCase() === 'dark';
  const isLarge = String(logoSize || '').toLowerCase() === 'lg';
  const isCompact = String(variant || '').toLowerCase() === 'compact';
  const isStage1 = stage === 'stage1';

  const logoSlotStyle = showBAssured ? bAssuredLogoSlotStyle : bharatConnectLogoSlotStyle;
  const bConnectColWidth = `${BBPS_BHARAT_CONNECT_LOGO.width}px`;

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

  const useInFlowLogo = Boolean(rightLogo) && !fixedLogo;
  const gridColsClass = showBAssured
    ? 'sm:grid-cols-[minmax(0,1fr)_130px]'
    : useInFlowLogo
      ? `sm:grid-cols-[minmax(0,1fr)_${bConnectColWidth}]`
      : '';

  const titleReserveClass =
    fixedLogo && showBharatConnect ? 'pr-[5.75rem] sm:pr-[5.75rem]' : '';

  return (
    <>
      {fixedLogo && showBharatConnect && rightLogo ? (
        <div
          className="pointer-events-none fixed right-4 top-14 z-30 sm:right-6 sm:top-16 lg:right-8"
          style={bharatConnectLogoSlotStyle}
        >
          {rightLogo}
        </div>
      ) : null}
      <header
        className={`grid w-full grid-cols-1 gap-x-4 gap-y-2 ${
          isCompact ? 'mb-0' : 'mb-4 gap-y-3'
        } ${useInFlowLogo ? `${gridColsClass} sm:items-center` : ''}`}
      >
      <div
        className={`flex min-w-0 items-center gap-2.5 sm:gap-3 ${isStage1 && !isCompact ? 'items-start' : 'items-center'} ${titleReserveClass}`}
      >
        {showBMnemonic &&
          (mnemonicClickable ? (
            <Link to={mnemonicHref} aria-label="Go to BBPS categories" className="shrink-0">
              {mnemonicNode}
            </Link>
          ) : (
            mnemonicNode
          ))}
        <div className="min-w-0 flex-1">
          {title ? (
            <h1
              className={`font-semibold text-gray-900 dark:text-slate-100 leading-tight ${
                isCompact ? 'text-lg sm:text-xl' : 'text-xl'
              }`}
            >
              {title}
            </h1>
          ) : null}
          {subtitleText ? (
            <p
              className={`mt-1 text-xs sm:text-sm ${
                isStage1 ? 'font-medium tracking-wide text-slate-600 dark:text-slate-400' : 'text-gray-500 dark:text-slate-400'
              }`}
            >
              {subtitleText}
            </p>
          ) : null}
        </div>
      </div>

      {useInFlowLogo ? (
        <div
          className={`flex shrink-0 items-center justify-end sm:justify-self-end ${showBharatConnect ? bharatConnectLogoTailwindSize : ''}`}
          style={logoSlotStyle}
        >
          {rightLogo}
        </div>
      ) : null}
    </header>
    </>
  );
};

export default BharatConnectBranding;
