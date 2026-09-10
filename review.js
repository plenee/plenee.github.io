/* Plenee Academy Review — generator-injected reviewer tooling for live Academy pages.

   Ported from the app's frontend/src/pages/ReviewPage.tsx per Rob's 2026-09-10 decision to move
   the review layer out of the app entirely ("the academy REVIEW was envisioned to allow
   highlighting and feedback text entry directly in the academy pages... it shouldn't be there
   [in the app]"). /Users/robert/Plenee/docs/academy_review_spec.md — the Plenee-root docs/ tree,
   a different repo from this one — is NOT moving and stays the reference for the anchoring
   mechanism, the data model, quiz review, and the pickup procedure; only the delivery
   architecture (in-app page vs. this script) changed. This file re-implements the same
   client-side logic without React so it runs directly on the live page instead of inside a copy
   ReviewPage.tsx used to fetch and re-render.

   Gate: inert for every normal reader, no network request, no DOM change. Activates only via
   ?review=1 in the URL (first visit, opens the sign-in card) or a stored, unexpired reviewer
   token (every visit after — see TOKEN_TTL_MS). A client-side gate was exactly what "Why not a
   bookmarklet" in the spec called not-a-real-control; every /review/* endpoint on the backend
   still re-checks the bearer token and the is_academy_reviewer flag regardless of what this
   script decides to show — that part of the architecture is unchanged from the app.

   Wire-up, on <body>: data-review-slug="<slug>" — emitted by generate_academy_v2.py only for
   pages backend/app/routers/review.py's GET /review/pages actually lists (chapters, the
   glossary, and the 5 quiz pages). Its absence means "nothing on this page to anchor a note
   against" — selection/notes stay off even for a signed-in reviewer, though the sign-in card
   itself still works on every page, so a first ?review=1 visit is never a dead end regardless of
   which page happens to carry it. */
