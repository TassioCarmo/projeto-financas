/**
 * Cores e opções de tema para Chart.js, sincronizadas com CSS variables.
 */
(function () {
    'use strict';

    function cssVar(name) {
        return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    }

    window.getChartColors = function () {
        return {
            green: cssVar('--chart-green'),
            red: cssVar('--chart-red'),
            blue: cssVar('--chart-blue'),
            purple: cssVar('--chart-purple'),
            orange: cssVar('--chart-orange'),
            teal: cssVar('--chart-teal'),
            pink: cssVar('--chart-pink'),
            indigo: cssVar('--chart-indigo'),
            brown: cssVar('--chart-brown'),
            gray: cssVar('--chart-gray'),
            grid: cssVar('--chart-grid'),
            text: cssVar('--chart-text'),
            palette: [
                cssVar('--chart-green'),
                cssVar('--chart-blue'),
                cssVar('--chart-orange'),
                cssVar('--chart-purple'),
                cssVar('--chart-red'),
                cssVar('--chart-teal'),
                cssVar('--chart-brown'),
                cssVar('--chart-gray'),
                cssVar('--chart-pink'),
                cssVar('--chart-indigo')
            ]
        };
    };

    window.getChartOptions = function (overrides) {
        var colors = window.getChartColors();
        var oculto = window.FinancasBalancePrivacy && window.FinancasBalancePrivacy.isHidden();
        var base = {
            responsive: true,
            plugins: {
                legend: {
                    labels: { color: colors.text }
                },
                tooltip: {
                    callbacks: {
                        label: function (context) {
                            if (oculto) {
                                return '••••';
                            }
                            var label = context.dataset.label || '';
                            if (label) {
                                label += ': ';
                            }
                            if (context.parsed.y !== null && context.parsed.y !== undefined) {
                                label += window.FinancasBalancePrivacy
                                    ? window.FinancasBalancePrivacy.formatarMoeda(context.parsed.y)
                                    : context.parsed.y;
                            }
                            return label;
                        }
                    }
                }
            },
            scales: {
                x: {
                    ticks: { color: colors.text },
                    grid: { color: colors.grid }
                },
                y: {
                    ticks: {
                        color: colors.text,
                        callback: function (value) {
                            if (oculto) {
                                return '••••';
                            }
                            return value;
                        }
                    },
                    grid: { color: colors.grid }
                }
            }
        };

        if (!overrides) return base;

        // Merge superficial para uso simples
        if (overrides.plugins) {
            Object.assign(base.plugins, overrides.plugins);
        }
        if (overrides.scales) {
            Object.assign(base.scales, overrides.scales);
        }
        return Object.assign(base, overrides);
    };
})();
