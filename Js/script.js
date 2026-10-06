
   (() => {
    "use strict";
  
    
    const topbar = document.getElementById("topbar");
    const toggle = document.getElementById("menuToggle");
    const nav = document.getElementById("mainNav");
  
    toggle.addEventListener("click", () => {
      const open = toggle.getAttribute("aria-expanded") === "true";
      toggle.setAttribute("aria-expanded", String(!open));
      nav.classList.toggle("open", !open);
    });
    nav.querySelectorAll("a").forEach(a =>
      a.addEventListener("click", () => {
        toggle.setAttribute("aria-expanded", "false");
        nav.classList.remove("open");
      })
    );
  
    window.addEventListener("scroll", () => {
      topbar.classList.toggle("scrolled", window.scrollY > 10);
    }, { passive: true });
  
    const navLinks = [...nav.querySelectorAll("a")];
    const sections = navLinks.map(a => document.querySelector(a.getAttribute("href")));
    if ("IntersectionObserver" in window) {
      const io = new IntersectionObserver(entries => {
        entries.forEach(e => {
          if (!e.isIntersecting) return;
          navLinks.forEach(a => a.classList.toggle("active", a.getAttribute("href") === "#" + e.target.id));
        });
      }, { rootMargin: "-45% 0px -50% 0px" });
      sections.forEach(s => s && io.observe(s));
    }
  
    
    function setupTabs(tablist) {
      const tabs = [...tablist.querySelectorAll('[role="tab"]')];
      const select = tab => {
        tabs.forEach(t => {
          const on = t === tab;
          t.setAttribute("aria-selected", String(on));
          t.tabIndex = on ? 0 : -1;
          document.getElementById(t.getAttribute("aria-controls")).hidden = !on;
        });
      };
      tabs.forEach((tab, i) => {
        tab.addEventListener("click", () => select(tab));
        tab.addEventListener("keydown", e => {
          const keys = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 };
          if (e.key in keys) {
            e.preventDefault();
            const next = tabs[(i + keys[e.key] + tabs.length) % tabs.length];
            next.focus(); select(next);
          } else if (e.key === "Home") { e.preventDefault(); tabs[0].focus(); select(tabs[0]); }
          else if (e.key === "End") { e.preventDefault(); tabs.at(-1).focus(); select(tabs.at(-1)); }
        });
      });
    }
    document.querySelectorAll('[role="tablist"]').forEach(setupTabs);
  
    // Botón copiar código
    const copyBtn = document.getElementById("copyBtn");
    copyBtn.addEventListener("click", async () => {
      const visible = document.querySelector(".code-tabs pre:not([hidden])");
      try {
        await navigator.clipboard.writeText(visible.textContent);
        copyBtn.textContent = "Copiado";
      } catch {
        copyBtn.textContent = "No se pudo copiar";
      }
      setTimeout(() => (copyBtn.textContent = "Copiar"), 1600);
    });
  
    
    const ZONES = [
      { id: "z1", short: "Soleada",    t: 30.3, h: 60, chip: [66, 50] },
      { id: "z2", short: "Sombra",     t: 22.4, h: 72, chip: [336, 128] },
      { id: "z3", short: "Intermedia", t: 24.7, h: 68, chip: [322, 246] },
      { id: "z4", short: "Intermedia", t: 26.1, h: 63, chip: [192, 160] },
      { id: "z5", short: "Refugio",    t: 20.6, h: 75, chip: [56, 206] }
    ];
    const criteria = { tmax: 30, tmin: 20, hmin: 60 };
    const INTERVAL_MS = 2000;
  
    ZONES.forEach(z => (z.base = { t: z.t, h: z.h }));
  
    const gauss = () => (Math.random() + Math.random() + Math.random() - 1.5) / 1.5;
    function nextReading(z) {
      z.t += (z.base.t - z.t) * 0.12 + gauss() * 0.35;
      z.h += (z.base.h - z.h) * 0.12 + gauss() * 1.1;
      z.h = Math.min(100, Math.max(0, z.h));
    }
  
    const T = z => Math.round(z.t * 10) / 10;
    const H = z => Math.round(z.h);
    function statusOf(z) {
      if (T(z) > criteria.tmax) return "high";
      if (T(z) < criteria.tmin || H(z) < criteria.hmin) return "low";
      return "ok";
    }
  
    const SVG_NS = "http://www.w3.org/2000/svg";
    const STATUS_COLOR = { ok: "#2E8B4E", high: "#C0392B", low: "#D98A1C" };
    const labelsLayer = document.getElementById("mapLabels");
    const chips = {};
  
    ZONES.forEach(z => {
      const g = document.createElementNS(SVG_NS, "g");
      g.setAttribute("class", "map-chip");
      g.setAttribute("transform", `translate(${z.chip[0]} ${z.chip[1]})`);
      g.innerHTML = `
        <rect width="96" height="54" rx="10"/>
        <circle class="dot" cx="12" cy="13" r="4.5"/>
        <text class="name" x="21" y="17">${z.short}</text>
        <text class="temp" x="10" y="36"></text>
        <text class="hum"  x="10" y="48"></text>`;
      labelsLayer.appendChild(g);
      chips[z.id] = {
        dot: g.querySelector(".dot"),
        temp: g.querySelector(".temp"),
        hum: g.querySelector(".hum"),
        shape: document.querySelector(`.zone[data-zone="${z.id}"]`)
      };
    });
  
    function renderMap() {
      ZONES.forEach(z => {
        const st = statusOf(z), c = chips[z.id];
        c.temp.textContent = `${T(z).toFixed(1)} °C`;
        c.hum.textContent = `${H(z)} %HR`;
        c.dot.setAttribute("fill", STATUS_COLOR[st]);
        c.shape.setAttribute("class", "zone " + st);
      });
    }
  
    function tick() { ZONES.forEach(nextReading); renderMap(); }
  
    let timer = setInterval(tick, INTERVAL_MS);
    document.addEventListener("visibilitychange", () => {
      clearInterval(timer);
      if (!document.hidden) timer = setInterval(tick, INTERVAL_MS);
    });
  
    renderMap();
  })();