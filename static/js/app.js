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
  });

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
