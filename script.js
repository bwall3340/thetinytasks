// The Tiny Tasks - Main JavaScript

class TinyTasksApp {
    constructor() {
        this.coverPage = document.getElementById('cover-page');
        this.mainPage = document.getElementById('main-page');
        this.hamburgerMenu = document.getElementById('hamburger-menu');
        this.mobileMenu = document.getElementById('mobile-menu');
        this.scrollThreshold = 50; // Pixels to scroll before transitioning
        this.isOnCoverPage = true; // Track which page we're on
        this.scrollPosition = 0; // Track scroll position
        this.isTransitioning = false; // Prevent multiple transitions

        this.init();
    }

    init() {
        this.bindEvents();
        this.handleInitialLoad();
    }

    bindEvents() {
        // Scroll event for bi-directional transition
        window.addEventListener('scroll', (e) => this.handleScroll(e));

        // Wheel event for precise control
        window.addEventListener('wheel', (e) => this.handleWheel(e), { passive: false });

        // Touch events for mobile
        window.addEventListener('touchstart', (e) => this.handleTouchStart(e));
        window.addEventListener('touchmove', (e) => this.handleTouch(e), { passive: false });

        // Hamburger menu toggle
        this.hamburgerMenu.addEventListener('click', () => this.toggleMobileMenu());

        // Close mobile menu when clicking overlay
        this.mobileMenu.addEventListener('click', (e) => {
            if (e.target === this.mobileMenu) {
                this.closeMobileMenu();
            }
        });

        // Tool card clicks
        document.querySelectorAll('.tool-card').forEach(card => {
            card.addEventListener('click', (e) => this.handleToolClick(e));
        });

        // Mobile menu tool clicks
        document.querySelectorAll('.mobile-menu a[data-tool]').forEach(link => {
            link.addEventListener('click', (e) => this.handleToolClick(e));
        });

        // Keyboard navigation
        document.addEventListener('keydown', (e) => this.handleKeydown(e));
    }

    handleInitialLoad() {
        if (!this.coverPage) return;
        // Ensure cover page is visible on load
        this.coverPage.style.transform = 'translateY(0)';
        this.coverPage.style.display = 'flex';
        this.isOnCoverPage = true;
        window.scrollTo(0, 0);

        // Set body height to ensure minimal scrollable content
        document.body.style.height = '100vh';
        document.body.style.overflow = 'hidden'; // Initially hidden

        // Add click-to-test for debugging
        this.coverPage.addEventListener('click', () => {
            console.log('🖱️ Cover page clicked - testing transition');
            this.transitionToMainPage();
        });
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

        // Handle wheel events for immediate responsiveness
        if (this.isOnCoverPage && e.deltaY > 0) {
            // Scrolling down on cover page - transition to main
            e.preventDefault();
            this.transitionToMainPage();
        } else if (!this.isOnCoverPage && e.deltaY < 0) {
            // Scrolling up on main page - check if we can return to cover
            const mainPage = this.mainPage;
            const mainPageScrollTop = mainPage.scrollTop;

            // If main page is scrolled to top, return to cover page
            if (mainPageScrollTop <= 10) { // Small threshold for sensitivity
                e.preventDefault();
                this.transitionToCoverPage();
            }
            // Otherwise, let the main page handle its internal scrolling
        }
    }

    handleTouchStart(e) {
        this.touchStartY = e.touches[0].clientY;
        this.touchStartTime = Date.now();
    }

    handleTouch(e) {
        if (this.isTransitioning) return;

        // Touch detection for mobile
        if (e.touches.length === 1) {
            const touch = e.touches[0];
            const deltaY = this.touchStartY - touch.clientY;
            const deltaTime = Date.now() - this.touchStartTime;

            // Swipe up threshold
            if (this.isOnCoverPage && deltaY > 50 && deltaTime < 500) {
                e.preventDefault();
                this.transitionToMainPage();
            }
            // Swipe down threshold
            else if (!this.isOnCoverPage && deltaY < -50 && deltaTime < 500) {
                const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
                if (scrollTop <= this.scrollThreshold) {
                    e.preventDefault();
                    this.transitionToCoverPage();
                }
            }
        }
    }

    handleKeydown(e) {
        // Arrow down or space to transition to main page
        if ((e.key === 'ArrowDown' || e.key === ' ') && this.isOnCoverPage) {
            e.preventDefault();
            this.transitionToMainPage();
        }

        // Arrow up to transition to cover page
        if (e.key === 'ArrowUp' && !this.isOnCoverPage) {
            const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
            if (scrollTop <= this.scrollThreshold) {
                e.preventDefault();
                this.transitionToCoverPage();
            }
        }

        // Escape to close mobile menu
        if (e.key === 'Escape') {
            this.closeMobileMenu();
        }
    }

