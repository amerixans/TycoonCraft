/**
 * Format numbers for display
 * - Numbers >= 1 trillion: "1.000 trillion"
 * - Numbers >= 1 million: "1.000 million"
 * - Numbers < 1 million: "1,000" (with commas)
 */
export function formatNumber(value) {
  const num = parseFloat(value);
  
  if (isNaN(num)) return '0';
  
  // 1 trillion or more
  if (num >= 1_000_000_000_000) {
    return (num / 1_000_000_000_000).toFixed(3) + ' trillion';
  }
  
  // 1 million or more
  if (num >= 1_000_000) {
    return (num / 1_000_000).toFixed(3) + ' million';
  }
  
  // Less than 1 million - add commas
  return Math.floor(num).toLocaleString('en-US');
}
