// The Tiny Tasks - Main JavaScript

class TinyTasksApp {
    constructor() {
        this.coverPage = document.getElementById('cover-page');
        this.mainPage = document.getElementById('main-page');
        this.hamburgerMenu = document.getElementById('hamburger-menu');
        this.mobileMenu = document.getElementById('mobile-menu');
        this.comingSoonModal = document.getElementById('coming-soon-modal');
        this.scrollThreshold = 50;
        // Pages without a cover (tool pages) must never enter cover mode —
        // the wheel/touch handlers preventDefault() while it is true.
        this.isOnCoverPage = !!this.coverPage;
        this.scrollPosition = 0;
        this.isTransitioning = false;

        this.init();
    }

    init() {
        this.bindEvents();
        this.handleInitialLoad();
    }

    bindEvents() {
        // Cover-page scroll hijacking — only bind it where a cover page exists.
        if (this.coverPage) {
            window.addEventListener('scroll', (e) => this.handleScroll(e));
            window.addEventListener('wheel', (e) => this.handleWheel(e), { passive: false });
            window.addEventListener('touchstart', (e) => this.handleTouchStart(e));
            window.addEventListener('touchmove', (e) => this.handleTouch(e), { passive: false });
        }

        if (this.hamburgerMenu) {
            this.hamburgerMenu.addEventListener('click', () => this.toggleMobileMenu());
        }

        if (this.mobileMenu) {
            this.mobileMenu.addEventListener('click', (e) => {
                if (e.target === this.mobileMenu) {
                    this.closeMobileMenu();
                }
            });
        }

        document.querySelectorAll('.tool-card').forEach(card => {
            card.addEventListener('click', (e) => this.handleToolClick(e));
        });

        document.querySelectorAll('.mobile-menu a[data-tool]').forEach(link => {
            link.addEventListener('click', (e) => this.handleToolClick(e));
        });

        document.addEventListener('keydown', (e) => this.handleKeydown(e));

        const modalCloseBtn = document.getElementById('modal-close-btn');
        if (modalCloseBtn) {
            modalCloseBtn.addEventListener('click', () => this.closeComingSoonModal());
        }

        if (this.comingSoonModal) {
            this.comingSoonModal.addEventListener('click', (e) => {
                if (e.target === this.comingSoonModal) this.closeComingSoonModal();
            });
        }

        const toolsNavLink = document.querySelector('.main-nav a[href="#tools"]');
        if (toolsNavLink && this.mainPage) {
            toolsNavLink.addEventListener('click', (e) => {
                e.preventDefault();
                const toolsEl = document.getElementById('tools');
                if (this.isOnCoverPage) {
                    this.transitionToMainPage();
                    setTimeout(() => {
                        if (toolsEl) this.mainPage.scrollTo({ top: toolsEl.offsetTop, behavior: 'smooth' });
                    }, 500);
                } else {
                    if (toolsEl) this.mainPage.scrollTo({ top: toolsEl.offsetTop, behavior: 'smooth' });
                }
            });
        }
    }

    handleInitialLoad() {
        if (!this.coverPage) return;
        this.coverPage.style.transform = 'translateY(0)';
        this.coverPage.style.display = 'flex';
        this.isOnCoverPage = true;
        window.scrollTo(0, 0);

        document.body.style.height = '100vh';
        document.body.style.overflow = 'hidden';

        this.coverPage.addEventListener('click', () => {
            this.transitionToMainPage();
        });

        const img = new Image();
        img.onload = () => this.coverPage.classList.add('ready');
        img.onerror = () => this.coverPage.classList.add('ready');
        img.src = '/assets/hero.jpg';
    }

    handleScroll(e) {
        if (!this.coverPage || this.isTransitioning) return;

        const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
        this.scrollPosition = scrollTop;

        if (this.isOnCoverPage && scrollTop > this.scrollThreshold) {
            this.transitionToMainPage();
        } else if (!this.isOnCoverPage && scrollTop <= this.scrollThreshold) {
            this.transitionToCoverPage();
        }
    }

    handleWheel(e) {
        if (!this.coverPage || this.isTransitioning) return;

        if (this.isOnCoverPage && e.deltaY > 0) {
            e.preventDefault();
            this.transitionToMainPage();
        } else if (!this.isOnCoverPage && e.deltaY < 0) {
            const mainPageScrollTop = this.mainPage.scrollTop;
            if (mainPageScrollTop <= 10) {
                e.preventDefault();
                this.transitionToCoverPage();
            }
        }
    }

    handleTouchStart(e) {
        this.touchStartY = e.touches[0].clientY;
        this.touchStartTime = Date.now();
    }

    handleTouch(e) {
        if (!this.coverPage || this.isTransitioning) return;

        if (e.touches.length === 1) {
            const touch = e.touches[0];
            const deltaY = this.touchStartY - touch.clientY;
            const deltaTime = Date.now() - this.touchStartTime;

            if (this.isOnCoverPage && deltaY > 50 && deltaTime < 500) {
                e.preventDefault();
                this.transitionToMainPage();
            } else if (!this.isOnCoverPage && deltaY < -50 && deltaTime < 500) {
                const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
                if (scrollTop <= this.scrollThreshold) {
                    e.preventDefault();
                    this.transitionToCoverPage();
                }
            }
        }
    }

