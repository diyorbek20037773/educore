/* EDUCORE front-end bootstrap. Alpine CSP build: components are registered with Alpine.data(),
   templates use only property/method references (no inline expressions that need eval). */
(function () {
  "use strict";

  var THEME_KEY = "educore-theme";

  function currentTheme() {
    return document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
  }

  document.addEventListener("alpine:init", function () {
    window.Alpine.data("themeToggle", function () {
      return {
        theme: currentTheme(),
        get label() {
          return this.theme === "dark" ? "Yorugʻ rejim" : "Qorongʻi rejim";
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
  });
})();
