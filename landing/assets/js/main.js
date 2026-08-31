/* =========================================================
   Wlogio marketing site — main.js
   =========================================================
   KONFIGURACJA: adres aplikacji Wlogio (panel logowania,
   logowanie do terminala, właściwa rejestracja konta).
   Ustaw jeden raz poniżej — używane w całym serwisie.
   ========================================================= */
window.WLOGIO_APP_URL = window.WLOGIO_APP_URL || "https://wlogio.onrender.com";

(function () {
  "use strict";

  var APP_URL = window.WLOGIO_APP_URL.replace(/\/$/, "");

  /* ---- Wire up every element with data-app-link="/path" ---- */
  document.querySelectorAll("[data-app-link]").forEach(function (el) {
    var path = el.getAttribute("data-app-link") || "";
    el.setAttribute("href", APP_URL + path);
  });

  /* ---- Mobile nav toggle ---- */
  var navToggle = document.querySelector(".nav-toggle");
  var mainNav = document.querySelector(".main-nav");
  if (navToggle && mainNav) {
    navToggle.addEventListener("click", function () {
      mainNav.classList.toggle("open");
      var expanded = mainNav.classList.contains("open");
      navToggle.setAttribute("aria-expanded", expanded ? "true" : "false");
    });
    mainNav.querySelectorAll("a").forEach(function (a) {
      a.addEventListener("click", function () {
        mainNav.classList.remove("open");
      });
    });
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

  /* ---- Registration page: type tabs (individual / company) ---- */
  var regTabs = document.querySelectorAll(".reg-tab");
  var regPanels = document.querySelectorAll(".reg-panel");
  regTabs.forEach(function (tab) {
    tab.addEventListener("click", function () {
      regTabs.forEach(function (t) { t.classList.remove("active"); });
      regPanels.forEach(function (p) { p.classList.remove("active"); });
      tab.classList.add("active");
      var target = document.getElementById(tab.dataset.target);
      if (target) target.classList.add("active");
    });
  });

  /* ---- Registration page: plan card selection ---- */
  var pickCards = document.querySelectorAll(".pick-card");
  var continueBtn = document.getElementById("regContinueBtn");
  var summaryEl = document.getElementById("regSelectedSummary");

  function updateContinueLink(card) {
    if (!card || !continueBtn) return;
    var plan = card.getAttribute("data-plan");
    var billing = document.querySelector(".billing-toggle button.active");
    var billingMode = billing ? billing.dataset.billing : "monthly";
    var path = "/register?plan=" + encodeURIComponent(plan) + "&billing=" + encodeURIComponent(billingMode);
    continueBtn.setAttribute("data-app-link", path);
    continueBtn.setAttribute("href", APP_URL + path);
    if (summaryEl) {
      summaryEl.innerHTML = "Wybrany plan: <b>" + card.getAttribute("data-plan-label") + "</b>";
    }
  }

  pickCards.forEach(function (card) {
    card.addEventListener("click", function () {
      var group = card.closest(".plan-picker");
      group.querySelectorAll(".pick-card").forEach(function (c) { c.classList.remove("selected"); });
      card.classList.add("selected");
      updateContinueLink(card);
    });
  });

  /* Preselect first visible plan card on each panel when it becomes active */
  regTabs.forEach(function (tab) {
    tab.addEventListener("click", function () {
      var target = document.getElementById(tab.dataset.target);
      if (!target) return;
      var firstCard = target.querySelector(".pick-card");
      if (firstCard) {
        target.querySelectorAll(".pick-card").forEach(function (c) { c.classList.remove("selected"); });
        firstCard.classList.add("selected");
        updateContinueLink(firstCard);
      }
    });
  });

  var initialCard = document.querySelector(".reg-panel.active .pick-card");
  if (initialCard) {
    initialCard.classList.add("selected");
    updateContinueLink(initialCard);
  }
})();
