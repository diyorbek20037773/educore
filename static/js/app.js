/* EDUCORE front-end bootstrap (ADR-012).
   Alpine CSP build: every component is registered with Alpine.data(); templates only reference properties,
   getters and methods — no inline expressions that would need eval. */
(function () {
  "use strict";

  var THEME_KEY = "educore-theme";

  function currentTheme() {
    return document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
  }

  document.addEventListener("alpine:init", function () {
    var Alpine = window.Alpine;

    Alpine.data("siteHeader", function () {
      return {
        drawerOpen: false,
        get drawerExpanded() {
          return this.drawerOpen ? "true" : "false";
        },
        toggleDrawer: function () {
          this.drawerOpen = !this.drawerOpen;
          document.documentElement.classList.toggle("overflow-hidden", this.drawerOpen);
        },
        closeDrawer: function () {
          this.drawerOpen = false;
          document.documentElement.classList.remove("overflow-hidden");
        },
      };
    });

    Alpine.data("dropdown", function () {
      return {
        open: false,
        get expanded() {
          return this.open ? "true" : "false";
        },
        toggle: function () {
          this.open = !this.open;
        },
        close: function () {
          this.open = false;
        },
      };
    });

    Alpine.data("themeToggle", function () {
      return {
        theme: currentTheme(),
        get isDark() {
          return this.theme === "dark";
        },
        get isLight() {
          return this.theme !== "dark";
        },
        get pressed() {
          return this.theme === "dark" ? "true" : "false";
        },
        toggle: function () {
          this.theme = this.theme === "dark" ? "light" : "dark";
          document.documentElement.setAttribute("data-theme", this.theme);
          try {
            localStorage.setItem(THEME_KEY, this.theme);
          } catch (e) {}
          document.dispatchEvent(new CustomEvent("educore:theme", { detail: { theme: this.theme } }));
        },
      };
    });

    Alpine.data("shareLink", function () {
      return {
        copied: false,
        get notCopied() {
          return !this.copied;
        },
        copy: function () {
          var self = this;
          var url = this.$el.getAttribute("data-url") || window.location.href;
          if (navigator.clipboard) {
            navigator.clipboard.writeText(url).then(function () {
              self.copied = true;
              setTimeout(function () {
                self.copied = false;
              }, 2000);
            });
          }
        },
      };
    });

    Alpine.data("lightbox", function () {
      return {
        open: false,
        src: "",
        alt: "",
        show: function (event) {
          var trigger = event.currentTarget;
          this.src = trigger.getAttribute("data-src") || trigger.getAttribute("href");
          this.alt = trigger.getAttribute("data-alt") || "";
          this.open = true;
        },
        hide: function () {
          this.open = false;
        },
      };
    });

    Alpine.data("countdown", function () {
      return {
        label: "",
        init: function () {
          var end = new Date(this.$el.getAttribute("data-end"));
          var render = this.$el.getAttribute("data-template") || "{d}";
          var self = this;
          function tick() {
            var days = Math.max(0, Math.ceil((end - new Date()) / 86400000));
            self.label = render.replace("{d}", String(days));
          }
          tick();
          setInterval(tick, 60000);
        },
      };
    });

    /* Home "Motivatsiya" row: round prev/next buttons scroll the track by one visible page. */
    Alpine.data("carousel", function () {
      return {
        scrollBy: function (direction) {
          var track = this.$refs.track;
          if (track) {
            track.scrollBy({ left: direction * track.clientWidth, behavior: "smooth" });
          }
        },
        prev: function () {
          this.scrollBy(-1);
        },
        next: function () {
          this.scrollBy(1);
        },
      };
    });

    /* Institutions banner and side rails (ADR-031): cross-fades [data-slide] children every data-interval ms.
       Pauses on hover/focus and while the tab is hidden; no autoplay under prefers-reduced-motion. */
    Alpine.data("rotator", function () {
      return {
        index: 0,
        timer: null,
        paused: false,
        init: function () {
          this.slides = Array.prototype.slice.call(this.$el.querySelectorAll("[data-slide]"));
          this.dots = Array.prototype.slice.call(this.$el.querySelectorAll("[data-dot]"));
          this.interval = parseInt(this.$el.getAttribute("data-interval"), 10) || 8000;
          this.show(0);
          var self = this;
          this.onVisibility = function () {
            if (document.hidden) {
              self.stop();
            } else {
              self.start();
            }
          };
          document.addEventListener("visibilitychange", this.onVisibility);
          this.start();
        },
        destroy: function () {
          this.stop();
          document.removeEventListener("visibilitychange", this.onVisibility);
        },
        start: function () {
          this.stop();
          if (this.slides.length < 2 || this.paused || reducedMotion()) {
            return;
          }
          var self = this;
          this.timer = setInterval(function () {
            self.show(self.index + 1);
          }, this.interval);
        },
        stop: function () {
          if (this.timer) {
            clearInterval(this.timer);
            this.timer = null;
          }
        },
        show: function (i) {
          var n = this.slides.length;
          if (!n) {
            return;
          }
          this.index = ((i % n) + n) % n;
          var active = this.index;
          this.slides.forEach(function (slide, k) {
            slide.classList.toggle("is-active", k === active);
            slide.inert = k !== active;
            slide.setAttribute("aria-hidden", k === active ? "false" : "true");
          });
          this.dots.forEach(function (dot, k) {
            dot.classList.toggle("is-active", k === active);
            dot.setAttribute("aria-current", k === active ? "true" : "false");
          });
        },
        next: function () {
          this.show(this.index + 1);
          this.start();
        },
        prev: function () {
          this.show(this.index - 1);
          this.start();
        },
        go: function (event) {
          this.show(parseInt(event.currentTarget.getAttribute("data-dot"), 10) || 0);
          this.start();
        },
        pause: function () {
          this.paused = true;
          this.stop();
        },
        resume: function () {
          this.paused = false;
          this.start();
        },
      };
    });

    /* Institution strip (< 1280 px): the track holds two copies; one copy scrolls by at 30 px/s. */
    Alpine.data("marquee", function () {
      return {
        init: function () {
          var track = this.$refs.track;
          if (!track) {
            return;
          }
          function measure() {
            var half = track.scrollWidth / 2;
            track.style.animationDuration = Math.max(10, Math.round(half / 30)) + "s";
          }
          measure();
          track.classList.toggle("is-running", !reducedMotion());
          if (window.ResizeObserver) {
            this.observer = new ResizeObserver(measure); // the strip is display:none on wide screens
            this.observer.observe(track);
          }
        },
        destroy: function () {
          if (this.observer) {
            this.observer.disconnect();
          }
        },
        pause: function () {
          this.$refs.track.classList.add("is-paused");
        },
        resume: function () {
          this.$refs.track.classList.remove("is-paused");
        },
      };
    });

    /* Section sub-nav: the chevron scrolls the link list by most of its visible width. */
    Alpine.data("subnav", function () {
      return {
        scrollNext: function () {
          var list = this.$refs.list;
          var atEnd = list.scrollLeft + list.clientWidth >= list.scrollWidth - 4;
          list.scrollTo({ left: atEnd ? 0 : list.scrollLeft + list.clientWidth * 0.8, behavior: "smooth" });
        },
      };
    });
  });

  function reducedMotion() {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }

  /* Boosted navigation replaces the body: never leave the page scroll-locked by an open drawer. */
  document.addEventListener("htmx:beforeSwap", function (event) {
    if (event.detail && event.detail.boosted) {
      document.documentElement.classList.remove("overflow-hidden");
    }
  });

  /* Live panel: highlight newly swapped items (aria-live handles announcements). */
  document.addEventListener("htmx:afterSwap", function (event) {
    var target = event.detail && event.detail.target;
    if (target && target.id === "live-panel-items") {
      target.querySelectorAll("[data-new='1']").forEach(function (el) {
        el.classList.add("is-new");
      });
    }
  });
})();
