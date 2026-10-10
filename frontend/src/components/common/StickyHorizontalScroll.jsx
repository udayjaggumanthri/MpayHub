import React from 'react';

/**
 * Report tables scroll inside this frame. The sideways bar stays on the
 * bottom edge of the frame, and the page itself does not shift left or right.
 */
const StickyHorizontalScroll = ({ children, className = '' }) => (
  <div className={`mpay-report-scroll min-w-0 max-w-full ${className}`}>{children}</div>
);

export default StickyHorizontalScroll;