    handleKeydown(e) {
        if ((e.key === 'ArrowDown' || e.key === ' ') && this.coverPage && this.isOnCoverPage) {
            e.preventDefault();
            this.transitionToMainPage();
        }

        if (e.key === 'ArrowUp' && this.coverPage && !this.isOnCoverPage) {
            const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
            if (scrollTop <= this.scrollThreshold) {
                e.preventDefault();
                this.transitionToCoverPage();
            }
        }

        if (e.key === 'Escape') {
            this.closeMobileMenu();
            this.closeComingSoonModal();
        }
    }

    transitionToMainPage() {
        if (!this.coverPage || this.isTransitioning || !this.isOnCoverPage) return;

        this.isTransitioning = true;
        this.isOnCoverPage = false;

        this.coverPage.classList.add('slide-up');
        this.coverPage.style.transform = 'translateY(-100vh)';

        document.body.style.overflow = 'hidden';
        document.body.style.height = '100vh';

        setTimeout(() => {
            this.isTransitioning = false;
        }, 800);

        setTimeout(() => {
            this.animateMainPageElements();
        }, 400);
    }

    transitionToCoverPage() {
        if (!this.coverPage || this.isTransitioning || this.isOnCoverPage) return;

        this.isTransitioning = true;
        this.isOnCoverPage = true;

        this.coverPage.style.display = 'flex';
        this.coverPage.classList.remove('slide-up');
        this.coverPage.style.transform = 'translateY(0)';

        document.body.style.overflow = 'hidden';
        document.body.style.height = '100vh';

        if (this.mainPage) this.mainPage.scrollTop = 0;

        // Reset cards so they re-animate next time
        document.querySelectorAll('.tool-card').forEach(card => {
            card.classList.remove('visible');
            card.style.animationDelay = '';
        });

        setTimeout(() => {
            this.isTransitioning = false;
        }, 800);
    }

    animateMainPageElements() {
        document.querySelectorAll('.tool-card').forEach((card, i) => {
            card.style.animationDelay = `${i * 80}ms`;
            card.classList.add('visible');
        });
    }

    toggleMobileMenu() {
        if (!this.hamburgerMenu || !this.mobileMenu) return;

        this.hamburgerMenu.classList.toggle('active');
        this.mobileMenu.classList.toggle('active');

        if (this.mobileMenu.classList.contains('active')) {
            document.body.style.overflow = 'hidden';
        } else {
            this.restoreBodyScroll();
        }
    }

    closeMobileMenu() {
        if (!this.hamburgerMenu || !this.mobileMenu) return;

        this.hamburgerMenu.classList.remove('active');
        this.mobileMenu.classList.remove('active');
        this.restoreBodyScroll();
    }

    // The cover page locks body scroll on purpose; everywhere else the body
    // must be free to scroll once the menu closes.
    restoreBodyScroll() {
        document.body.style.overflow = this.isOnCoverPage ? 'hidden' : 'auto';
    }

    handleToolClick(e) {
        const toolElement = e.currentTarget;
        const toolName = toolElement.dataset.tool;

        if (!toolName) return;

        this.closeMobileMenu();
        this.addClickAnimation(toolElement);
        this.launchTool(toolName);
    }

    addClickAnimation(element) {
        element.style.transform = 'scale(0.95)';
        setTimeout(() => {
            element.style.transform = '';
        }, 150);
    }

    launchTool(toolName) {
        switch(toolName) {
            case 'sankey-chart':
                window.location.href = './Sankey/sankey_chart_tool (15).html';
                break;

            case 'background-remover':
                window.location.href = './background-remover.html';
                break;

            case 'return-stream':
                window.location.href = './return-stream.html';
                break;

            case 'market-outlook':
                window.location.href = '/market';
                break;

            case 'meal-planner':
                window.location.href = '/meal-planner';
                break;

            case 'about':
                window.location.href = './about.html';
                break;

            case 'bigger-projects':
                window.location.href = './bigger-projects.html';
                break;

            default:
                this.showComingSoonModal(toolName);
                break;
        }
    }

    showComingSoonModal(toolName) {
        const displayName = toolName
            .replace(/-/g, ' ')
            .replace(/\b\w/g, c => c.toUpperCase());
        const nameEl = document.getElementById('modal-tool-name');
        if (nameEl) nameEl.textContent = displayName;
        if (this.comingSoonModal) this.comingSoonModal.classList.add('active');
    }

    closeComingSoonModal() {
        if (this.comingSoonModal) this.comingSoonModal.classList.remove('active');
    }
}

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new TinyTasksApp();
});

// Touch event tracking for mobile
document.addEventListener('touchstart', (e) => {
    if (e.touches.length === 1) {
        window.touchStartY = e.touches[0].clientY;
    }
});

// Smooth scrolling polyfill for older browsers
if (!('scrollBehavior' in document.documentElement.style)) {
    window.addEventListener('scroll', () => {
        document.documentElement.style.scrollBehavior = 'smooth';
    });
}
