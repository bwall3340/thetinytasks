// The Tiny Tasks - Main JavaScript

class TinyTasksApp {
    constructor() {
        this.coverPage = document.getElementById('cover-page');
        this.mainPage = document.getElementById('main-page');
        this.hamburgerMenu = document.getElementById('hamburger-menu');
        this.mobileMenu = document.getElementById('mobile-menu');
        this.comingSoonModal = document.getElementById('coming-soon-modal');
        this.scrollThreshold = 50;
        this.isOnCoverPage = true;
        this.scrollPosition = 0;
        this.isTransitioning = false;

        this.init();
    }

    init() {
        this.bindEvents();
        this.handleInitialLoad();
    }

    bindEvents() {
        window.addEventListener('scroll', (e) => this.handleScroll(e));
        window.addEventListener('wheel', (e) => this.handleWheel(e), { passive: false });
        window.addEventListener('touchstart', (e) => this.handleTouchStart(e));
        window.addEventListener('touchmove', (e) => this.handleTouch(e), { passive: false });

        this.hamburgerMenu.addEventListener('click', () => this.toggleMobileMenu());

        this.mobileMenu.addEventListener('click', (e) => {
            if (e.target === this.mobileMenu) {
                this.closeMobileMenu();
            }
        });

        document.querySelectorAll('.tool-card').forEach(card => {
            card.addEventListener('click', (e) => this.handleToolClick(e));
        });

        document.querySelectorAll('.mobile-menu a[data-tool]').forEach(link => {
            link.addEventListener('click', (e) => this.handleToolClick(e));
        });

        document.addEventListener('keydown', (e) => this.handleKeydown(e));

        document.getElementById('modal-close-btn').addEventListener('click', () => this.closeComingSoonModal());
        this.comingSoonModal.addEventListener('click', (e) => {
            if (e.target === this.comingSoonModal) this.closeComingSoonModal();
        });

        const toolsNavLink = document.querySelector('.main-nav a[href="#tools"]');
        if (toolsNavLink) {
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
        if (this.isTransitioning) return;

        const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
        this.scrollPosition = scrollTop;

        if (this.isOnCoverPage && scrollTop > this.scrollThreshold) {
            this.transitionToMainPage();
        } else if (!this.isOnCoverPage && scrollTop <= this.scrollThreshold) {
            this.transitionToCoverPage();
        }
    }

    handleWheel(e) {
        if (this.isTransitioning) return;

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
        if (this.isTransitioning) return;

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
        if ((e.key === 'ArrowDown' || e.key === ' ') && this.isOnCoverPage) {
            e.preventDefault();
            this.transitionToMainPage();
        }

        if (e.key === 'ArrowUp' && !this.isOnCoverPage) {
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

        this.mainPage.scrollTop = 0;

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
        this.hamburgerMenu.classList.toggle('active');
        this.mobileMenu.classList.toggle('active');

        if (this.mobileMenu.classList.contains('active')) {
            document.body.style.overflow = 'hidden';
        } else {
            document.body.style.overflow = 'auto';
        }
    }

    closeMobileMenu() {
        this.hamburgerMenu.classList.remove('active');
        this.mobileMenu.classList.remove('active');
        document.body.style.overflow = 'auto';
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
            case 'white-background-remover':
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
        document.getElementById('modal-tool-name').textContent = displayName;
        this.comingSoonModal.classList.add('active');
    }

    closeComingSoonModal() {
        this.comingSoonModal.classList.remove('active');
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
