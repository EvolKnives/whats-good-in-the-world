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

  function readSeenIds() {
    try {
      var raw = sessionStorage.getItem(SEEN_KEY);
      var parsed = raw ? JSON.parse(raw) : [];
      return Array.isArray(parsed) ? parsed.map(String) : [];
    } catch (e) {
      return [];
    }
  }

  function writeSeenIds(ids) {
    try {
      var capped = ids.slice(-Math.max(SET_SIZE * 4, 60));
      sessionStorage.setItem(SEEN_KEY, JSON.stringify(capped));
    } catch (e) {
      /* ignore quota / private mode */
    }
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
    var picked = fresh.slice(0, count);
    if (picked.length < count) {
      picked = picked.concat(reused.slice(0, count - picked.length));
    }
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

  function imageFigure(src, alt) {
    var figure = document.createElement("figure");
    figure.className = "story__figure story__figure--zoom";
    figure.setAttribute("role", "button");
    figure.tabIndex = 0;
    figure.setAttribute("aria-label", "View photo larger");
    var img = document.createElement("img");
    img.src = src;
    img.alt = alt || "";
    img.width = 1200;
    img.height = 750;
    img.loading = "lazy";
    img.decoding = "async";
    img.referrerPolicy = "no-referrer";
    img.addEventListener("error", function onErr() {
      img.removeEventListener("error", onErr);
      figure.classList.remove("story__figure--zoom");
      figure.removeAttribute("role");
      figure.removeAttribute("tabIndex");
      figure.removeAttribute("aria-label");
      figure.classList.add("story__figure--placeholder");
      figure.textContent = "";
      img.remove();
    });
    function openThis(e) {
      if (e) e.preventDefault();
      openLightbox(src, alt || "");
    }
    figure.addEventListener("click", openThis);
    figure.addEventListener("keydown", function (e) {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        openThis(e);
      }
    });
    figure.appendChild(img);
    return figure;
  }

  function youtubeEmbed(id, title, large) {
    var wrap = document.createElement("div");
    wrap.className = "story__video" + (large ? " story__video--large" : "");
    var iframe = document.createElement("iframe");
    iframe.src =
      "https://www.youtube-nocookie.com/embed/" +
      encodeURIComponent(id) +
      "?rel=0&modestbranding=1";
    iframe.title = (title || "Story") + " — video";
    iframe.loading = "lazy";
    iframe.setAttribute(
      "allow",
      "accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
    );
    iframe.allowFullscreen = true;
    iframe.referrerPolicy = "strict-origin-when-cross-origin";
    wrap.appendChild(iframe);
    return wrap;
  }

  function renderMedia(story, tier) {
    var media = document.createElement("div");
    media.className = "story__media";
    var yt = youtubeId(story.youtube);
    var images = Array.isArray(story.images) ? story.images.filter(Boolean) : [];

    if (yt) {
      media.appendChild(
        youtubeEmbed(yt, story.title, tier === "hero" || tier === "featured")
      );
      if (images[0] && tier === "hero") {
        media.appendChild(imageFigure(images[0], story.title));
      }
      return media;
    }

    if (images.length) {
      var max = tier === "hero" ? 2 : 1;
      var slice = images.slice(0, max);
      if (slice.length > 1) media.classList.add("story__media--pair");
      slice.forEach(function (src) {
        media.appendChild(imageFigure(src, story.title));
      });
      return media;
    }

    var ph = document.createElement("figure");
    ph.className = "story__figure story__figure--placeholder";
    media.appendChild(ph);
    return media;
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

  function renderStory(story, index) {
    var impact = Math.max(1, Math.min(5, Number(story.impact) || 3));
    var tier = story.tier || tierFromImpact(impact);
    var id = storyId(story, index);
    var article = document.createElement("article");
    article.className = "story story--" + tier;
    article.id = id;
    article.dataset.impact = String(impact);

    article.appendChild(renderMedia(story, tier));

    var body = document.createElement("div");
    body.className = "story__body";

    var metaRow = document.createElement("div");
    metaRow.className = "story__meta-row";
    var meta = document.createElement("p");
    meta.className = "story__meta";
    meta.textContent = story.source || "Source";
    metaRow.appendChild(meta);
    metaRow.appendChild(makeShareButton(story, id));
    body.appendChild(metaRow);

    var title = document.createElement("h2");
    title.className = "story__title";
    title.textContent = story.title || "Untitled";
    body.appendChild(title);

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

    var seen = readSeenIds();
    stories.forEach(function (s, i) {
      var key = stableStoryKey(s, i);
      if (seen.indexOf(key) === -1) seen.push(key);
    });
    writeSeenIds(seen);
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

    // Brief busy state so the tap feels responsive without waiting on network
    window.setTimeout(function () {
      var avoid = displayedStories.map(function (s, i) {
        return stableStoryKey(s, i);
      });
      var seen = readSeenIds();
      // Prefer avoiding currently shown; also nudge away from recently seen when pool allows
      var avoidSet = avoid.slice();
      if (storyPool.length >= SET_SIZE * 2) {
        seen.forEach(function (id) {
          if (avoidSet.indexOf(id) === -1) avoidSet.push(id);
        });
      }

      var next = pickDisjointSet(storyPool, avoidSet, SET_SIZE);
      // If session avoid exhausted the pool, fall back to current-only avoid
      if (next.length < SET_SIZE) {
        next = pickDisjointSet(storyPool, avoid, SET_SIZE);
      }

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
      showToast("Fifteen new stories");
    }, reduceMotion ? 0 : 120);
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
        var ok = renderWeek(packed.data, packed.featured);
        if (!ok) return;
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
        text:
          "Fifteen quiet highlights from the week of " +
          (weekMeta.label || "this week") +
          ".",
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
