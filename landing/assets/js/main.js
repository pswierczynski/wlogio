/* =========================================================
   Wlogio marketing site — main.js
   =========================================================
   KONFIGURACJA: adres aplikacji Wlogio (panel logowania,
   logowanie do terminala, właściwa rejestracja konta).
   Ustaw jeden raz poniżej — używane w całym serwisie.
   ========================================================= */
/* Strona i aplikacja działają pod jedną domeną (wlogio.pl) — adres pusty = ten sam serwer.
   Gdyby aplikacja kiedyś trafiła na osobną domenę, ustaw np. "https://app.wlogio.pl". */
window.WLOGIO_APP_URL = (typeof window.WLOGIO_APP_URL === "string") ? window.WLOGIO_APP_URL : "";

(function () {
  "use strict";

  var APP_URL = window.WLOGIO_APP_URL.replace(/\/$/, "");

  /* ---- Wire up every element with data-app-link="/path" ---- */
  document.querySelectorAll("[data-app-link]").forEach(function (el) {
    var path = el.getAttribute("data-app-link") || "";
    el.setAttribute("href", APP_URL + path);
  });


  /* ---- Animacje pojawiania się elementów przy przewijaniu ---- */
  (function () {
    var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce || !("IntersectionObserver" in window)) {
      document.documentElement.classList.remove("js");
      return;
    }
    var groups = [
      ".head", ".step", ".feature-item", ".chip", ".acc-card", ".plan-card",
      ".billing-toggle", ".terminal-copy > *", ".terminal-art", ".faq-item",
      ".cta-band", ".stat", ".reg-card", ".reg-actions", ".reg-hero .wrap > *"
    ];
    var seen = new Set();
    groups.forEach(function (sel) {
      document.querySelectorAll(sel).forEach(function (el) {
        if (seen.has(el) || el.closest(".hero")) return;
        seen.add(el);
        el.classList.add("reveal");
        if (el.classList.contains("terminal-art")) el.classList.add("reveal-zoom");
        // opóźnienie kaskadowe wśród rodzeństwa (maks. ~0,5 s)
        var idx = Array.prototype.indexOf.call(el.parentNode.children, el);
        el.style.transitionDelay = Math.min(idx, 6) * 0.08 + "s";
      });
    });
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (!en.isIntersecting) return;
        var el = en.target;
        el.classList.add("in");
        io.unobserve(el);
        // po zakończeniu animacji zdejmujemy klasy, żeby nie kolidowały z :hover itp.
        setTimeout(function () {
          el.classList.remove("reveal", "reveal-zoom", "reveal-left", "in");
          el.style.transitionDelay = "";
        }, 1400);
      });
    }, { threshold: 0.12, rootMargin: "0px 0px -6% 0px" });
    seen.forEach(function (el) { io.observe(el); });
  })();

  /* ---- Mobile nav toggle ---- */
  var navToggle = document.querySelector(".nav-toggle");
  var mainNav = document.querySelector(".main-nav");
  if (navToggle && mainNav) {
    navToggle.addEventListener("click", function () {
      mainNav.classList.toggle("open");
      var expanded = mainNav.classList.contains("open");
      navToggle.setAttribute("aria-expanded", expanded ? "true" : "false");
      var hd = document.getElementById("siteHeader");
      if (hd) hd.classList.toggle("menu-open", expanded);
    });
    mainNav.querySelectorAll("a").forEach(function (a) {
      a.addEventListener("click", function () {
        mainNav.classList.remove("open");
        var hd = document.getElementById("siteHeader");
        if (hd) hd.classList.remove("menu-open");
      });
    });
  }

  /* ---- Header: biały po przewinięciu ---- */
  var siteHeader = document.getElementById("siteHeader");
  if (siteHeader) {
    var onScroll = function () { siteHeader.classList.toggle("is-scrolled", window.scrollY > 40); };
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
  }

  /* ---- Pricing billing toggle (monthly / yearly, 2 months free) ---- */
  var toggleButtons = document.querySelectorAll(".billing-toggle button");
  var priceEls = document.querySelectorAll("[data-monthly]");

  function formatPLN(value) {
    return new Intl.NumberFormat("pl-PL", { maximumFractionDigits: 0 }).format(value);
  }

  function setBilling(mode) {
    toggleButtons.forEach(function (btn) {
      btn.classList.toggle("active", btn.dataset.billing === mode);
    });
    priceEls.forEach(function (el) {
      var monthly = parseFloat(el.getAttribute("data-monthly"));
      if (isNaN(monthly)) return;
      if (mode === "yearly") {
        var yearlyMonthlyEquivalent = Math.round(monthly * 10 / 12); // 2 miesiące gratis / rok
        el.textContent = formatPLN(yearlyMonthlyEquivalent);
      } else {
        el.textContent = formatPLN(monthly);
      }
    });
    var unitEls = document.querySelectorAll("[data-unit]");
    unitEls.forEach(function (el) {
      el.textContent = mode === "yearly" ? "zł / mies. *" : "zł / mies.";
    });
    var notes = document.querySelectorAll(".billing-note");
    notes.forEach(function (el) {
      el.style.display = mode === "yearly" ? "block" : "none";
    });
    document.querySelectorAll("[data-plan-key]").forEach(function (el) {
      el.setAttribute("data-billing", mode);
    });
  }

  toggleButtons.forEach(function (btn) {
    btn.addEventListener("click", function () {
      setBilling(btn.dataset.billing);
    });
  });

})();
