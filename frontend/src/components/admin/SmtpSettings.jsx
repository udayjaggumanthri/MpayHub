import React from 'react';
import { Route, Routes } from 'react-router-dom';
import SmtpProfileList from './SmtpProfileList';
import SmtpProfileForm from './SmtpProfileForm';

const SmtpSettings = () => (
  <Routes>
    <Route index element={<SmtpProfileList />} />
    <Route path="new" element={<SmtpProfileForm />} />
    <Route path=":id/edit" element={<SmtpProfileForm />} />
  </Routes>
);

export default SmtpSettings;
