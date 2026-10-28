/* AgroNGA storefront. Vanilla JS, no dependencies.
   Sections: helpers · theme · currency · cart · drawer/menu · hero · panels · filter · product page · forms · misc */
(() => {
  'use strict';
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const root = document.documentElement;
  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const icon = (n) => `<svg class="i" aria-hidden="true"><use href="#i-${n}"/></svg>`;
  const store = {
    get(k, d) { try { const v = localStorage.getItem(k); return v === null ? d : JSON.parse(v); } catch (e) { return d; } },
    set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* private mode */ } },
  };

  /* ── Toast ── */
  let toastTimer;
  function toast(msg) {
    let t = $('.toast');
    if (!t) { t = document.createElement('div'); t.className = 'toast'; t.setAttribute('role', 'status'); document.body.appendChild(t); }
    t.innerHTML = icon('check') + `<span>${esc(msg)}</span>`;
    requestAnimationFrame(() => t.classList.add('is-shown'));
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => t.classList.remove('is-shown'), 2600);
  }

  /* ── Theme ── */
  const setTheme = (m) => { root.dataset.theme = m; store.set('agronga-theme', m); };
  $$('[data-theme-toggle]').forEach((b) => b.addEventListener('click', () => setTheme(root.dataset.theme === 'dark' ? 'light' : 'dark')));

  /* ── Currency (cookie is the shared source of truth with the server) ── */
  const CUR = { NGN: { sym: '₦', dec: 0 }, USD: { sym: '$', dec: 2 } };
  // The cookie wins over the HTML attribute, so a cached page never shows the wrong currency.
  const cookieCur = (document.cookie.match(/(?:^|; )agronga_currency=([A-Z]{3})/) || [])[1];
  let code = CUR[cookieCur] ? cookieCur : (CUR[root.dataset.currency] ? root.dataset.currency : 'NGN');
  root.dataset.currency = code;
  const money = (n, c = code) => CUR[c].sym + Number(n).toLocaleString('en-US', { minimumFractionDigits: CUR[c].dec, maximumFractionDigits: CUR[c].dec });
  function renderPrice(el, animate) {
    // .price-alt shows the OTHER currency (product page: "Also priced at ...")
    const c = el.classList.contains('price-alt') ? (code === 'NGN' ? 'USD' : 'NGN') : code;
    const v = el.dataset[c.toLowerCase()];
    el.textContent = v === '' || v === undefined ? 'Price on request' : (el.dataset.from ? 'From ' : '') + money(v, c);
    if (animate && !reduced) { el.classList.remove('is-flip'); void el.offsetWidth; el.classList.add('is-flip'); }
  }
  function setCurrency(next, announce) {
    if (!CUR[next]) return;
    code = next;
    root.dataset.currency = next;
    document.cookie = `agronga_currency=${next}; path=/; max-age=31536000; SameSite=Lax`;
    $$('.seg').forEach((s) => { s.dataset.active = next; $$('button', s).forEach((b) => b.setAttribute('aria-checked', String(b.dataset.code === next))); });
    $$('.price, .price-alt').forEach((el) => renderPrice(el, true));
    document.dispatchEvent(new CustomEvent('currency:change'));
    if (announce) toast(`Prices now shown in ${next === 'NGN' ? 'naira (₦)' : 'US dollars ($)'}`);
  }
  $$('.seg').forEach((s) => {
    s.dataset.active = code;
    $$('button', s).forEach((b) => {
      b.setAttribute('aria-checked', String(b.dataset.code === code));
      b.addEventListener('click', () => b.dataset.code !== code && setCurrency(b.dataset.code, true));
    });
  });
  $$('.price, .price-alt').forEach((el) => renderPrice(el, false));

  /* ── Cart ── */
  const KEY = 'agronga-cart-v1';
  let cart = store.get(KEY, []);
  if (!Array.isArray(cart)) cart = [];
  const unitPrice = (it) => { const v = it[code.toLowerCase()]; return v === '' || v == null ? null : Number(v); };
  const cartCount = () => cart.reduce((n, i) => n + i.qty, 0);
  function cartTotal() {
    let total = 0, missing = false;
    cart.forEach((i) => { const p = unitPrice(i); if (p === null) missing = true; else total += p * i.qty; });
    return { total, missing };
  }
  function saveCart() { store.set(KEY, cart); renderCart(); document.dispatchEvent(new CustomEvent('cart:change')); }
  function addToCart(data, qty = 1) {
    const found = cart.find((i) => i.slug === data.slug);
    if (found) found.qty = Math.min(9999, found.qty + qty);
    else cart.push({ slug: data.slug, name: data.name, unit: data.unit || '', url: data.url || '', img: data.img || '', ngn: data.ngn, usd: data.usd, qty });
    saveCart();
  }
  function setQty(slug, qty) {
    const it = cart.find((i) => i.slug === slug); if (!it) return;
    it.qty = Math.max(1, Math.min(9999, qty)); saveCart();
  }
  function removeItem(slug) { cart = cart.filter((i) => i.slug !== slug); saveCart(); }

  function lineHTML(i) {
    const p = unitPrice(i);
    return `<li class="line" data-slug="${esc(i.slug)}">
      <a href="${esc(i.url)}"><img src="${esc(i.img)}" alt="" loading="lazy"></a>
      <div><a class="line-name" href="${esc(i.url)}">${esc(i.name)}</a>
        <span class="line-unit">${p === null ? 'Price on request' : money(p) + ' ' + esc(i.unit)}</span></div>
      <div class="line-bottom">
        <div class="qty" role="group" aria-label="Quantity of ${esc(i.name)}">
          <button type="button" data-line="dec" aria-label="Decrease quantity">${icon('minus')}</button>
          <output aria-live="polite">${i.qty}</output>
          <button type="button" data-line="inc" aria-label="Increase quantity">${icon('plus')}</button>
        </div>
        <span class="line-total">${p === null ? '—' : money(p * i.qty)}</span>
        <button type="button" class="line-remove" data-line="rm">Remove</button>
      </div></li>`;
  }
  function renderCart() {
    const n = cartCount();
    $$('[data-cart-count]').forEach((b) => {
      const was = Number(b.textContent) || 0;
      b.textContent = n; b.classList.toggle('has-items', n > 0);
      if (n > was) { b.classList.remove('bump'); void b.offsetWidth; b.classList.add('bump'); }
    });
    const { total, missing } = cartTotal();
    const totalText = missing && !total ? 'On request' : money(total);
    $$('[data-cart-lines]').forEach((ul) => {
      ul.innerHTML = cart.map(lineHTML).join('');
      const wrap = ul.closest('[data-cart-wrap]');
      if (wrap) { $('[data-cart-empty]', wrap).hidden = n > 0; $('[data-cart-full]', wrap).hidden = n === 0; }
    });
    $$('[data-cart-total]').forEach((el) => { el.textContent = totalText; });
    $$('[data-cart-note]').forEach((el) => { el.hidden = !missing; });
    $$('[data-cart-json]').forEach((el) => { el.value = JSON.stringify(cart.map((i) => ({ slug: i.slug, qty: i.qty }))); });
    $$('[data-cart-currency]').forEach((el) => { el.textContent = code === 'NGN' ? 'naira (₦)' : 'US dollars ($)'; });
  }
  document.addEventListener('currency:change', renderCart);
  document.addEventListener('click', (e) => {
    const b = e.target.closest('[data-line]'); if (!b) return;
    const slug = b.closest('.line').dataset.slug, it = cart.find((i) => i.slug === slug); if (!it) return;
    if (b.dataset.line === 'inc') setQty(slug, it.qty + 1);
    else if (b.dataset.line === 'dec') it.qty > 1 ? setQty(slug, it.qty - 1) : b.closest('.line').dispatchEvent(new CustomEvent('leave', { bubbles: true }));
    else b.closest('.line').dispatchEvent(new CustomEvent('leave', { bubbles: true }));
  });
  document.addEventListener('leave', (e) => {
    const li = e.target, slug = li.dataset.slug;
    if (reduced) return removeItem(slug);
    li.classList.add('is-leaving'); setTimeout(() => removeItem(slug), 280);
  });
  window.addEventListener('storage', (e) => { if (e.key === KEY) { cart = store.get(KEY, []); renderCart(); } });

  /* add-to-cart buttons */
  function fly(from) {
    const target = $$('[data-cart-open]').find((b) => b.offsetParent !== null);
    if (reduced || !target || !from.animate) return;
    const a = from.getBoundingClientRect(), b = target.getBoundingClientRect();
    const dot = document.createElement('span'); dot.className = 'fly';
    dot.style.left = a.left + a.width / 2 - 9 + 'px'; dot.style.top = a.top + a.height / 2 - 9 + 'px';
    document.body.appendChild(dot);
    const dx = b.left + b.width / 2 - (a.left + a.width / 2), dy = b.top + b.height / 2 - (a.top + a.height / 2);
    dot.animate([{ transform: 'translate(0,0) scale(1)', opacity: 1 }, { transform: `translate(${dx * .5}px, ${dy * .5 - 60}px) scale(1.2)`, opacity: 1, offset: .5 }, { transform: `translate(${dx}px, ${dy}px) scale(.3)`, opacity: .4 }],
      { duration: 750, easing: 'cubic-bezier(.5,0,.3,1)' }).onfinish = () => dot.remove();
  }
  document.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-add]'); if (!btn) return;
    e.preventDefault();
    const qtyEl = btn.dataset.qtyInput ? $(btn.dataset.qtyInput) : null;
    const qty = qtyEl ? Math.max(1, parseInt(qtyEl.value, 10) || 1) : 1;
    const d = btn.dataset;
    if ((code === 'USD' ? d.usd : d.ngn) === '') { location.href = d.quoteUrl || '/contact/?topic=quote'; return; }
    addToCart(d, qty); fly(btn);
    btn.classList.add('is-added'); clearTimeout(btn._t); btn._t = setTimeout(() => btn.classList.remove('is-added'), 1500);
    toast(`${d.name} added to cart`);
  });

  /* ── Drawer + mobile menu ── */
  let lastFocus = null;
  const scrim = $('.scrim');
  function openPanel(el, focusSel) {
    $('.toast')?.classList.remove('is-shown');
    lastFocus = document.activeElement; el.classList.add('is-open'); el.setAttribute('aria-hidden', 'false');
    if (scrim && el.classList.contains('drawer')) scrim.classList.add('is-open');
    document.body.style.overflow = 'hidden';
    setTimeout(() => $(focusSel, el)?.focus(), 60);
  }
  function closePanels() {
    $$('.drawer.is-open, .mobile-menu.is-open, .lightbox.is-open').forEach((el) => { el.classList.remove('is-open'); el.setAttribute('aria-hidden', 'true'); });
    scrim?.classList.remove('is-open'); document.body.style.overflow = '';
    $$('[data-menu-open]').forEach((b) => b.setAttribute('aria-expanded', 'false'));
    lastFocus?.focus?.(); lastFocus = null;
  }
  $$('[data-cart-open]').forEach((b) => b.addEventListener('click', (e) => { if (!$('.drawer')) return; e.preventDefault(); openPanel($('.drawer'), '[data-close]'); }));
  $$('[data-menu-open]').forEach((b) => b.addEventListener('click', () => { b.setAttribute('aria-expanded', 'true'); openPanel($('.mobile-menu'), '[data-close]'); }));
  $$('[data-close]').forEach((b) => b.addEventListener('click', closePanels));
  scrim?.addEventListener('click', closePanels);
  $$('.mobile-menu nav a').forEach((a) => a.addEventListener('click', closePanels));
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closePanels(); });
  $$('[data-cart-link]').forEach((a) => a.addEventListener('click', () => { document.body.style.overflow = ''; }));

  const header = $('.site-header');
  if (header) { const f = () => header.classList.toggle('is-scrolled', scrollY > 8); f(); addEventListener('scroll', f, { passive: true }); }

  /* ── Hero slides ── */
  const hero = $('[data-hero]');
  if (hero) {
    const slides = $$('.slide', hero), dots = $$('.hero-dot', hero);
    const DUR = 7000; let cur = 0, auto = !reduced;
    hero.style.setProperty('--dur', DUR + 'ms');
    const go = (i) => {
      cur = (i + slides.length) % slides.length;
      slides.forEach((s, k) => { s.classList.toggle('is-active', k === cur); s.setAttribute('aria-hidden', String(k !== cur)); $$('a,button', s).forEach((el) => { el.tabIndex = k === cur ? 0 : -1; }); });
      dots.forEach((d, k) => { d.classList.remove('is-active'); d.classList.toggle('is-done', !auto ? k === cur : k < cur); d.setAttribute('aria-current', String(k === cur)); });
      void hero.offsetWidth;
      if (auto) dots[cur].classList.add('is-active'); else dots[cur].classList.add('is-done');
      if (slides[cur].dataset.tint) hero.style.setProperty('--tint', slides[cur].dataset.tint);
    };
    hero.addEventListener('animationend', (e) => { if (e.animationName === 'fill' && auto) go(cur + 1); });
    $('[data-next]', hero)?.addEventListener('click', () => go(cur + 1));
    $('[data-prev]', hero)?.addEventListener('click', () => go(cur - 1));
    dots.forEach((d, k) => d.addEventListener('click', () => go(k)));
    const pause = (on) => hero.classList.toggle('is-paused', on);
    hero.addEventListener('mouseenter', () => pause(true)); hero.addEventListener('mouseleave', () => pause(false));
    hero.addEventListener('focusin', () => pause(true)); hero.addEventListener('focusout', () => pause(false));
    document.addEventListener('visibilitychange', () => pause(document.hidden));
    hero.addEventListener('keydown', (e) => { if (e.key === 'ArrowRight') go(cur + 1); if (e.key === 'ArrowLeft') go(cur - 1); });
    let x0 = null;
    hero.addEventListener('touchstart', (e) => { x0 = e.touches[0].clientX; }, { passive: true });
    hero.addEventListener('touchend', (e) => { if (x0 === null) return; const dx = e.changedTouches[0].clientX - x0; if (Math.abs(dx) > 50) go(cur + (dx < 0 ? 1 : -1)); x0 = null; });
    go(0);
  }

  /* ── Flavour panels ── */
  const panels = $$('[data-panel]');
  if (panels.length) {
    const act = (p) => panels.forEach((q) => { const on = q === p; q.classList.toggle('is-active', on); $('.panel-name', q).setAttribute('aria-expanded', String(on)); });
    panels.forEach((p) => {
      $('.panel-name', p).addEventListener('click', () => act(p));
      p.addEventListener('click', (e) => { if (!e.target.closest('a,button')) act(p); });
      p.addEventListener('mouseenter', () => matchMedia('(hover: hover) and (min-width: 900px)').matches && act(p));
    });
    act(panels[0]);
  }

  /* ── Product filter chips (client side) ── */
  $$('[data-filter-group]').forEach((g) => {
    const cards = $$('[data-cat]', g.closest('section, main')), countEl = $('[data-filter-count]', g.closest('section, main'));
    $$('[data-filter]', g).forEach((chip) => chip.addEventListener('click', () => {
      $$('[data-filter]', g).forEach((c) => c.setAttribute('aria-pressed', String(c === chip)));
      let n = 0;
      cards.forEach((c) => {
        const show = chip.dataset.filter === 'all' || c.dataset.cat === chip.dataset.filter;
        c.classList.toggle('is-hidden', !show);
        if (show) { n++; if (!reduced) { c.animate([{ opacity: 0, transform: 'translateY(12px)' }, { opacity: 1, transform: 'none' }], { duration: 420, delay: n * 35, easing: 'ease-out', fill: 'backwards' }); } }
      });
      if (countEl) countEl.textContent = `${n} product${n === 1 ? '' : 's'}`;
    }));
  });

  /* ── Quantity steppers + product page ── */
  $$('[data-qty]').forEach((q) => {
    const input = $('input', q);
    $$('[data-step]', q).forEach((b) => b.addEventListener('click', () => { input.value = Math.max(1, Math.min(9999, (parseInt(input.value, 10) || 1) + Number(b.dataset.step))); }));
    input.addEventListener('change', () => { input.value = Math.max(1, Math.min(9999, parseInt(input.value, 10) || 1)); });
  });
  const main = $('[data-gallery-main]');
  if (main) {
    const img = $('img', main), thumbs = $$('[data-thumb]');
    thumbs.forEach((t) => t.addEventListener('click', () => {
      thumbs.forEach((x) => x.setAttribute('aria-current', String(x === t)));
      img.classList.add('is-swap'); setTimeout(() => { img.src = t.dataset.src; img.classList.remove('is-swap'); }, 180);
    }));
    const lb = $('.lightbox');
    main.addEventListener('click', () => { if (!lb) return; $('img', lb).src = img.src; openPanel(lb, '[data-close]'); });
    lb?.addEventListener('click', (e) => { if (e.target === lb) closePanels(); });
  }
  $$('[data-tabs]').forEach((t) => {
    const tabs = $$('[role="tab"]', t), panes = $$('[role="tabpanel"]', t);
    const sel = (k) => { tabs.forEach((b, j) => { b.setAttribute('aria-selected', String(j === k)); b.tabIndex = j === k ? 0 : -1; }); panes.forEach((p, j) => { p.hidden = j !== k; }); };
    tabs.forEach((b, k) => { b.addEventListener('click', () => sel(k)); b.addEventListener('keydown', (e) => { if (e.key === 'ArrowRight') { sel((k + 1) % tabs.length); tabs[(k + 1) % tabs.length].focus(); } if (e.key === 'ArrowLeft') { sel((k + tabs.length - 1) % tabs.length); tabs[(k + tabs.length - 1) % tabs.length].focus(); } }); });
    sel(0);
  });
  const sticky = $('[data-stickybar]'), buyRow = $('[data-buyrow]');
  if (sticky && buyRow && 'IntersectionObserver' in window) {
    new IntersectionObserver(([en]) => sticky.classList.toggle('is-shown', !en.isIntersecting && en.boundingClientRect.top < 0), { threshold: 0 }).observe(buyRow);
  }

  /* ── Forms: quote + contact post to the server and swap in its htmx fragment.
        Delegated, so a re-rendered form (e.g. with validation errors) keeps working. ── */
  document.addEventListener('submit', async (e) => {
    const form = e.target.closest('form[data-ajax]'); if (!form) return;
    e.preventDefault();
    const target = form.closest('[data-form-target]') || form.parentElement, btn = $('[type=submit]', form), label = btn?.textContent;
    if (btn) { btn.disabled = true; btn.textContent = 'Sending…'; }
    try {
      const r = await fetch(form.action, { method: 'POST', body: new FormData(form), headers: { 'HX-Request': 'true' }, credentials: 'same-origin' });
      const tpl = document.createElement('template');
      tpl.innerHTML = (await r.text()).trim();
      const next = tpl.content.firstElementChild;
      target.replaceWith(next);
      next.scrollIntoView({ block: 'nearest', behavior: reduced ? 'auto' : 'smooth' });
    } catch (err) {
      if (btn) { btn.disabled = false; btn.textContent = label; }
      toast('Network problem. Please try again.');
    }
  });
  /* ── Cart page: live quote (goods + shipping for the chosen country + exchange rate), then pay ── */
  const orderForm = $('[data-order-form]');
  if (orderForm) {
    const country = $('[name=country]', orderForm), expected = $('[data-expected-total]', orderForm);
    const payBtns = () => $$('[data-pay-btn], [data-request-btn]', orderForm);
    let timer = null, seq = 0, quiet = false, lastQuote = null;
    // One key per visit to this page: a double-click or retry reuses the same payment instead of creating a second order.
    const checkoutKey = (window.crypto && crypto.randomUUID) ? crypto.randomUUID() : String(Date.now()) + Math.random().toString(16).slice(2);

    const setText = (sel, v) => $$(sel, orderForm).forEach((el) => { el.textContent = v; });
    function applyQuote(d) {
      lastQuote = d; expected.value = d.total;
      setText('[data-q-subtotal]', d.subtotal_fmt); setText('[data-q-shipping]', d.shipping_fmt);
      setText('[data-q-ship-label]', d.shipping_label); setText('[data-q-total]', d.total_fmt);
      const rate = $('[data-q-rate]', orderForm); rate.textContent = d.rate_text; rate.hidden = !d.rate_text;
      $('[data-q-notes]', orderForm).innerHTML = (d.notes || []).map((n) => `<li>${esc(n)}</li>`).join('');
      $('[data-q-error]', orderForm).hidden = true;
      // keep the browser's cart snapshot in step with the server's prices (rate moves, admin edits)
      let changed = false;
      cart.forEach((i) => { const p = d.prices[i.slug]; if (p && (i.usd !== p.usd || i.ngn !== p.ngn)) { i.usd = p.usd; i.ngn = p.ngn; changed = true; } });
      if (changed) { quiet = true; saveCart(); quiet = false; }
      // a product that cannot be exported (e.g. shea nuts) blocks payment until the buyer fixes the cart or the country
      const blocked = Array.isArray(d.blocked) && d.blocked.length > 0, alertBox = $('[data-q-blocked]', orderForm);
      if (alertBox) { alertBox.textContent = blocked ? d.blocked_notice : ''; alertBox.hidden = !blocked; }
      orderForm.classList.remove('is-quoting'); payBtns().forEach((b) => { b.disabled = blocked; });
    }
    async function requestQuote() {
      if (!cart.length) return;
      const mine = ++seq;
      orderForm.classList.add('is-quoting'); payBtns().forEach((b) => { b.disabled = true; });   // never let anyone pay a stale total
      const fd = new FormData(); fd.set('cart', JSON.stringify(cart.map((i) => ({ slug: i.slug, qty: i.qty })))); fd.set('country', country.value);
      fd.set('csrfmiddlewaretoken', $('[name=csrfmiddlewaretoken]', orderForm).value);
      try {
        const r = await fetch(orderForm.dataset.quoteUrl, { method: 'POST', body: fd, credentials: 'same-origin' });
        const d = await r.json();
        if (mine !== seq) return;                                  // a newer request is in flight
        if (!d.ok) throw new Error((d.errors && d.errors.__all__ && d.errors.__all__[0]) || 'quote failed');
        applyQuote(d);
      } catch (err) {
        if (mine !== seq) return;
        orderForm.classList.remove('is-quoting');
        const box = $('[data-q-error]', orderForm); box.hidden = false;
      }
    }
    const schedule = () => { clearTimeout(timer); orderForm.classList.add('is-quoting'); payBtns().forEach((b) => { b.disabled = true; }); timer = setTimeout(requestQuote, 150); };
    country?.addEventListener('change', schedule);
    document.addEventListener('currency:change', schedule);
    document.addEventListener('cart:change', () => { if (!quiet) schedule(); });
    $('[data-q-retry]', orderForm)?.addEventListener('click', requestQuote);
    schedule();

    orderForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      if (!cart.length) return toast('Your cart is empty');
      const btn = e.submitter || $('[type=submit]', orderForm), label = btn.innerHTML;
      const all = payBtns(); all.forEach((b) => { b.disabled = true; });
      btn.innerHTML = btn.value === 'paystack' ? 'Taking you to Paystack…' : 'Sending…';
      $$('.field', orderForm).forEach((f) => { f.classList.remove('has-error'); $('.field-error', f)?.remove(); });
      $('.form-alert:not([data-q-error])', orderForm)?.remove();
      const fd = new FormData(orderForm); fd.set('pay', btn.value || 'paystack'); fd.set('idem', checkoutKey);
      let redirecting = false;
      try {
        const r = await fetch(orderForm.action, { method: 'POST', body: fd, credentials: 'same-origin' });
        const data = await r.json();
        if (data.ok && data.redirect) { redirecting = true; location.href = data.redirect; return; }
        if (r.status === 409 && data.quote) applyQuote(data.quote);       // the rate moved: show the new total, ask them to confirm
        Object.entries(data.errors || {}).forEach(([k, msgs]) => {
          const el = k === '__all__' ? null : $(`[name="${k}"]`, orderForm);
          if (el) { const f = el.closest('.field'); f.classList.add('has-error'); f.insertAdjacentHTML('beforeend', `<p class="field-error">${esc(msgs[0])}</p>`); }
          else $('[data-q-error]', orderForm).insertAdjacentHTML('beforebegin', `<p class="form-alert" role="alert">${esc(msgs[0])}</p>`);
        });
        $('.has-error .input, .form-alert', orderForm)?.scrollIntoView({ block: 'center' });
      } catch (err) { $('[data-q-error]', orderForm).insertAdjacentHTML('beforebegin', '<p class="form-alert" role="alert">Network problem. Please try again.</p>'); }
      finally { if (!redirecting) { btn.innerHTML = label; all.forEach((b) => { b.disabled = !lastQuote; }); renderCart(); } }
    });
  }

  /* order status page: empty the cart once the order is settled; poll while payment is still confirming */
  if ($('[data-clear-cart]')) { cart = []; saveCart(); }
  const poll = $('[data-poll]');
  if (poll) {
    let tries = Number(sessionStorage.getItem('agronga-poll') || 0);
    if (tries < 12) { sessionStorage.setItem('agronga-poll', tries + 1); setTimeout(() => location.reload(), 5000); }
  }

  /* ── Misc: reveal on scroll, count-up, email reveal ── */
  if ('IntersectionObserver' in window) {
    const io = new IntersectionObserver((es) => es.forEach((en) => { if (en.isIntersecting) { en.target.classList.add('in'); io.unobserve(en.target); } }), { rootMargin: '0px 0px -8% 0px', threshold: .08 });
    $$('.reveal, .steps').forEach((el) => io.observe(el));
    const co = new IntersectionObserver((es) => es.forEach((en) => {
      if (!en.isIntersecting) return; co.unobserve(en.target);
      const to = Number(en.target.dataset.count), suffix = en.target.dataset.suffix || '';
      if (reduced) { en.target.textContent = to + suffix; return; }
      const t0 = performance.now(); (function tick(t) { const p = Math.min(1, (t - t0) / 1400); en.target.textContent = Math.round(to * (1 - Math.pow(1 - p, 3))) + suffix; if (p < 1) requestAnimationFrame(tick); })(t0);
    }), { threshold: .6 });
    $$('[data-count]').forEach((el) => co.observe(el));
  } else { $$('.reveal').forEach((el) => el.classList.add('in')); }
  $$('[data-email]').forEach((a) => { const addr = `${a.dataset.user}@${a.dataset.domain}`; a.href = `mailto:${addr}`; (a.querySelector('span') || a).textContent = addr; });

  renderCart();
})();
