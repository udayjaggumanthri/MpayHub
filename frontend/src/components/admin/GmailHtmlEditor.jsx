import React, { useCallback, useEffect, useRef } from 'react';
import {
  FaBold,
  FaItalic,
  FaUnderline,
  FaListOl,
  FaListUl,
  FaLink,
  FaEraser,
} from 'react-icons/fa6';

const exec = (command, value = null) => {
  document.execCommand(command, false, value);
};

const GmailHtmlEditor = ({ value, onChange, placeholder = 'Compose email body…', minHeight = 320 }) => {
  const editorRef = useRef(null);
  const lastHtml = useRef('');

  const emitChange = useCallback(() => {
    const html = editorRef.current?.innerHTML ?? '';
    if (html !== lastHtml.current) {
      lastHtml.current = html;
      onChange(html);
    }
  }, [onChange]);

  useEffect(() => {
    const el = editorRef.current;
    if (!el) return;
    const html = value || '';
    if (html !== lastHtml.current) {
      el.innerHTML = html;
      lastHtml.current = html;
    }
  }, [value]);

  const handleToolbar = (e, command, val = null) => {
    e.preventDefault();
    editorRef.current?.focus();
    exec(command, val);
    emitChange();
  };

  const insertLink = (e) => {
    e.preventDefault();
    editorRef.current?.focus();
    const url = window.prompt('Enter URL', 'https://');
    if (url) {
      exec('createLink', url);
      emitChange();
    }
  };

  const btnClass =
    'p-2 rounded-md text-gray-600 hover:bg-gray-200 hover:text-gray-900 transition-colors';

  return (
    <div className="mpay-paper gmail-editor rounded-lg border border-gray-200 bg-white overflow-hidden shadow-inner">
      <div className="flex flex-wrap items-center gap-0.5 px-2 py-1.5 border-b border-gray-200 bg-gray-50">
        <button type="button" className={btnClass} title="Bold" onMouseDown={(e) => handleToolbar(e, 'bold')}>
          <FaBold className="w-3.5 h-3.5" />
        </button>
        <button type="button" className={btnClass} title="Italic" onMouseDown={(e) => handleToolbar(e, 'italic')}>
          <FaItalic className="w-3.5 h-3.5" />
        </button>
        <button
          type="button"
          className={btnClass}
          title="Underline"
          onMouseDown={(e) => handleToolbar(e, 'underline')}
        >
          <FaUnderline className="w-3.5 h-3.5" />
        </button>
        <span className="w-px h-5 bg-gray-300 mx-1" />
        <button
          type="button"
          className={btnClass}
          title="Numbered list"
          onMouseDown={(e) => handleToolbar(e, 'insertOrderedList')}
        >
          <FaListOl className="w-3.5 h-3.5" />
        </button>
        <button
          type="button"
          className={btnClass}
          title="Bullet list"
          onMouseDown={(e) => handleToolbar(e, 'insertUnorderedList')}
        >
          <FaListUl className="w-3.5 h-3.5" />
        </button>
        <span className="w-px h-5 bg-gray-300 mx-1" />
        <button type="button" className={btnClass} title="Insert link" onMouseDown={insertLink}>
          <FaLink className="w-3.5 h-3.5" />
        </button>
        <button
          type="button"
          className={btnClass}
          title="Clear formatting"
          onMouseDown={(e) => handleToolbar(e, 'removeFormat')}
        >
          <FaEraser className="w-3.5 h-3.5" />
        </button>
      </div>
      <div
        ref={editorRef}
        className="gmail-editor-body px-4 py-3 text-[15px] text-gray-800 leading-relaxed outline-none"
        style={{ minHeight }}
        contentEditable
        suppressContentEditableWarning
        role="textbox"
        aria-multiline="true"
        data-placeholder={placeholder}
        onInput={emitChange}
        onBlur={emitChange}
      />
    </div>
  );
};

export default GmailHtmlEditor;
