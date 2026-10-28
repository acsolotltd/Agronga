/* AgroNGA: Alpine (CSP build) components + stores.
   CSP build rule: templates reference properties/methods only, no inline expressions.
   Registered on `alpine:init`, so this file must load BEFORE the Alpine script. */
document.addEventListener('alpine:init', () => {
  const root = document.documentElement;

  /* ── Screen-reader announcements ─────────────── */
  Alpine.store('live', {
    msg: '',
    say(text) { this.msg = ''; queueMicrotask(() => { this.msg = text; }); },
  });

  /* ── Theme: 'light' | 'dark' | 'system' ─────────
     The inline script in <head> sets the first paint; this keeps it in sync. */
  const KEY = 'agronga-theme';
  const mq = matchMedia('(prefers-color-scheme: dark)');
  Alpine.store('theme', {
    mode: root.dataset.theme || 'system',
    init() { mq.addEventListener('change', () => this.apply()); },
    set(mode) {
      this.mode = mode;
      try { localStorage.setItem(KEY, mode); } catch (e) {}
      this.apply();
    },
    apply() {
      root.classList.toggle('dark', this.mode === 'dark' || (this.mode === 'system' && mq.matches));
      root.dataset.theme = this.mode;
    },
  });

  /* ── Currency: server is the source of truth (cookie); this mirrors it ── */
  Alpine.store('currency', {
    code: root.dataset.currency,
    name: root.dataset.currencyName,
    init() {
      // Sent by the server via HX-Trigger after POST /currency/
      document.addEventListener('currency:changed', (e) => {
        const { code, name } = e.detail || {};
        if (!code) return;
        this.code = code; this.name = name;
        root.dataset.currency = code; root.dataset.currencyName = name;
        Alpine.store('live').say(`Prices are now shown in ${name}.`);
      });
    },
  });

  /* ── Shared radiogroup behaviour (arrow keys) ── */
  const roving = (el, step) => {
    const items = [...el.parentElement.querySelectorAll('[role="radio"]')];
    const next = items[(items.indexOf(el) + step + items.length) % items.length];
    next.focus(); next.click();
  };

  Alpine.data('themeOption', () => ({
    mode: '',
    init() { this.mode = this.$el.dataset.mode; },
    get active() { return Alpine.store('theme').mode === this.mode; },
    choose() { Alpine.store('theme').set(this.mode); },
    next() { roving(this.$el, 1); },
    prev() { roving(this.$el, -1); },
  }));

  Alpine.data('currencyOption', () => ({
    code: '',
    init() { this.code = this.$el.dataset.code; },
    get active() { return Alpine.store('currency').code === this.code; },
    next() { roving(this.$el, 1); },
    prev() { roving(this.$el, -1); },
  }));

  /* ── Header / mobile menu ── */
  Alpine.data('siteHeader', () => ({
    open: false,
    init() {
      matchMedia('(min-width: 64rem)').addEventListener('change', (e) => { if (e.matches) this.open = false; });
    },
    toggle() { this.open = !this.open; },
    close() {
      if (!this.open) return;
      this.open = false;
      this.$refs.menuBtn.focus();
    },
    onPanelClick(e) { if (e.target.closest('a')) this.open = false; },
  }));

  /* ── Quote form: loading state ── */
  Alpine.data('quoteForm', () => ({
    submitting: false,
    start() { this.submitting = true; },
    done() { this.submitting = false; },
    get label() { return this.submitting ? 'Sending…' : 'Send request'; },
  }));

  /* ── Rebuilds the email address in the browser so no mailto: sits in the HTML ── */
  Alpine.data('revealEmail', () => ({
    init() {
      const a = this.$el, addr = `${a.dataset.user}@${a.dataset.domain}`;
      a.href = `mailto:${addr}`;
      a.textContent = addr;
    },
  }));

  /* ── Announces a message when this element appears (e.g. form success) ── */
  Alpine.data('announce', () => ({
    init() { Alpine.store('live').say(this.$el.dataset.message); },
  }));
});

/* ── htmx glue (no Alpine needed) ── */
// htmx ignores 4xx by default; the quote form returns 422 with errors rendered
document.addEventListener('htmx:beforeSwap', (e) => {
  if (e.detail.xhr.status === 422) { e.detail.shouldSwap = true; e.detail.isError = false; }
});
// After a boosted page change, move focus to <main> for keyboard and screen-reader users
document.addEventListener('htmx:afterSettle', (e) => {
  if (e.detail.boosted) document.getElementById('main')?.focus({ preventScroll: true });
});
