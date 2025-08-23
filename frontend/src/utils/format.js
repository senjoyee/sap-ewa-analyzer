import React from 'react';
import { Tooltip } from '@fluentui/react-components';

/**
 * Format a date-like input to DD-MM-YYYY with leading zeros and hyphen separators.
 * Accepts Date, ISO-like string, or timestamp.
 */
export const formatDateDDMMYYYY = (input) => {
  if (input === null || input === undefined || input === '') return '';
  const d = input instanceof Date ? input : new Date(input);
  if (isNaN(d.getTime())) return String(input);
  const dd = String(d.getDate()).padStart(2, '0');
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const yyyy = d.getFullYear();
  return `${dd}-${mm}-${yyyy}`;
};

/**
 * Format numbers with thousands separators and dot decimal.
 * Falls back to the original value if not a finite number.
 */
export const formatNumber = (value, options) => {
  if (value === null || value === undefined || value === '') return String(value ?? '');
  const num = typeof value === 'number' ? value : Number(String(value).replace(/,/g, ''));
  if (!isFinite(num)) return String(value);
  const formatter = new Intl.NumberFormat('en-US', options);
  return formatter.format(num);
};

const isIsoDateLike = (v) => typeof v === 'string' && /^\d{4}-\d{2}-\d{2}/.test(v);

/**
 * Heuristic display formatter for table cells and labels.
 * - Dates (Date or ISO-like strings) -> DD-MM-YYYY
 * - Numbers -> grouped with dot decimal
 * - Otherwise returns the original value
 */
export const formatDisplay = (value) => {
  if (value instanceof Date || isIsoDateLike(value)) {
    return formatDateDDMMYYYY(value);
  }
  if (typeof value === 'number') {
    return formatNumber(value);
  }
  if (typeof value === 'string') {
    const pure = value.trim();
    if (/^\d+(\.\d+)?$/.test(pure)) {
      return formatNumber(Number(pure));
    }
  }
  return value;
};

/**
 * Inline text with ellipsis and a tooltip that reveals full content.
 * Does not alter layout other than applying text-overflow.
 */
export const TruncatedText = ({ text, className, maxWidth = '100%', tooltipContent }) => {
  if (text === null || text === undefined) return null;
  const full = String(text);
  return (
    <Tooltip content={tooltipContent ?? full} relationship="label">
      <span
        className={className}
        title={full}
        style={{
          display: 'inline-block',
          maxWidth,
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          verticalAlign: 'bottom',
        }}
      >
        {full}
      </span>
    </Tooltip>
  );
};
