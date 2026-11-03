/* ArtificialMoralAgent 3.x additions: server config, notices, disclaimer under every result, key help. */
(function () {
  function base() { let b = window.location.pathname; if (!b.endsWith("/")) b = b.substring(0, b.lastIndexOf("/") + 1); return b; }
  window.AMA_CONFIG = { public_demo: false };
  fetch(base() + "api/v1/config", { credentials: "same-origin" }).then(r => r.json()).then(cfg => {
    window.AMA_CONFIG = cfg;
    const hint = document.getElementById("guest-mode-hint");
    if (hint && cfg.public_demo && !cfg.signed_in) hint.textContent = "Public demo: up to " + cfg.demo_per_ip_per_day +
      " free evaluations a day. Results stay private unless the site owner publishes them.";
    if (!cfg.model_key_configured) {
      notice('No model API key is configured on this server yet. <a class="ama-link" href="' + base() +
             'help/gemini-key">Get a free Gemini key</a> and add it with <code>ama init</code>.', 0);
    } else if (cfg.public_demo && !cfg.signed_in) {
      notice("Public demo: you can run up to " + cfg.demo_per_ip_per_day + " free evaluations a day. Evaluations are private unless the site owner publishes them.", 9000);
    }
  }).catch(() => {});

  function notice(html, ms) {
    let el = document.getElementById("ama-notice");
    if (!el) {
      el = document.createElement("div"); el.id = "ama-notice"; el.className = "ama-notice"; el.setAttribute("role", "status");
      document.body.appendChild(el);
    }
    el.innerHTML = '<span>' + html + '</span><button aria-label="Close" onclick="this.parentElement.style.display=\'none\'">&times;</button>';
    el.style.display = "flex";
    if (ms) setTimeout(() => { el.style.display = "none"; }, ms);
  }
  window.amaShowNotice = function (msg) { const d = document.createElement("div"); d.textContent = msg; notice(d.innerHTML, 12000); };

  window.amaShowDisclaimer = function (data) {
    const results = document.getElementById("results-section") || document.querySelector(".results-section");
    if (!results) return;
    let el = document.getElementById("ama-result-disclaimer");
    if (!el) { el = document.createElement("p"); el.id = "ama-result-disclaimer"; el.className = "ama-disclaimer"; results.appendChild(el); }
    el.textContent = (data && data.general_disclaimer) || (window.AMA_CONFIG && window.AMA_CONFIG.disclaimer) || "";
  };
})();
