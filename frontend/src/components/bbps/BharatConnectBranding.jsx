import React from 'react';

const LOGO_SIZE = 'h-[35px]';

const BharatConnectBranding = ({ stage = 'stage2', title = '' }) => {
  const showBMnemonic = stage === 'stage1';
  const showBharatConnect = stage === 'stage2';
  const showBAssured = stage === 'stage3';

  return (
    <div className="flex items-center justify-between mb-4">
      <div className="flex items-center gap-2">
        {showBMnemonic && (
          <div className={`${LOGO_SIZE} w-[35px] rounded bg-blue-700 text-white text-xl font-bold flex items-center justify-center`}>
            B
          </div>
        )}
        {title && <h1 className="text-xl font-semibold text-gray-900">{title}</h1>}
      </div>
      {showBharatConnect && (
        <div className={`${LOGO_SIZE} w-[83px] rounded border border-blue-200 bg-white text-[11px] font-semibold text-blue-700 flex items-center justify-center`}>
          Bharat Connect
        </div>
      )}
      {showBAssured && (
        <div className="h-[35px] w-[130px] rounded border border-emerald-200 bg-white text-[11px] font-semibold text-emerald-700 flex items-center justify-center">
          B Assured
        </div>
      )}
    </div>
  );
};

export default BharatConnectBranding;
