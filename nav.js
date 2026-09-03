/* Plenee shared nav behaviour — plenee.com and plenee.com/academy/.
   app.plenee.com reimplements the cross-tab half in React (frontend/src/utils/crossTab.ts);
   the two are deliberately separate deploy units, so that small duplication is on purpose.

   Wire-up, on <body>:
     data-plenee-surface="home" | "academy"
     data-plenee-home="index.html"          (relative, so file:// still works)
     data-plenee-academy="academy/index.html"

   Three things happen here:
     1. the nav collapses past the top of the page and the wordmark clips away
     2. the account menu is built from the surface plus the sign-in hint cookie
     3. Academy and Navigator open in NAMED tabs, so a second click focuses rather
        than duplicates
*/
(function () {
  'use strict';

  var body = document.body;
  var SURFACE = body.getAttribute('data-plenee-surface') || 'home';
  var NAVIGATOR_URL = 'https://app.plenee.com/';

  var TARGETS = {
    home:      { name: 'plenee-home',      label: 'Plenee' },
    academy:   { name: 'plenee-academy',   label: 'Academy' },
    navigator: { name: 'plenee-navigator', label: 'Navigator' }
  };
  function urlFor(key) {
    if (key === 'navigator') return NAVIGATOR_URL;
    if (key === 'academy')   return body.getAttribute('data-plenee-academy') || '/academy/';
    return body.getAttribute('data-plenee-home') || '/';
  }

  /* This tab announces its own identity so the OTHER surface's window.open(url, name)
     can find it. Without this the return trip opens a duplicate. */
  try { if (!window.name) window.name = TARGETS[SURFACE].name; } catch (e) {}

  /* ── cookies ───────────────────────────────────────────────────────────────
     Shared across plenee.com and app.plenee.com because they sit under the same
     registrable domain. BroadcastChannel and localStorage are origin-scoped and
     cannot cross that boundary, so a cookie is the only channel available.

     plenee_auth_hint is a DISPLAY HINT ONLY. It decides which menu items to draw and
     nothing else; it is not httpOnly, carries no identity, and grants no access. Every
     real check stays server-side against the bearer token. */
  var COOKIE_DOMAIN = /(^|\.)plenee\.com$/.test(location.hostname) ? '; domain=.plenee.com' : '';

  function readCookie(k) {
    var m = document.cookie.match('(^|;)\\s*' + k + '\\s*=\\s*([^;]+)');
    return m ? decodeURIComponent(m[2]) : '';
  }
  function writeCookie(k, v, maxAge) {
    document.cookie = k + '=' + encodeURIComponent(v) + '; path=/' + COOKIE_DOMAIN +
      '; max-age=' + maxAge + '; samesite=lax' + (location.protocol === 'https:' ? '; secure' : '');
  }

  function signedIn() { return readCookie('plenee_auth_hint') === '1'; }

  /* Liveness. Each surface stamps the clock; a stamp older than the window means that
     tab is gone. Stamped every 20s rather than continuously — the dot only has to be
     right at the moment the menu opens, so a fast poll would burn cycles for nothing. */
  var HEARTBEAT_MS = 20000, STALE_MS = 65000;
  function stamp() { writeCookie('plenee_tab_' + SURFACE, String(Date.now()), 90); }
  function tabLooksOpen(key) {
    if (handles[key] && !handles[key].closed) return true;   // exact, while we hold it
    var t = parseInt(readCookie('plenee_tab_' + key), 10);
    return !!t && (Date.now() - t) < STALE_MS;
  }
  stamp();
  setInterval(stamp, HEARTBEAT_MS);
  window.addEventListener('pagehide', function () {
    writeCookie('plenee_tab_' + SURFACE, '', 0);             // leaving: drop the stamp
  });

  /* ── open or focus ─────────────────────────────────────────────────────────
     A named target opens a tab if none carries that name, and focuses the existing one
     if it does. The one case it cannot cover: tabs opened independently of each other
     (two bookmarks) are in separate browsing context groups, and no browser exposes a
     way to focus an arbitrary tab. Then this opens a fresh one. */
  var handles = {};
  function openOrFocus(key) {
    var t = TARGETS[key];
    var w = window.open(urlFor(key), t.name);
    if (w) { handles[key] = w; try { w.focus(); } catch (e) {} }
  }

  /* ── account menu ──────────────────────────────────────────────────────────── */
  var acct = document.querySelector('.nav-acct');
  var userBtn = acct && acct.querySelector('.nav-user');
  var menu = acct && acct.querySelector('.nav-menu');
  var cta = document.querySelector('.nav-cta');

  var LINES = '<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor"'
    + ' stroke-width="2" stroke-linecap="round" aria-hidden="true">'
    + '<line x1="4" y1="7" x2="20" y2="7"/><line x1="4" y1="12" x2="20" y2="12"/>'
    + '<line x1="4" y1="17" x2="20" y2="17"/></svg>';

  function row(cls) {
    var b = document.createElement('button');
    b.type = 'button'; b.className = 'nav-mi'; b.setAttribute('role', 'menuitem');
    var d = document.createElement('span'); d.className = cls;
    b.appendChild(d);
    return b;
  }

  function buildMenu() {
    if (!menu) return;
    menu.textContent = '';
    var signed = signedIn();

    /* the surfaces you are NOT on. Home is reached by the mark, so it is not listed. */
    ['navigator', 'academy'].forEach(function (key) {
      if (key === SURFACE) return;
      var live = tabLooksOpen(key);
      var b = row('nav-dot' + (live ? ' is-live' : ''));
      b.appendChild(document.createTextNode(TARGETS[key].label));
      b.title = live ? TARGETS[key].label + ' is open — switch to that tab'
                     : 'Open ' + TARGETS[key].label + ' in a new tab';
      b.addEventListener('click', function () { close_(); openOrFocus(key); });
      menu.appendChild(b);
    });

    var sep = document.createElement('div'); sep.className = 'nav-sep';
    menu.appendChild(sep);

    if (signed) {
      var out = row('nav-dot is-blank');
      out.appendChild(document.createTextNode('Sign out'));
      out.addEventListener('click', function () {
        writeCookie('plenee_auth_hint', '', 0);
        close_();
        /* the token lives on app.plenee.com and cannot be cleared from here, so the
           real sign-out happens in the app's own tab */
        var w = window.open(NAVIGATOR_URL + 'logout', TARGETS.navigator.name);
        if (w) { handles.navigator = w; try { w.focus(); } catch (e) {} }
        render();
      });
      menu.appendChild(out);
    } else {
      [['Sign in', 'login'], ['Register', 'register']].forEach(function (p) {
        var a = document.createElement('a');
        a.className = 'nav-mi'; a.setAttribute('role', 'menuitem');
        a.href = NAVIGATOR_URL + p[1];
        a.target = TARGETS.navigator.name;
        var d = document.createElement('span'); d.className = 'nav-dot is-blank';
        a.appendChild(d);
        a.appendChild(document.createTextNode(p[0]));
        a.addEventListener('click', close_);
        menu.appendChild(a);
      });
    }
  }

  function render() {
    var signed = signedIn();
    if (userBtn) {
      userBtn.classList.toggle('is-signed', signed);
      if (signed) userBtn.textContent = (readCookie('plenee_user_initial') || 'A').toUpperCase();
      else userBtn.innerHTML = LINES;
      userBtn.setAttribute('aria-label', signed ? 'Account menu' : 'Menu');
    }
    if (cta) cta.hidden = signed;          /* signed in: the Sign In CTA has no job */
    buildMenu();
  }

  function close_() {
    if (menu) menu.hidden = true;
    if (userBtn) userBtn.setAttribute('aria-expanded', 'false');
  }

  if (userBtn) {
    userBtn.addEventListener('click', function (e) {
      e.stopPropagation();
      var wasOpen = !menu.hidden;
      close_();
      if (!wasOpen) {
        buildMenu();                        /* rebuild so the dots are current on open */
        menu.hidden = false;
        userBtn.setAttribute('aria-expanded', 'true');
      }
    });
    document.addEventListener('click', function (e) {
      if (menu && !menu.hidden && !acct.contains(e.target)) close_();
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') close_();
    });
  }

  /* ── the mark is the only way home ─────────────────────────────────────────── */
  var home = document.querySelector('.nav-home');
  if (home) {
    home.addEventListener('click', function (e) {
      e.preventDefault();
      if (SURFACE === 'home') window.scrollTo({ top: 0, behavior: 'smooth' });
      else openOrFocus('home');
    });
  }

  /* ── collapse past the top ─────────────────────────────────────────────────── */
  var navEl = document.querySelector('nav');
  if (navEl) {
    var MIN_DEPTH = 60, ticking = false;
    window.addEventListener('scroll', function () {
      if (ticking) return;
      ticking = true;
      requestAnimationFrame(function () {
        ticking = false;
        navEl.classList.toggle('is-collapsed', window.scrollY > MIN_DEPTH);
      });
    }, { passive: true });
  }

  /* ── mobile section links ──────────────────────────────────────────────────── */
  var toggle = document.getElementById('nav-toggle');
  var links = document.getElementById('nav-links');
  if (toggle && links) {
    toggle.addEventListener('click', function () {
      var open = links.classList.toggle('open');
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
    links.querySelectorAll('a').forEach(function (a) {
      a.addEventListener('click', function () {
        links.classList.remove('open');
        toggle.setAttribute('aria-expanded', 'false');
      });
    });
  }

  render();
  /* coming back via bfcache, or from another tab: the hint may have changed */
  window.addEventListener('pageshow', render);
  document.addEventListener('visibilitychange', function () {
    if (!document.hidden) { stamp(); render(); }
  });
})();
