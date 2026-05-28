import React from 'react';
import { Route, Routes } from 'react-router-dom';
import EmailNotificationList from './EmailNotificationList';
import EmailTemplateEditor from './EmailTemplateEditor';

const EmailNotifications = () => (
  <Routes>
    <Route index element={<EmailNotificationList />} />
    <Route path="edit/*" element={<EmailTemplateEditor />} />
  </Routes>
);

export default EmailNotifications;
