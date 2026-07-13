/**
 * Ocultar/mostrar saldos por privacidade.
 * Persiste preferência em localStorage (chave: financas-hide-balances).
 */
(function () {
    'use strict';

    var STORAGE_KEY = 'financas-hide-balances';
    var MASCARA = 'R$ ••••••';

    function getStoredHidden() {
        try {
            return localStorage.getItem(STORAGE_KEY) === 'true';
        } catch (e) {
            return false;
        }
    }

    function isHidden() {
        return document.documentElement.getAttribute('data-hide-balances') === 'true';
    }

    function formatarMoeda(valor) {
        if (isHidden()) {
            return MASCARA;
        }
        return 'R$ ' + Number(valor).toLocaleString('pt-BR', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        });
    }

    function atualizarBotoes() {
        var oculto = isHidden();
        document.querySelectorAll('.balance-toggle').forEach(function (btn) {
            btn.setAttribute('aria-pressed', oculto ? 'true' : 'false');
            btn.setAttribute(
                'aria-label',
                oculto ? 'Mostrar saldos' : 'Ocultar saldos'
            );
            btn.setAttribute('title', oculto ? 'Mostrar saldos' : 'Ocultar saldos');
        });
    }

    function aplicarMascaraDOM() {
        document.querySelectorAll('[data-sensitive="currency"]').forEach(function (el) {
            if (!el.dataset.original) {
                el.dataset.original = el.textContent.trim();
            }
            el.textContent = isHidden() ? MASCARA : el.dataset.original;
        });
    }

    function applyHiddenState(oculto) {
        document.documentElement.setAttribute('data-hide-balances', oculto ? 'true' : 'false');
        atualizarBotoes();
        aplicarMascaraDOM();
    }

    function setHidden(oculto) {
        try {
            localStorage.setItem(STORAGE_KEY, oculto ? 'true' : 'false');
        } catch (e) { /* storage indisponível */ }
        applyHiddenState(oculto);
        window.dispatchEvent(new CustomEvent('balancevisibilitychange', {
            detail: { hidden: oculto }
        }));
    }

    function toggleHidden() {
        setHidden(!isHidden());
    }

    function initBalanceToggle() {
        document.querySelectorAll('.balance-toggle').forEach(function (btn) {
            btn.addEventListener('click', toggleHidden);
        });
        applyHiddenState(getStoredHidden());
    }

    window.FinancasBalancePrivacy = {
        isHidden: isHidden,
        get: getStoredHidden,
        set: setHidden,
        toggle: toggleHidden,
        init: initBalanceToggle,
        formatarMoeda: formatarMoeda,
        aplicarMascaraDOM: aplicarMascaraDOM,
        MASCARA: MASCARA
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initBalanceToggle);
    } else {
        initBalanceToggle();
    }
})();
