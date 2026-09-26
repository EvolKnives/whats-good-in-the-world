(function () {
  "use strict";

  var storiesEl = document.getElementById("stories");
  var statusEl = document.getElementById("status");
  var weekLabelEl = document.getElementById("week-label");
  var headerEl = document.getElementById("site-header");
  var shareWeekBtn = document.getElementById("share-week");
  var toastEl = document.getElementById("toast");
  var lightboxEl = document.getElementById("lightbox");
  var lightboxImg = document.getElementById("lightbox-img");
  var lightboxClose = document.getElementById("lightbox-close");
  var refreshBtn = document.getElementById("refresh-week");
  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var openArticle = null;
  var weekMeta = { weekOf: "", label: "This week" };
  var toastTimer = null;
  var lightboxOpen = false;
  var currentFingerprint = "";
  var loadingWeek = false;
  var SITE_TITLE = "What's Good In The World?";
  var storyPool = [];
  var displayedStories = [];
  var SET_SIZE = 15;
  var SEEN_KEY = "wgw-seen-ids";

  document.documentElement.classList.add("js");

  function tierFromImpact(impact) {
    var n = Math.max(1, Math.min(5, Number(impact) || 3));
    if (n >= 5) return "hero";
    if (n >= 4) return "featured";
    if (n >= 3) return "standard";
    if (n >= 2) return "compact";
    return "minimal";
  }

  function formatWeekOf(isoDate) {
    var d = new Date(isoDate + "T12:00:00");
    if (Number.isNaN(d.getTime())) return "This week";
    return d.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric"
    });
  }

  function slugify(str) {
    return String(str || "story")
      .toLowerCase()
      .replace(/['']/g, "")
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "")
      .slice(0, 56) || "story";
  }

  function storyId(story, index) {
    if (story && story.id) return "story-" + slugify(story.id);
    return "story-" + slugify(story && story.title) + "-" + index;
  }

  function stableStoryKey(story, index) {
    if (story && story.id) return String(story.id);
    return slugify(story && story.title) + "::" + index;
  }

  function shuffleInPlace(arr) {
    for (var i = arr.length - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1));
      var t = arr[i];
      arr[i] = arr[j];
      arr[j] = t;
    }
    return arr;
  }

  function uniqueIds(ids) {
    var seen = {};
    return (Array.isArray(ids) ? ids : []).map(String).filter(function (id) {
      if (seen[id]) return false;
      seen[id] = true;
      return true;
    });
  }

  function readSeenState(weekOf) {
    var requestedWeek = weekOf ? String(weekOf) : "";
    try {
      var raw = localStorage.getItem(SEEN_KEY);
      var parsed = raw ? JSON.parse(raw) : null;
      var storedWeek = parsed && !Array.isArray(parsed) ? String(parsed.weekOf || "") : "";
      var ids = parsed && !Array.isArray(parsed) ? parsed.ids : parsed;

      // A new weekly pool gets a soft reset, without losing the current round
      // when the page is merely reopened during the same week.
      if (requestedWeek && storedWeek && requestedWeek !== storedWeek) {
        return { weekOf: requestedWeek, ids: [] };
      }
      return {
        weekOf: requestedWeek || storedWeek,
        ids: uniqueIds(ids)
      };
    } catch (e) {
      return { weekOf: requestedWeek, ids: [] };
    }
  }

  function readSeenIds(weekOf) {
    return readSeenState(weekOf).ids;
  }

  function writeSeenIds(ids, weekOf) {
    try {
      localStorage.setItem(
        SEEN_KEY,
        JSON.stringify({
          weekOf: weekOf ? String(weekOf) : String(weekMeta.weekOf || ""),
          ids: uniqueIds(ids)
        })
      );
    } catch (e) {
      /* ignore quota / private mode */
    }
  }

  function primaryImageKey(story) {
    var imgs = storyImages(story);
    return imgs.length ? String(imgs[0]) : "";
  }

  function pickDisjointSet(pool, avoidIds, count) {
    var avoid = {};
    (avoidIds || []).forEach(function (id) {
      avoid[String(id)] = true;
    });
    var fresh = [];
    var reused = [];
    pool.forEach(function (story, index) {
      var key = stableStoryKey(story, index);
      if (avoid[key]) reused.push(story);
      else fresh.push(story);
    });
    shuffleInPlace(fresh);
    shuffleInPlace(reused);

    // Prefer unique primary photo paths so Refresh never paints the same
    // bytes twice on screen when the pool still has unused images.
    var usedImg = {};
    var picked = [];

    function takePreferUnique(source) {
      var deferred = [];
      source.forEach(function (story) {
        if (picked.length >= count) return;
        var img = primaryImageKey(story);
        if (img && usedImg[img]) {
          deferred.push(story);
          return;
        }
        if (img) usedImg[img] = true;
        picked.push(story);
      });
      deferred.forEach(function (story) {
        if (picked.length >= count) return;
        var img = primaryImageKey(story);
        if (img) usedImg[img] = true;
        picked.push(story);
      });
    }

    takePreferUnique(fresh);
    if (picked.length < count) takePreferUnique(reused);
    return picked.slice(0, count);
  }

  function pageUrl(hash) {
    var base = location.origin + location.pathname + location.search;
    return hash ? base + "#" + hash : base.replace(/#$/, "");
  }

  function showToast(msg) {
    if (!toastEl) return;
    toastEl.hidden = false;
    toastEl.textContent = msg;
    toastEl.classList.add("is-on");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () {
      toastEl.classList.remove("is-on");
      setTimeout(function () {
        toastEl.hidden = true;
      }, 280);
    }, 1800);
  }

  function copyText(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(text);
    }
    return new Promise(function (resolve, reject) {
      var ta = document.createElement("textarea");
      ta.value = text;
      ta.setAttribute("readonly", "");
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      try {
        if (document.execCommand("copy")) resolve();
        else reject(new Error("copy failed"));
      } catch (e) {
        reject(e);
      }
      document.body.removeChild(ta);
    });
  }

  function canNativeShare() {
    return typeof navigator.share === "function";
  }

  function sharePayload(data) {
    var payload = {
      title: data.title || SITE_TITLE,
      text: data.text || "",
      url: data.url || pageUrl()
    };

    if (canNativeShare()) {
      return navigator
        .share(payload)
        .then(function () {
          /* user completed or dismissed — no toast needed */
        })
        .catch(function (err) {
          if (err && err.name === "AbortError") return;
          return copyText(payload.url).then(function () {
            showToast("Link copied");
          });
        });
    }

    return copyText(payload.url).then(function () {
      showToast("Link copied");
    }).catch(function () {
      showToast("Couldn’t share");
    });
  }

  function youtubeId(url) {
    if (!url || typeof url !== "string") return null;
    var m = url.match(
      /(?:youtube\.com\/(?:watch\?v=|embed\/|shorts\/)|youtu\.be\/)([A-Za-z0-9_-]{6,})/
    );
    return m ? m[1] : null;
  }


  function openLightbox(src, alt) {
    if (!lightboxEl || !lightboxImg || !src) return;
    lightboxImg.src = src;
    lightboxImg.alt = alt || "";
    lightboxEl.hidden = false;
    lightboxEl.setAttribute("aria-hidden", "false");
    // Force reflow so open transition plays
    void lightboxEl.offsetWidth;
    lightboxEl.classList.add("is-open");
    document.body.classList.add("lightbox-open");
    lightboxOpen = true;
    if (lightboxClose) lightboxClose.focus({ preventScroll: true });
  }

  function closeLightbox() {
    if (!lightboxEl || !lightboxOpen) return;
    lightboxEl.classList.remove("is-open");
    document.body.classList.remove("lightbox-open");
    lightboxOpen = false;
    lightboxEl.setAttribute("aria-hidden", "true");
    setTimeout(function () {
      if (!lightboxOpen) {
        lightboxEl.hidden = true;
        if (lightboxImg) {
          lightboxImg.removeAttribute("src");
          lightboxImg.alt = "";
        }
      }
    }, reduceMotion ? 0 : 300);
  }

  function isLocalImage(src) {
    return typeof src === "string" && !/^https?:\/\//i.test(src);
  }

  function storyImages(story) {
    return Array.isArray(story.images) ? story.images.filter(Boolean) : [];
  }

  function preloadStoryImages(stories, limit) {
    var list = (stories || []).slice(0, limit || 4);
    var jobs = [];
    list.forEach(function (story) {
      var src = storyImages(story)[0];
      if (!src) return;
      jobs.push(
        new Promise(function (resolve) {
          var img = new Image();
          img.decoding = "async";
          img.onload = function () {
            resolve(src);
          };
          img.onerror = function () {
            resolve(null);
          };
          img.src = src;
        })
      );
    });
    return Promise.all(jobs);
  }

  function bindLightbox(el, src, alt) {
    function openThis(e) {
      if (e) e.preventDefault();
      openLightbox(src, alt || "");
    }
    el.addEventListener("click", openThis);
    el.addEventListener("keydown", function (e) {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        openThis(e);
      }
    });
  }

  function makePhoto(src, alt, opts) {
    opts = opts || {};
    var img = document.createElement("img");
    img.className = "story__photo";
    img.alt = alt || "";
    img.width = 1200;
    img.height = 750;
    img.decoding = "async";
    if (opts.eager) {
      img.loading = "eager";
      img.setAttribute("fetchpriority", "high");
    } else {
      img.loading = "lazy";
    }
    if (!isLocalImage(src)) {
      img.referrerPolicy = "no-referrer";
    }
    img.classList.add("is-loading");
    function markLoaded() {
      img.classList.remove("is-loading");
      img.classList.add("is-loaded");
    }
    if (img.complete && img.naturalWidth) {
      markLoaded();
    } else {
      img.addEventListener("load", markLoaded, { once: true });
    }
    img.addEventListener(
      "error",
      function onErr() {
        img.removeEventListener("error", onErr);
        img.classList.remove("is-loading");
        img.classList.add("is-error");
        img.removeAttribute("src");
      },
      { once: true }
    );
    img.src = src;
    return img;
  }

  function makeShareButton(story, id) {
    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "share-btn share-btn--story";
    btn.setAttribute("aria-label", "Share this story");
    btn.textContent = "Share";
    btn.addEventListener("click", function (e) {
      e.preventDefault();
      e.stopPropagation();
      sharePayload({
        title: story.title || SITE_TITLE,
        text: (story.summary || "").slice(0, 180),
        url: pageUrl(id)
      });
    });
    return btn;
  }

  function renderHeroCard(story, tier, priorityIndex, id) {
    var card = document.createElement("div");
    card.className = "story__card";
    var images = storyImages(story);
    var src = images[0];
    var eager = typeof priorityIndex === "number" && priorityIndex < 4;

    if (src) {
      var photo = makePhoto(src, story.title || "", { eager: eager });
      card.appendChild(photo);
      card.classList.add("story__card--zoom");
      var zoomHit = document.createElement("button");
      zoomHit.type = "button";
      zoomHit.className = "story__zoom-hit";
      zoomHit.setAttribute("aria-label", "View photo larger");
      bindLightbox(zoomHit, src, story.title || "");
      card.appendChild(zoomHit);
    } else {
      card.classList.add("story__card--placeholder");
    }

    var wash = document.createElement("div");
    wash.className = "story__wash";
    wash.setAttribute("aria-hidden", "true");
    card.appendChild(wash);

    var overlay = document.createElement("div");
    overlay.className = "story__overlay";

    var metaRow = document.createElement("div");
    metaRow.className = "story__meta-row";
    var meta = document.createElement("p");
    meta.className = "story__meta";
    meta.textContent = story.source || "Good news";
    metaRow.appendChild(meta);
    var share = makeShareButton(story, id);
    share.classList.add("share-btn--on-card");
    metaRow.appendChild(share);
    overlay.appendChild(metaRow);

    var title = document.createElement("h2");
    title.className = "story__title";
    title.textContent = story.title || "Untitled";
    overlay.appendChild(title);

    card.appendChild(overlay);
    return card;
  }

  function closeOpen() {

    if (!openArticle) return;
    openArticle.classList.remove("is-expanded");
    var btn = openArticle.querySelector(".story__more");
    if (btn) {
      btn.setAttribute("aria-expanded", "false");
      var label = btn.querySelector(".story__more-label");
      if (label) label.textContent = "Read more";
    }
    openArticle = null;
  }

  function toggleExpand(article, button) {
    var willOpen = !article.classList.contains("is-expanded");
    if (willOpen) {
      if (openArticle && openArticle !== article) closeOpen();
      article.classList.add("is-expanded");
      button.setAttribute("aria-expanded", "true");
      var label = button.querySelector(".story__more-label");
      if (label) label.textContent = "Show less";
      openArticle = article;
      if (article.id && history.replaceState) {
        history.replaceState(null, "", "#" + article.id);
      }
    } else {
      closeOpen();
      if (history.replaceState) {
        history.replaceState(null, "", pageUrl());
      }
    }
  }

  function renderStory(story, index) {
    var impact = Math.max(1, Math.min(5, Number(story.impact) || 3));
    var tier = story.tier || tierFromImpact(impact);
    var id = storyId(story, index);
    var article = document.createElement("article");
    article.className = "story story--" + tier;
    article.id = id;
    article.dataset.impact = String(impact);

    article.appendChild(renderHeroCard(story, tier, index, id));

    var body = document.createElement("div");
    body.className = "story__body";

    if (story.summary) {
      var summary = document.createElement("p");
      summary.className = "story__summary";
      summary.textContent = story.summary;
      body.appendChild(summary);
    }

    var panelId = "story-panel-" + index;

    var moreBtn = document.createElement("button");
    moreBtn.type = "button";
    moreBtn.className = "story__more";
    moreBtn.setAttribute("aria-expanded", "false");
    moreBtn.setAttribute("aria-controls", panelId);
    var moreLabel = document.createElement("span");
    moreLabel.className = "story__more-label";
    moreLabel.textContent = "Read more";
    var chevron = document.createElement("span");
    chevron.className = "story__more-chevron";
    chevron.setAttribute("aria-hidden", "true");
    moreBtn.appendChild(moreLabel);
    moreBtn.appendChild(chevron);

    var panel = document.createElement("div");
    panel.className = "story__panel";
    panel.id = panelId;
    panel.setAttribute("role", "region");
    panel.setAttribute("aria-label", "Fuller summary");

    var panelInner = document.createElement("div");
    panelInner.className = "story__panel-inner";

    var longEl = document.createElement("div");
    longEl.className = "story__long";
    var longText = story.summaryLong || story.summary || "";
    longText.split(/\n\n+/).forEach(function (para) {
      var p = document.createElement("p");
      p.textContent = para.trim();
      if (p.textContent) longEl.appendChild(p);
    });
    panelInner.appendChild(longEl);

    if (story.summaryLongNote) {
      var note = document.createElement("p");
      note.className = "story__note";
      note.textContent = story.summaryLongNote;
      panelInner.appendChild(note);
    }

    if (story.url) {
      var orig = document.createElement("a");
      orig.className = "story__original";
      orig.href = story.url;
      orig.target = "_blank";
      orig.rel = "noopener noreferrer";
      orig.textContent = "Source article";
      panelInner.appendChild(orig);
    }

    panel.appendChild(panelInner);

    moreBtn.addEventListener("click", function (e) {
      e.preventDefault();
      toggleExpand(article, moreBtn);
    });

    body.appendChild(moreBtn);
    body.appendChild(panel);
    article.appendChild(body);
    return article;
  }

  function observeReveal(nodes) {
    if (reduceMotion || !("IntersectionObserver" in window)) {
      nodes.forEach(function (n) {
        n.classList.add("is-visible");
      });
      return;
    }
    nodes.forEach(function (n) {
      n.classList.add("will-reveal");
    });
    var io = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            entry.target.classList.remove("will-reveal");
            io.unobserve(entry.target);
          }
        });
      },
      { rootMargin: "0px 0px -6% 0px", threshold: 0.08 }
    );
    nodes.forEach(function (n) {
      io.observe(n);
    });
    setTimeout(function () {
      nodes.forEach(function (n) {
        if (!n.classList.contains("is-visible")) {
          n.classList.add("is-visible");
          n.classList.remove("will-reveal");
        }
      });
    }, 1800);
  }

  function focusHash() {
    var hash = (location.hash || "").replace(/^#/, "");
    if (!hash) return;
    var el = document.getElementById(hash);
    if (!el) return;
    el.classList.add("is-visible");
    el.classList.remove("will-reveal");
    try {
      el.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "start" });
    } catch (e) {
      el.scrollIntoView(true);
    }
    // Soft highlight
    el.classList.add("is-deep-linked");
    setTimeout(function () {
      el.classList.remove("is-deep-linked");
    }, 1600);
  }

  function onScrollHeader() {
    if (!headerEl) return;
    headerEl.classList.toggle("is-scrolled", window.scrollY > 8);
  }

  function showError(message) {
    storiesEl.setAttribute("aria-busy", "false");
    if (statusEl && statusEl.isConnected) {
      statusEl.classList.add("status--error");
      statusEl.textContent = message;
    } else {
      storiesEl.innerHTML = "";
      var p = document.createElement("p");
      p.className = "status status--error";
      p.id = "status";
      p.textContent = message;
      storiesEl.appendChild(p);
      statusEl = p;
    }
  }

  function fingerprintStories(stories) {
    try {
      return JSON.stringify(
        (stories || []).map(function (s, i) {
          return stableStoryKey(s, i);
        })
      );
    } catch (e) {
      return String(Date.now());
    }
  }

  function sortStories(stories) {
    return stories
      .map(function (s, i) {
        return { s: s, i: i };
      })
      .sort(function (a, b) {
        var ia = Number(a.s.impact) || 0;
        var ib = Number(b.s.impact) || 0;
        if (ib !== ia) return ib - ia;
        return a.i - b.i;
      })
      .map(function (x) {
        return x.s;
      });
  }

  function choosePoolSet(pool, weekOf) {
    var seen = readSeenIds(weekOf);
    var unseenCount = pool.filter(function (story, index) {
      return seen.indexOf(stableStoryKey(story, index)) === -1;
    }).length;

    if (unseenCount < SET_SIZE) {
      writeSeenIds([], weekOf);
      return {
        stories: pickDisjointSet(pool, [], SET_SIZE),
        recycled: true
      };
    }

    return {
      stories: pickDisjointSet(pool, seen, SET_SIZE),
      recycled: false
    };
  }

  function renderWeek(data, storiesOverride) {
    var stories = Array.isArray(storiesOverride)
      ? storiesOverride.slice(0, SET_SIZE)
      : Array.isArray(data.stories)
        ? data.stories.slice(0, SET_SIZE)
        : [];
    if (!stories.length) {
      showError("No stories yet for this week.");
      return false;
    }

    stories = sortStories(stories);
    closeOpen();
    closeLightbox();

    if (data && data.weekOf) {
      weekMeta.weekOf = data.weekOf;
      weekMeta.label = formatWeekOf(data.weekOf);
      weekLabelEl.textContent = "Week of " + weekMeta.label;
    }

    storiesEl.setAttribute("aria-busy", "false");
    storiesEl.innerHTML = "";
    statusEl = null;
    var nodes = stories.map(function (story, i) {
      return renderStory(story, i);
    });
    nodes.forEach(function (n) {
      storiesEl.appendChild(n);
    });
    observeReveal(nodes);
    displayedStories = stories.slice();
    currentFingerprint = fingerprintStories(stories);

    var seen = readSeenIds(weekMeta.weekOf);
    stories.forEach(function (s, i) {
      var key = stableStoryKey(s, i);
      if (seen.indexOf(key) === -1) seen.push(key);
    });
    writeSeenIds(seen, weekMeta.weekOf);
    return true;
  }

  function scrollToTop() {
    try {
      window.scrollTo({
        top: 0,
        behavior: reduceMotion ? "auto" : "smooth"
      });
    } catch (e) {
      window.scrollTo(0, 0);
    }
  }

  function setRefreshBusy(busy) {
    loadingWeek = busy;
    if (!refreshBtn) return;
    refreshBtn.disabled = !!busy;
    refreshBtn.setAttribute("aria-busy", busy ? "true" : "false");
  }

  function ingestWeekData(data) {
    var featured = Array.isArray(data.stories) ? data.stories : [];
    var pool = Array.isArray(data.pool) && data.pool.length ? data.pool : featured;
    storyPool = pool.slice();
    return { data: data, featured: featured, pool: pool };
  }

  function refreshFromPool() {
    if (loadingWeek) return;
    if (!storyPool.length) {
      showToast("Couldn’t refresh. Try again.");
      return;
    }

    setRefreshBusy(true);
    storiesEl.setAttribute("aria-busy", "true");

    var choice = choosePoolSet(storyPool, weekMeta.weekOf);
    var next = choice.stories;

    var settle = reduceMotion ? 0 : 80;
    var preloadWait = preloadStoryImages(sortStories(next), 4);

    Promise.resolve(preloadWait)
      .catch(function () {
        /* ignore preload failures */
      })
      .then(function () {
        return new Promise(function (resolve) {
          window.setTimeout(resolve, settle);
        });
      })
      .then(function () {
        var ok = renderWeek(
          { weekOf: weekMeta.weekOf, stories: next },
          next
        );
        storiesEl.setAttribute("aria-busy", "false");
        setRefreshBusy(false);

        if (!ok) {
          showToast("Couldn’t refresh. Try again.");
          return;
        }

        scrollToTop();
        if (history.replaceState) {
          history.replaceState(null, "", pageUrl());
        }
        showToast(
          choice.recycled
            ? "You’ve seen the rest — starting a new round"
            : "Fifteen new stories"
        );
      });
  }

  function loadWeek() {
    storiesEl.setAttribute("aria-busy", "true");

    return fetch("data/week.json", { cache: "no-cache" })
      .then(function (res) {
        if (!res.ok) throw new Error("load failed");
        return res.json();
      })
      .then(function (data) {
        var packed = ingestWeekData(data);
        // Fresh 15 from the pool on every page open, skipping this week's seen ids.
        var choice = choosePoolSet(packed.pool, packed.data.weekOf);
        var initial = choice.stories;
        if (!initial.length) initial = packed.featured.slice(0, SET_SIZE);
        var ok = renderWeek(packed.data, initial);
        if (!ok) return;
        if (choice.recycled) showToast("You’ve seen the rest — starting a new round");
        requestAnimationFrame(focusHash);
      })
      .catch(function () {
        showError("Couldn’t load stories. Try a local server (see README).");
      });
  }

  if (shareWeekBtn) {
    shareWeekBtn.addEventListener("click", function (e) {
      e.preventDefault();
      sharePayload({
        title: SITE_TITLE,
        text: "Fifteen good things worth a look.",
        url: pageUrl()
      });
    });
  }

  if (refreshBtn) {
    refreshBtn.addEventListener("click", function (e) {
      e.preventDefault();
      if (loadingWeek) return;
      refreshFromPool();
    });
  }

  if (lightboxEl) {
    lightboxEl.addEventListener("click", function (e) {
      if (e.target === lightboxEl) closeLightbox();
    });
  }
  if (lightboxClose) {
    lightboxClose.addEventListener("click", function (e) {
      e.preventDefault();
      e.stopPropagation();
      closeLightbox();
    });
  }
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && lightboxOpen) {
      e.preventDefault();
      closeLightbox();
    }
  });

  window.addEventListener("scroll", onScrollHeader, { passive: true });
  window.addEventListener("hashchange", focusHash);
  onScrollHeader();

  loadWeek();
})();