(function () {
  'use strict';

  var API = 'https://api.plenee.com';
  /* Confirmed, not inferred — Website session grepped this as the literal baked-in VITE_API_URL
     shipping in app.plenee.com's own production bundle (2026-09-10). */

  var TOKEN_KEY = 'plenee_review_token';
  var TOKEN_EXP_KEY = 'plenee_review_token_exp';
  var TOKEN_TTL_MS = 3 * 24 * 60 * 60 * 1000; /* 3-day expiry, per academy_review_spec.md's
                                                  "Decisions" — localStorage itself has no TTL,
                                                  so the expiry timestamp is stored alongside the
                                                  token and checked on every read. */

  var body = document.body;
  var SLUG = body.getAttribute('data-review-slug') || '';
  var PAGE_URL = location.href.split('?')[0].split('#')[0];
  var ANCHOR_TAGS = 'p, dd, dt, h2, [data-qz]';

  /* ── token storage ─────────────────────────────────────────────────────────── */
  function readToken() {
    var t, exp;
    try {
      t = localStorage.getItem(TOKEN_KEY);
      exp = parseInt(localStorage.getItem(TOKEN_EXP_KEY), 10);
    } catch (e) { return null; }
    if (!t || !exp || isNaN(exp) || Date.now() > exp) return null;
    return t;
  }
  function storeToken(t) {
    try {
      localStorage.setItem(TOKEN_KEY, t);
      localStorage.setItem(TOKEN_EXP_KEY, String(Date.now() + TOKEN_TTL_MS));
    } catch (e) {}
  }
  function clearToken() {
    try {
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(TOKEN_EXP_KEY);
    } catch (e) {}
  }

  /* ── the gate itself — everything below this line only ever runs for an active reviewer. ─── */
  var params = new URLSearchParams(location.search);
  var hasToken = !!readToken();
  if (!params.has('review') && !hasToken) return; /* inert for every normal reader */

  /* ── API — same contract ReviewPage.tsx used, verified directly against the backend rather
     than assumed. ──────────────────────────────────────────────────────────────────────────── */
  function login(email, password) {
    /* POST /auth/login is an OAuth2-password-flow endpoint: form-encoded, NOT JSON, and the
       field is literally named `username` even though it is checked against the email column
       (backend/app/routers/auth.py:90,93) — the exact same gotcha
       frontend/src/api/client.ts's loginRequest() carries a comment about. */
    var form = 'username=' + encodeURIComponent(email) + '&password=' + encodeURIComponent(password);
    return fetch(API + '/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: form
    }).then(function (res) {
      if (!res.ok) throw new Error('Incorrect email or password');
      return res.json();
    });
  }
  function authedFetch(path, opts) {
    opts = opts || {};
    opts.headers = opts.headers || {};
    opts.headers['Authorization'] = 'Bearer ' + readToken();
    if (opts.body && !opts.headers['Content-Type']) opts.headers['Content-Type'] = 'application/json';
    return fetch(API + path, opts);
  }
  function whoami() {
    return authedFetch('/review/me').then(function (res) {
      if (!res.ok) throw new Error('Could not confirm reviewer status');
      return res.json();
    });
  }
  function fetchNotes(slug) {
    return authedFetch('/review/notes?chapter_slug=' + encodeURIComponent(slug))
      .then(function (res) { return res.ok ? res.json() : []; })
      .catch(function () { return []; });
  }
  function sendNote(anchor, instruction) {
    var payload = {}, k;
    for (k in anchor) { if (anchor.hasOwnProperty(k)) payload[k] = anchor[k]; }
    payload.instruction = instruction;
    return authedFetch('/review/notes', { method: 'POST', body: JSON.stringify(payload) })
      .then(function (res) {
        if (res.ok) return res.json();
        return res.json().catch(function () { return {}; }).then(function (j) {
          throw new Error((j && j.detail) || 'Could not save that note.');
        });
      });
  }

  /* ── anchoring — ported near-verbatim from ReviewPage.tsx:56-112 (offsetWithinBlock/
     rangeFromOffsets/markRange). Already plain DOM/Range API there, no React dependency to
     begin with, so this is close to a straight copy with `const`/arrow syntax undone. ────────── */
  function offsetWithinBlock(block, container, offset) {
    var r = document.createRange();
    r.selectNodeContents(block);
    r.setEnd(container, offset);
    return r.toString().length;
  }
  function rangeFromOffsets(block, start, end) {
    var walker = document.createTreeWalker(block, NodeFilter.SHOW_TEXT);
    var acc = 0, startNode = null, startOffset = 0, endNode = null, endOffset = 0, node, len;
    while ((node = walker.nextNode())) {
      len = node.data.length;
      if (startNode === null && acc + len >= start) { startNode = node; startOffset = start - acc; }
      if (acc + len >= end) { endNode = node; endOffset = end - acc; break; }
      acc += len;
    }
    if (!startNode || !endNode) return null;
    var r = document.createRange();
    r.setStart(startNode, startOffset);
    r.setEnd(endNode, endOffset);
    return r;
  }
  function markRange(range, noteId) {
    /* Skip the visual wrap (the note itself still saves either way) when the range already sits
       inside an earlier note's <mark> — two notes on the identical span otherwise nest and can
       leave a stray empty mark behind, since extractContents/insertNode were never designed to
       re-wrap an already-wrapped range (same real, low-priority gap ReviewPage.tsx had). */
    var ancestor = range.commonAncestorContainer;
    var container = ancestor.nodeType === 1 ? ancestor : ancestor.parentNode;
    var already = container && container.closest && container.closest('mark.review-note-mark');
    if (already) return false;
    var mark = document.createElement('mark');
    mark.className = 'review-note-mark';
    mark.setAttribute('data-note-id', String(noteId));
    try {
      mark.appendChild(range.extractContents());
      range.insertNode(mark);
      return true;
    } catch (e) {
      try { console.warn('Academy Review: could not visually mark note', noteId, e); } catch (e2) {}
      return false;
    }
  }

  /* ── tiny DOM-builder — this file has no build step, so no JSX; this is the plainest
     substitute that keeps the UI chrome below readable. ───────────────────────────────────── */
  function el(tag, attrs, kids) {
    var e = document.createElement(tag), k, i;
    for (k in attrs) {
      if (!attrs.hasOwnProperty(k)) continue;
      if (k === 'style') e.style.cssText = attrs[k];
      else e.setAttribute(k, attrs[k]);
    }
    kids = kids || [];
    for (i = 0; i < kids.length; i++) {
      e.appendChild(typeof kids[i] === 'string' ? document.createTextNode(kids[i]) : kids[i]);
    }
    return e;
  }
  var FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif";

  /* ── UI chrome — ported from ReviewPage.tsx:296-438's JSX/styling as plain DOM construction;
     same visual content (banner, popover with Cmd/Ctrl-Enter + Escape, floating "See notes"
     button + count badge, notes sheet), no React underneath it. ─────────────────────────────── */
  var pendingRange = null, pendingAnchor = null, notes = [];
  var popoverEl = null, sheetBtnEl = null, sheetEl = null;

  function buildBanner() {
    document.body.appendChild(el('div', {
      style: 'position:fixed; top:0; left:0; right:0; z-index:9999; background:#FFF6E3;' +
        'border-bottom:1px solid #F0C766; color:#8A5D00; padding:.5rem .9rem; text-align:center;' +
        'font:600 13px/1.4 ' + FONT + ';'
    }, [
      SLUG
        ? 'Reviewing — select any text below to leave a note. Nothing here is published.'
        : 'Academy Review is signed in, but this page has nothing to review.'
    ]));
  }

  function closePop() {
    if (popoverEl && popoverEl.parentNode) popoverEl.parentNode.removeChild(popoverEl);
    popoverEl = null;
    pendingRange = null;
    pendingAnchor = null;
  }

  function openPop(pos) {
    closePop();
    var textarea = el('textarea', {
      style: 'display:block; width:100%; min-height:88px; resize:vertical; font-size:.9rem;' +
        'padding:.55rem; border:1px solid #DDE8F0; border-radius:6px; box-sizing:border-box; font-family:inherit;'
    });
    function doSend() {
      var instruction = textarea.value.replace(/^\s+|\s+$/g, '');
      if (!instruction || !pendingAnchor || !pendingRange) return;
      var anchor = pendingAnchor, range = pendingRange;
      sendNote(anchor, instruction).then(function (note) {
        markRange(range, note.id);
        try { window.getSelection().removeAllRanges(); } catch (e) {}
        notes.push(note);
        renderSheetButton();
        refreshSheetIfOpen();
        closePop();
      }).catch(function (err) {
        try { window.alert(err.message || 'Could not save that note.'); } catch (e) {}
      });
    }
    textarea.addEventListener('keydown', function (e) {
      if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') doSend();
      if (e.key === 'Escape') closePop();
    });
    var cancelBtn = el('button', { type: 'button' }, ['Cancel']);
    cancelBtn.addEventListener('click', closePop);
    var sendBtn = el('button', { type: 'button', style: 'background:#E8A317; border-color:#E8A317; color:#3D2900;' }, ['Send']);
    sendBtn.addEventListener('click', doSend);
    popoverEl = el('div', {
      style: 'position:absolute; top:' + pos.top + 'px; left:' + pos.left + 'px; z-index:9970;' +
        'width:330px; background:#fff; border:1px solid #F0C766; border-radius:9px;' +
        'box-shadow:0 14px 40px rgba(14,30,43,.22); overflow:hidden; font-family:' + FONT + ';'
    }, [
      el('div', { style: 'padding:.6rem;' }, [textarea]),
      el('div', { style: 'display:flex; gap:8px; justify-content:flex-end; padding:0 .6rem .6rem;' }, [cancelBtn, sendBtn])
    ]);
    document.body.appendChild(popoverEl);
    textarea.focus();
  }

  function onMouseUp() {
    if (!SLUG) return;
    var container = document.querySelector('.chapter-body');
    var sel = window.getSelection();
    var text = (sel ? sel.toString() : '').replace(/^\s+|\s+$/g, '');
    if (!sel || sel.rangeCount === 0 || text.length < 3) { closePop(); return; }
    var range = sel.getRangeAt(0);
    if (!container || !container.contains(range.commonAncestorContainer)) return;

    var startEl = range.startContainer.nodeType === 1 ? range.startContainer : range.startContainer.parentElement;
    var endEl = range.endContainer.nodeType === 1 ? range.endContainer : range.endContainer.parentElement;
    var startBlock = startEl && startEl.closest(ANCHOR_TAGS);
    var endBlock = endEl && endEl.closest(ANCHOR_TAGS);
    if (!startBlock || startBlock !== endBlock) {
      try { window.alert('Select text within a single paragraph, entry, question, or option.'); } catch (e) {}
      return;
    }

    var paragraph = startBlock.textContent || '';
    var start_index = offsetWithinBlock(startBlock, range.startContainer, range.startOffset);
    var end_index = offsetWithinBlock(startBlock, range.endContainer, range.endOffset);
    if (end_index <= start_index || end_index > paragraph.length) { closePop(); return; }

    var qzKind = startBlock.getAttribute('data-qz'); /* 'q' | 'o' | null */
    var anchor = {
      chapter_slug: SLUG,
      page_url: PAGE_URL,
      element: startBlock.tagName.toLowerCase(),
      paragraph: paragraph,
      start_index: start_index,
      end_index: end_index
    };
    if (qzKind) {
      var qi = parseInt(startBlock.getAttribute('data-qi'), 10);
      anchor.element = 'qz-' + qzKind;
      anchor.question_index = qi;
      /* The quiz's own question/option data lives in #quiz-data's JSON — the same blob the
         page's own inline script (QUIZ_JS, generate_academy_v2.py) already read once to build
         this DOM in the first place. Re-read it here rather than threading a reference through,
         since this handler has no other connection to it. */
      try {
        var qd = JSON.parse(document.getElementById('quiz-data').textContent);
        var item = qd.items[qi];
        if (item) {
          anchor.question_text = item.q;
          anchor.quiz_options = item.options;
          anchor.quiz_answer = item.answer;
          anchor.quiz_explanation = item.why;
        }
      } catch (e) {}
    }

    pendingRange = range.cloneRange();
    pendingAnchor = anchor;
    var r = range.getBoundingClientRect();
    openPop({
      top: window.scrollY + r.bottom + 8,
      left: Math.min(Math.max(12, window.scrollX + r.left), window.innerWidth - 350)
    });
  }

  function renderSheetButton() {
    if (sheetBtnEl && sheetBtnEl.parentNode) sheetBtnEl.parentNode.removeChild(sheetBtnEl);
    if (notes.length === 0) return;
    sheetBtnEl = el('button', {
      type: 'button',
      style: 'position:fixed; right:20px; bottom:20px; z-index:9965; display:flex;' +
        'align-items:center; gap:8px; background:#fff; border:1px solid #DDE8F0; border-radius:999px;' +
        'padding:.5rem .8rem .5rem 1rem; box-shadow:0 6px 20px rgba(14,30,43,.14); cursor:pointer;' +
        'font:600 14px ' + FONT + ';'
    }, [
      'See notes',
      el('span', {
        style: 'background:#FFF6E3; color:#8A5D00; border-radius:999px; padding:.05rem .5rem;' +
          'font-size:12px; font-weight:700;'
      }, [String(notes.length)])
    ]);
    sheetBtnEl.addEventListener('click', toggleSheet);
    document.body.appendChild(sheetBtnEl);
  }

  function scrollToNote(id) {
    var mark = document.querySelector('mark[data-note-id="' + id + '"]');
    if (!mark) return;
    mark.scrollIntoView({ behavior: 'smooth', block: 'center' });
    var marks = document.querySelectorAll('mark.review-note-mark'), i;
    for (i = 0; i < marks.length; i++) marks[i].classList.remove('review-note-active');
    mark.classList.add('review-note-active');
  }

  // Split from toggleSheet() so a note sent while the sheet is already open can refresh just
  // this part in place (see doSend() above) rather than the sheet only picking up the new note
  // the next time it's closed and reopened.
  function sheetList() {
    var list = el('div', { style: 'max-height:340px; overflow:auto; padding:.35rem;' });
    notes.forEach(function (n) {
      var quoted = n.selected.length > 60 ? n.selected.slice(0, 60) + '…' : n.selected;
      var quoteLine = el('div', { style: 'color:#8A9EB0; font-size:12px; margin-top:4px; cursor:pointer;' }, ['“' + quoted + '”']);
      quoteLine.addEventListener('click', function () { scrollToNote(n.id); });
      list.appendChild(el('div', { style: 'padding:.55rem; border-radius:7px;' }, [
        el('div', { style: 'font-size:13px; line-height:1.5;' }, [n.instruction]),
        quoteLine
      ]));
    });
    return list;
  }

  function refreshSheetIfOpen() {
    if (!sheetEl) return;
    sheetEl.replaceChild(sheetList(), sheetEl.lastChild);
  }

  function toggleSheet() {
    if (sheetEl && sheetEl.parentNode) { sheetEl.parentNode.removeChild(sheetEl); sheetEl = null; return; }
    var closeBtn = el('button', { type: 'button', style: 'border:0; background:none; font-size:19px; line-height:1; cursor:pointer;' }, ['×']);
    closeBtn.addEventListener('click', toggleSheet);
    sheetEl = el('div', {
      style: 'position:fixed; right:20px; bottom:72px; z-index:9966; width:360px; background:#fff;' +
        'border:1px solid #DDE8F0; border-radius:11px; box-shadow:0 14px 40px rgba(14,30,43,.2);' +
        'overflow:hidden; font-family:' + FONT + ';'
    }, [
      el('div', {
        style: 'padding:.65rem .5rem .65rem .85rem; border-bottom:1px solid #DDE8F0; display:flex;' +
          'align-items:center; justify-content:space-between;'
      }, [el('b', { style: 'font-size:14px;' }, ['Notes for this page']), closeBtn]),
      sheetList()
    ]);
    document.body.appendChild(sheetEl);
  }

  /* ── sign-in card — shown instead of the banner until a valid reviewer session exists. Every
     field/behavior here mirrors ReviewPage.tsx's own reviewer gate, just without the app's
     login PAGE around it, since this has to appear directly on top of whatever Academy page it
     landed on. ──────────────────────────────────────────────────────────────────────────────── */
  function buildSignInCard(onSignedIn) {
    var emailInput = el('input', {
      type: 'email', placeholder: 'Email',
      style: 'display:block; width:100%; margin-bottom:6px; padding:.4rem .55rem;' +
        'border:1px solid #DDE8F0; border-radius:6px; box-sizing:border-box; font-family:inherit;'
    });
    var pwInput = el('input', {
      type: 'password', placeholder: 'Password',
      style: 'display:block; width:100%; margin-bottom:8px; padding:.4rem .55rem;' +
        'border:1px solid #DDE8F0; border-radius:6px; box-sizing:border-box; font-family:inherit;'
    });
    var errEl = el('div', { style: 'color:#B23B3B; font-size:12px; margin-bottom:6px; display:none;' });
    var goBtn = el('button', { type: 'button', style: 'background:#E8A317; border-color:#E8A317; color:#3D2900;' }, ['Sign in']);
    function attempt() {
      errEl.style.display = 'none';
      login(emailInput.value, pwInput.value).then(function (tok) {
        storeToken(tok.access_token);
        return whoami();
      }).then(function (me) {
        if (!me.is_reviewer) {
          clearToken();
          throw new Error('This account is not an Academy reviewer.');
        }
        onSignedIn();
      }).catch(function (err) {
        errEl.textContent = err.message || 'Sign-in failed.';
        errEl.style.display = 'block';
      });
    }
    goBtn.addEventListener('click', attempt);
    pwInput.addEventListener('keydown', function (e) { if (e.key === 'Enter') attempt(); });
    var card = el('div', {
      style: 'position:fixed; top:12px; right:12px; z-index:9999; width:240px; background:#fff;' +
        'border:1px solid #DDE8F0; border-radius:9px; box-shadow:0 14px 40px rgba(14,30,43,.22);' +
        'padding:.7rem; font-family:' + FONT + ';'
    }, [
      el('div', { style: 'font:700 13px ' + FONT + '; margin-bottom:8px;' }, ['Academy Review sign-in']),
      emailInput, pwInput, errEl, goBtn
    ]);
    document.body.appendChild(card);
    return card;
  }

  /* ── boot ─────────────────────────────────────────────────────────────────────────────────── */
  function activate() {
    buildBanner();
    if (!SLUG) return; /* nothing on this page to select/anchor, see the file header comment */
    var container = document.querySelector('.chapter-body');
    if (!container) return;
    container.addEventListener('mouseup', onMouseUp);
    fetchNotes(SLUG).then(function (existing) {
      notes = existing;
      renderSheetButton();
      /* Re-highlight notes that already existed for this page — exact-match only, same "if the
         generator transformed it, that's worth reporting, not guessing" spirit as the spec's own
         pickup resolution order, just applied to this convenience highlight rather than the real
         editorial step. A note that cannot be re-found this way still exists server-side; it
         just will not show an in-page mark to click into. */
      var blocks = Array.prototype.slice.call(container.querySelectorAll(ANCHOR_TAGS));
      existing.forEach(function (note) {
        var block = null, i;
        for (i = 0; i < blocks.length; i++) {
          if (blocks[i].textContent === note.paragraph) { block = blocks[i]; break; }
        }
        if (!block) return;
        var range = rangeFromOffsets(block, note.start_index, note.end_index);
        if (range) markRange(range, note.id);
      });
    });
  }

  var existingToken = readToken();
  if (existingToken) {
    whoami().then(function (me) {
      if (me.is_reviewer) activate();
      else clearToken();
    }).catch(function () { clearToken(); });
  } else {
    var card = buildSignInCard(function () {
      if (card && card.parentNode) card.parentNode.removeChild(card);
      activate();
    });
  }
})();
