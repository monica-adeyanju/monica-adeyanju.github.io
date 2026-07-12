/* ─── Smooth scroll for nav links ─────────────────────────────────────────── */
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            target.scrollIntoView({ behavior: 'smooth' });
        }
    });
});

/* ─── Navbar background on scroll ─────────────────────────────────────────── */
const nav = document.querySelector('.nav');
let lastScroll = 0;

window.addEventListener('scroll', () => {
    const currentScroll = window.pageYOffset;

    if (currentScroll > 50) {
        nav.style.borderBottomColor = 'rgba(30, 41, 59, 0.8)';
    } else {
        nav.style.borderBottomColor = 'rgba(30, 41, 59, 0.3)';
    }

    lastScroll = currentScroll;
});

/* ─── Fade-in animation on scroll ─────────────────────────────────────────── */
const observerOptions = {
    threshold: 0.1,
    rootMargin: '0px 0px -50px 0px'
};

const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.classList.add('visible');
            observer.unobserve(entry.target);
        }
    });
}, observerOptions);

// Observe all sections and project cards
document.querySelectorAll('.section, .project-card, .skill-group').forEach(el => {
    el.classList.add('fade-in');
    observer.observe(el);
});

/* ─── Add fade-in styles dynamically ──────────────────────────────────────── */
const style = document.createElement('style');
style.textContent = `
    .fade-in {
        opacity: 0;
        transform: translateY(20px);
        transition: opacity 0.6s ease, transform 0.6s ease;
    }
    .fade-in.visible {
        opacity: 1;
        transform: translateY(0);
    }
`;
document.head.appendChild(style);
