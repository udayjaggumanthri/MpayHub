import React, { useState } from 'react';
import { FaEye, FaEyeSlash } from 'react-icons/fa';

const PasswordField = ({ className = '', ...props }) => {
  const [visible, setVisible] = useState(false);
  return (
    <div className="relative">
      <input
        {...props}
        type={visible ? 'text' : 'password'}
        className={`${className} pr-12`}
      />
      <button
        type="button"
        className="absolute inset-y-0 right-0 px-3 flex items-center text-gray-400 hover:text-gray-600"
        aria-label={visible ? 'Hide password' : 'Show password'}
        onClick={() => setVisible((current) => !current)}
      >
        {visible ? <FaEyeSlash size={18} /> : <FaEye size={18} />}
      </button>
    </div>
  );
};

export default PasswordField;
