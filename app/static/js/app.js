/**
 * Inicialização global da aplicação.
 */
(function () {
    'use strict';

    function initFlashDismiss() {
        document.querySelectorAll('.alert[data-auto-dismiss]').forEach(function (alert) {
            setTimeout(function () {
                alert.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
                alert.style.opacity = '0';
                alert.style.transform = 'translateY(-8px)';
                setTimeout(function () { alert.remove(); }, 300);
            }, 4000);
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initFlashDismiss);
    } else {
        initFlashDismiss();
    }
})();
