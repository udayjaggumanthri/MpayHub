/**
 * Official BBPS partner logo dimensions (px). Use only via BbpsPartnerLogos.
 */
export const BBPS_BHARAT_CONNECT_LOGO = { width: 83, height: 30 };
export const BBPS_B_ASSURED_LOGO = { width: 130, height: 120 };

/** Fixed frame; transparent — no merge with page background. */
export const bbpsLogoFrameClass =
  'inline-flex shrink-0 items-center justify-center overflow-hidden bg-transparent p-0 m-0 leading-none';

const logoFrameStyleBase = {
  boxSizing: 'border-box',
  isolation: 'isolate',
  position: 'relative',
  zIndex: 2,
  flexShrink: 0,
  background: 'transparent',
  padding: 0,
  margin: 0,
  lineHeight: 0,
};

export const bharatConnectFrameStyle = {
  ...logoFrameStyleBase,
  width: `${BBPS_BHARAT_CONNECT_LOGO.width}px`,
  height: `${BBPS_BHARAT_CONNECT_LOGO.height}px`,
  minWidth: `${BBPS_BHARAT_CONNECT_LOGO.width}px`,
  minHeight: `${BBPS_BHARAT_CONNECT_LOGO.height}px`,
  maxWidth: `${BBPS_BHARAT_CONNECT_LOGO.width}px`,
  maxHeight: `${BBPS_BHARAT_CONNECT_LOGO.height}px`,
};

export const bAssuredFrameStyle = {
  ...logoFrameStyleBase,
  width: `${BBPS_B_ASSURED_LOGO.width}px`,
  height: `${BBPS_B_ASSURED_LOGO.height}px`,
  minWidth: `${BBPS_B_ASSURED_LOGO.width}px`,
  minHeight: `${BBPS_B_ASSURED_LOGO.height}px`,
  maxWidth: `${BBPS_B_ASSURED_LOGO.width}px`,
  maxHeight: `${BBPS_B_ASSURED_LOGO.height}px`,
};

/**
 * B-Connect SVG viewBox is wider than 83:30 — cover fills the spec frame without stretching.
 * B Assured aspect is close to 130:120 — contain preserves the mark.
 */
export const bharatConnectImgClass =
  'block h-full w-full max-w-none object-cover object-left';

export const bAssuredImgClass =
  'block h-full w-full max-w-none object-contain object-center';

export const bharatConnectImgProps = {
  width: BBPS_BHARAT_CONNECT_LOGO.width,
  height: BBPS_BHARAT_CONNECT_LOGO.height,
  className: bharatConnectImgClass,
  decoding: 'sync',
};

export const bAssuredImgProps = {
  width: BBPS_B_ASSURED_LOGO.width,
  height: BBPS_B_ASSURED_LOGO.height,
  className: bAssuredImgClass,
  decoding: 'sync',
};

/** Reserved column width for header layouts (prevents overlap with titles). */
export const bharatConnectLogoSlotStyle = {
  width: `${BBPS_BHARAT_CONNECT_LOGO.width}px`,
  minWidth: `${BBPS_BHARAT_CONNECT_LOGO.width}px`,
  height: `${BBPS_BHARAT_CONNECT_LOGO.height}px`,
  minHeight: `${BBPS_BHARAT_CONNECT_LOGO.height}px`,
  flexShrink: 0,
};

export const bAssuredLogoSlotStyle = {
  width: `${BBPS_B_ASSURED_LOGO.width}px`,
  minWidth: `${BBPS_B_ASSURED_LOGO.width}px`,
  height: `${BBPS_B_ASSURED_LOGO.height}px`,
  minHeight: `${BBPS_B_ASSURED_LOGO.height}px`,
  flexShrink: 0,
};
