import React, { useState, useRef, useEffect } from 'react';
import './CustomSelect.css';

export function CustomSelect({ value, onChange, options, placeholder = "Select...", className = "" }) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef(null);

  useEffect(() => {
    function handleClickOutside(event) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

  const handleSelect = (optionValue) => {
    onChange(optionValue);
    setIsOpen(false);
  };

  const selectedOption = options.find(opt => opt.value === value);

  return (
    <div className={`custom-select-container ${className}`} ref={dropdownRef} onClick={(e) => e.stopPropagation()}>
      <div 
        className={`custom-select-trigger ${isOpen ? 'open' : ''}`}
        onClick={() => setIsOpen(!isOpen)}
      >
        <span>{selectedOption ? selectedOption.label : placeholder}</span>
        <svg 
          width="12" 
          height="12" 
          viewBox="0 0 24 24" 
          fill="none" 
          stroke="currentColor" 
          strokeWidth="2" 
          strokeLinecap="round" 
          strokeLinejoin="round" 
          className="custom-select-icon"
        >
          <path d="m6 9 6 6 6-6"/>
        </svg>
      </div>
      {isOpen && (
        <div className="custom-select-content">
          {options.map(option => (
            <div 
              key={option.value} 
              className={`custom-select-item ${value === option.value ? 'selected' : ''}`}
              onClick={() => handleSelect(option.value)}
            >
              <span className="custom-select-item-text">{option.label}</span>
              {value === option.value && (
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="custom-select-check">
                  <path d="M20 6 9 17l-5-5"/>
                </svg>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
