/**
 * Navegação mobile — sidebar drawer com overlay e tecla Escape.
 */
(function () {
    'use strict';

    function initNav() {
        var toggle = document.getElementById('menu-toggle');
        var sidebar = document.getElementById('sidebar');
        var overlay = document.getElementById('sidebar-overlay');

        if (!toggle || !sidebar) return;

        function abrir() {
            sidebar.classList.add('aberta');
            if (overlay) overlay.classList.add('visivel');
            toggle.setAttribute('aria-expanded', 'true');
            document.body.style.overflow = 'hidden';
        }

        function fechar() {
            sidebar.classList.remove('aberta');
            if (overlay) overlay.classList.remove('visivel');
            toggle.setAttribute('aria-expanded', 'false');
            document.body.style.overflow = '';
        }

        toggle.addEventListener('click', function () {
            if (sidebar.classList.contains('aberta')) {
                fechar();
            } else {
                abrir();
            }
        });

        if (overlay) {
            overlay.addEventListener('click', fechar);
        }

        // Fechar ao clicar em link da sidebar (mobile)
        sidebar.querySelectorAll('.sidebar-link').forEach(function (link) {
            link.addEventListener('click', function () {
                if (window.innerWidth < 1024) fechar();
            });
        });

        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && sidebar.classList.contains('aberta')) {
                fechar();
                toggle.focus();
            }
        });

        // Fechar sidebar ao redimensionar para desktop
        window.addEventListener('resize', function () {
            if (window.innerWidth >= 1024) fechar();
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initNav);
    } else {
        initNav();
    }
})();
