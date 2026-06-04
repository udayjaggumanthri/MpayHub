import React from 'react';

import { bbpsLogoAssets } from './bbpsLogoAssets';
import {
  bAssuredFrameStyle,
  bAssuredImgProps,
  bbpsLogoFrameClass,
  bharatConnectFrameStyle,
  bharatConnectImgProps,
} from './bbpsLogoSizes';

/**
 * Bharat Connect — fixed 83×30 px frame; artwork fills frame (uniform scale, no stretch).
 */
export const BharatConnectLogo = ({
  reverse = false,
  isolated = true,
  className = '',
  alt = 'Bharat Connect logo',
  /** 'cover' = BBPS spec fill; 'contain' = full mark visible inside 83×30 frame */
  fit = 'cover',
}) => {
  const src = reverse ? bbpsLogoAssets.bharatConnectReverse : bbpsLogoAssets.bharatConnectPrimary;
  const imgClass =
    fit === 'contain'
      ? 'block h-full w-full max-w-none object-contain object-center'
      : bharatConnectImgProps.className;
  const img = (
    <img
      src={src}
      alt={alt}
      width={bharatConnectImgProps.width}
      height={bharatConnectImgProps.height}
      decoding={bharatConnectImgProps.decoding}
      className={imgClass}
      draggable={false}
    />
  );

  const frameClass = `${bbpsLogoFrameClass} ${className}`.trim();

  if (!isolated) {
    return (
      <span className={frameClass} style={bharatConnectFrameStyle}>
        {img}
      </span>
    );
  }

  return (
    <span className={frameClass} style={bharatConnectFrameStyle} role="img" aria-label={alt}>
      {img}
    </span>
  );
};

/**
 * B Assured — fixed 130×120 px, original proportions (object-contain).
 */
export const BAssuredLogo = ({
  reverse = false,
  isolated = true,
  className = '',
  alt = 'B Assured logo',
}) => {
  const src = reverse ? bbpsLogoAssets.bAssuredReverse : bbpsLogoAssets.bAssuredPrimary;
  const img = <img src={src} alt={alt} {...bAssuredImgProps} draggable={false} />;

  const frameClass = `${bbpsLogoFrameClass} ${className}`.trim();

  if (!isolated) {
    return (
      <span className={frameClass} style={bAssuredFrameStyle}>
        {img}
      </span>
    );
  }

  return (
    <span className={frameClass} style={bAssuredFrameStyle} role="img" aria-label={alt}>
      {img}
    </span>
  );
};
