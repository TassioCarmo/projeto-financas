/**
 * Gerenciamento de tema claro/escuro.
 * Persiste preferência em localStorage (chave: financas-theme).
 */
(function () {
    'use strict';

    var STORAGE_KEY = 'financas-theme';

    function getSystemTheme() {
        return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }

    function getStoredTheme() {
        try {
            return localStorage.getItem(STORAGE_KEY);
        } catch (e) {
            return null;
        }
    }

    function getTheme() {
        return getStoredTheme() || getSystemTheme();
    }

    function applyTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        document.querySelectorAll('.theme-toggle').forEach(function (btn) {
            btn.setAttribute('aria-pressed', theme === 'dark' ? 'true' : 'false');
            btn.setAttribute('aria-label', theme === 'dark' ? 'Ativar modo claro' : 'Ativar modo escuro');
        });
    }

    function setTheme(theme) {
        try {
            localStorage.setItem(STORAGE_KEY, theme);
        } catch (e) { /* storage indisponível */ }
        applyTheme(theme);
        window.dispatchEvent(new CustomEvent('themechange', { detail: { theme: theme } }));
    }

    function toggleTheme() {
        var current = document.documentElement.getAttribute('data-theme') || getTheme();
        setTheme(current === 'dark' ? 'light' : 'dark');
    }

    function initThemeToggle() {
        document.querySelectorAll('.theme-toggle').forEach(function (btn) {
            btn.addEventListener('click', toggleTheme);
        });
    }

    // Aplicar tema salvo imediatamente (também chamado inline no head)
    applyTheme(getTheme());

    window.FinancasTheme = {
        get: getTheme,
        set: setTheme,
        toggle: toggleTheme,
        init: initThemeToggle
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initThemeToggle);
    } else {
        initThemeToggle();
    }

    // Reagir a mudança de preferência do sistema (se usuário não definiu manualmente)
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function (e) {
        if (!getStoredTheme()) {
            applyTheme(e.matches ? 'dark' : 'light');
            window.dispatchEvent(new CustomEvent('themechange', {
                detail: { theme: e.matches ? 'dark' : 'light' }
            }));
        }
    });
})();
