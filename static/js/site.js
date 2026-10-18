(() => {
  const menuButton = document.getElementById('menu-toggle');
  const menu = document.getElementById('site-navigation');
  const header = document.getElementById('site-header');

  if (menuButton && menu) {
    menuButton.addEventListener('click', () => {
      const isOpen = menuButton.getAttribute('aria-expanded') === 'true';
      menuButton.setAttribute('aria-expanded', String(!isOpen));
      menu.classList.toggle('is-open', !isOpen);
      menuButton.setAttribute('aria-label', isOpen ? 'Open navigation' : 'Close navigation');
    });
    menu.querySelectorAll('a').forEach(link => link.addEventListener('click', () => {
      menu.classList.remove('is-open');
      menuButton.setAttribute('aria-expanded', 'false');
    }));
    document.addEventListener('keydown', event => {
      if (event.key === 'Escape') {
        menu.classList.remove('is-open');
        menuButton.setAttribute('aria-expanded', 'false');
      }
    });
  }
  const setHeader = () => header?.classList.toggle('is-scrolled', window.scrollY > 10);
  window.addEventListener('scroll', setHeader, { passive: true });
  setHeader();

  // Progressive enhancement: content stays visible when JS/observer is unavailable.
  if ('IntersectionObserver' in window && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    const elements = [...document.querySelectorAll('.reveal')];
    const observer = new IntersectionObserver((entries, obs) => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          obs.unobserve(entry.target);
        }
      }
    }, { threshold: .08, rootMargin: '0px 0px 30px 0px' });
    // Hide only after observers are registered and page has laid out.
    elements.forEach(element => observer.observe(element));
    document.documentElement.classList.add('js-motion');
  }
})();
