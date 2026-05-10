import React from 'react';
import { Link } from 'react-router-dom';
import BharatConnectBranding from '../BharatConnectBranding';

const Card = ({ title, to, buttonClass, label }) => (
  <div className="bg-white rounded-xl shadow-md border border-violet-100/90 p-8 flex flex-col items-center text-center min-h-[220px] justify-between">
    <h2 className="text-lg font-semibold text-indigo-950">{title}</h2>
    <Link
      to={to}
      className={`mt-6 inline-flex items-center justify-center px-10 py-3 rounded-full text-white font-medium shadow-sm transition hover:opacity-95 w-full max-w-xs ${buttonClass}`}
    >
      {label}
    </Link>
  </div>
);

const ComplaintsHub = () => (
  <div className="max-w-6xl mx-auto">
    <div className="bg-white rounded-xl border border-violet-100 shadow-sm p-6 mb-8">
      <BharatConnectBranding stage="stage2" title="COMPLAINT MANAGEMENT" />
      <p className="text-sm text-gray-600 max-w-2xl">
        Register a complaint, track an existing case, search your transactions, or review your complaint history.
      </p>
    </div>

    <div className="grid md:grid-cols-2 xl:grid-cols-4 gap-6">
      <Card title="Complaint Registration" to="register" buttonClass="bg-blue-600" label="Register Now" />
      <Card title="Complaint Tracking" to="track" buttonClass="bg-emerald-600" label="Track Complaint" />
      <Card title="Search Transaction" to="search-transaction" buttonClass="bg-amber-500" label="Search Now" />
      <Card title="Complaint History" to="history" buttonClass="bg-slate-700" label="View History" />
    </div>
  </div>
);

export default ComplaintsHub;
