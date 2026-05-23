import React from 'react';
import { Route, Routes } from 'react-router-dom';
import SmsProfileList from './SmsProfileList';
import SmsProfileForm from './SmsProfileForm';
import SmsEventTemplates from './SmsEventTemplates';

const SmsSettings = () => (
  <Routes>
    <Route index element={<SmsProfileList />} />
    <Route path="new" element={<SmsProfileForm />} />
    <Route path="templates" element={<SmsEventTemplates />} />
    <Route path=":id/edit" element={<SmsProfileForm />} />
  </Routes>
);

export default SmsSettings;
