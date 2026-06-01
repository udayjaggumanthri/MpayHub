import React from 'react';
import BbpsBillsList from './BbpsBillsList';

/** Retailer / agent view — own bill payments only. */
const MyBills = () => (
  <BbpsBillsList
    variant="page"
    title="My Bills"
    subtitle="View your bill payment transaction history"
    defaultScope="self"
    showCsvExport
  />
);

export default MyBills;
