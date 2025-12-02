/**
 * Parse a UTC timestamp string from the backend.
 * Backend sends timestamps without 'Z' suffix (e.g., "2025-12-02T04:36:16.844310")
 * so we need to add it to ensure JavaScript parses them as UTC.
 */
export function parseUTCDate(dateString) {
  if (!dateString) return null;
  // If the string doesn't end with 'Z' and doesn't have explicit timezone offset (+/-)
  // after the time portion, add 'Z' to indicate UTC
  if (!dateString.endsWith('Z') && !/[+-]\d{2}:?\d{2}$/.test(dateString)) {
    dateString = dateString + 'Z';
  }
  return new Date(dateString);
}

/**
 * Format a UTC timestamp to local time string.
 */
export function formatLocalDateTime(dateString) {
  const date = parseUTCDate(dateString);
  if (!date) return '';
  return date.toLocaleString();
}

/**
 * Format a UTC timestamp to local time only.
 */
export function formatLocalTime(dateString) {
  const date = parseUTCDate(dateString);
  if (!date) return '';
  return date.toLocaleTimeString();
}
