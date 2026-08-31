/**
 * Recharts renders SVG, which Tailwind `dark:` variants cannot reach. Chart
 * chrome (grid, axes, cursor) therefore has to be resolved in JS from the
 * active theme. Brand series colours are intentionally left alone so data keeps
 * the same identity in both themes.
 */
export function getChartTheme(isDark) {
  return {
    grid: isDark ? '#1e293b' : '#e2e8f0',
    axis: isDark ? '#94a3b8' : '#64748b',
    axisStrong: isDark ? '#cbd5e1' : '#475569',
    axisLine: isDark ? '#334155' : '#cbd5e1',
    cursor: isDark ? 'rgba(148, 163, 184, 0.12)' : 'rgba(15, 23, 42, 0.06)',
    legend: isDark ? '#cbd5e1' : '#475569',
    tooltip: {
      backgroundColor: isDark ? '#1e293b' : '#ffffff',
      border: `1px solid ${isDark ? '#334155' : '#e2e8f0'}`,
      borderRadius: 12,
      color: isDark ? '#f1f5f9' : '#0f172a',
      boxShadow: isDark
        ? '0 10px 15px -3px rgb(0 0 0 / 0.5)'
        : '0 10px 15px -3px rgb(0 0 0 / 0.1)',
    },
  };
}