    transitionToMainPage() {
        if (!this.coverPage || this.isTransitioning || !this.isOnCoverPage) return;

        console.log('🚀 Starting transition to main page');

        this.isTransitioning = true;
        this.isOnCoverPage = false;

        // Force the slide-up animation
        this.coverPage.classList.add('slide-up');

        // Also try setting the transform directly as backup
        this.coverPage.style.transform = 'translateY(-100vh)';

        // Enable scrolling on body but keep it locked to main page content
        document.body.style.overflow = 'hidden'; // Keep body locked
        document.body.style.height = '100vh'; // Maintain viewport height

        console.log('Added slide-up class and transform');

        // Complete transition after animation
        setTimeout(() => {
            this.isTransitioning = false;
        }, 800);

        // Add entrance animation to main page elements
        setTimeout(() => {
            this.animateMainPageElements();
        }, 400);
    }

    transitionToCoverPage() {
        if (!this.coverPage || this.isTransitioning || this.isOnCoverPage) return;

        console.log('🔙 Returning to cover page');

        this.isTransitioning = true;
        this.isOnCoverPage = true;

        // Show cover page and remove slide-up
        this.coverPage.style.display = 'flex';
        this.coverPage.classList.remove('slide-up');
        this.coverPage.style.transform = 'translateY(0)';

        // Lock body scrolling
        document.body.style.overflow = 'hidden';
        document.body.style.height = '100vh';

        // Reset main page scroll position
        this.mainPage.scrollTop = 0;

        // Complete transition
        setTimeout(() => {
            this.isTransitioning = false;
        }, 800);
    }

    animateMainPageElements() {
        const toolCards = document.querySelectorAll('.tool-card');

        toolCards.forEach((card, index) => {
            setTimeout(() => {
                card.style.opacity = '0';
                card.style.transform = 'translateY(30px)';
                card.style.transition = 'all 0.6s cubic-bezier(0.25, 0.46, 0.45, 0.94)';

                requestAnimationFrame(() => {
                    card.style.opacity = '1';
                    card.style.transform = 'translateY(0)';
                });
            }, index * 100);
        });
    }

    toggleMobileMenu() {
        this.hamburgerMenu.classList.toggle('active');
        this.mobileMenu.classList.toggle('active');

        // Prevent body scroll when menu is open
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

        // Close mobile menu if open
        this.closeMobileMenu();

        // Add click animation
        this.addClickAnimation(toolElement);

        // Handle tool navigation
        this.launchTool(toolName);
    }

    addClickAnimation(element) {
        element.style.transform = 'scale(0.95)';
        setTimeout(() => {
            element.style.transform = '';
        }, 150);
    }

    launchTool(toolName) {
        // Handle tool launching
        console.log(`Launching tool: ${toolName}`);

        // Add visual feedback
        this.showToast(`Launching ${toolName.replace('-', ' ')}...`);

        // Handle specific tools
        switch(toolName) {
            case 'sankey-chart':
                // Navigate to Sankey chart tool in same tab
                setTimeout(() => {
                    window.location.href = './Sankey/sankey_chart_tool (15).html';
                }, 500);
                break;

            case 'background-remover':
                // Navigate to Enhanced Background Remover tool in same tab
                setTimeout(() => {
                    window.location.href = './background-remover.html';
                }, 500);
                break;

            case 'white-background-remover':
                // Redirect old tool name to new one for compatibility
                setTimeout(() => {
                    window.location.href = './background-remover.html';
                }, 500);
                break;

            default:
                // Placeholder for other tools
                setTimeout(() => {
                    alert(`${toolName.replace('-', ' ')} coming soon!\n\nThis tool is planned for a future release.`);
                }, 500);
                break;
        }
    }

    showToast(message) {
        // Create toast notification
        const toast = document.createElement('div');
        toast.className = 'toast';
        toast.textContent = message;
        toast.style.cssText = `
            position: fixed;
            bottom: 20px;
            left: 50%;
            transform: translateX(-50%);
            background: #1e293b;
            color: white;
            padding: 12px 24px;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 500;
            z-index: 1000;
            opacity: 0;
            transition: opacity 0.3s ease;
        `;

        document.body.appendChild(toast);

        // Animate in
        requestAnimationFrame(() => {
            toast.style.opacity = '1';
        });

        // Remove after delay
        setTimeout(() => {
            toast.style.opacity = '0';
            setTimeout(() => {
                document.body.removeChild(toast);
            }, 300);
        }, 2000);
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
        const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
        document.documentElement.style.scrollBehavior = 'smooth';
    });
}