(() => {
  "use strict";

  const INTERVALO_MS = 15000;
  const TEXTO_ESTADO = { ok: "Óptima", high: "Alerta alta", low: "Alerta baja", none: "Sin datos" };
  const COLOR_ESTADO = { ok: "#2E8B4E", high: "#C0392B", low: "#D98A1C", none: "#9AA9A6" };
  const $ = id => document.getElementById(id);

  function pintarMapa(zonas) {
    zonas.forEach(z => {
      document.querySelectorAll(`.zone[data-field="${z.field}"], .recinto[data-field="${z.field}"]`).forEach(forma => {
        forma.classList.remove("ok", "high", "low", "none");
        forma.classList.add(z.estado);
      });

      const chip = document.querySelector(`[data-chip="${z.field}"]`);
      if (!chip) return;
      chip.querySelector(".temp").textContent = z.temp !== null ? `${z.temp.toFixed(1)} °C` : "--";
      chip.querySelector(".estado").textContent = TEXTO_ESTADO[z.estado];
      chip.querySelector(".dot").setAttribute("fill", COLOR_ESTADO[z.estado]);
    });
  }

  function pintarGenerales(generales) {
    const lista = $("generalesLista");
    lista.replaceChildren();
    generales.forEach(g => {
      const li = document.createElement("li");
      li.className = g.estado;
      const nombre = document.createElement("span");
      nombre.textContent = g.nombre;
      const valor = document.createElement("strong");
      valor.textContent = g.valor === null ? "--"
        : g.unidad === "%" ? `${Math.round(g.valor)} %` : `${g.valor.toFixed(1)} ${g.unidad}`;
      li.append(nombre, valor);
      lista.appendChild(li);
    });
  }

  function pintarAlertas(alertas) {
    const lista = $("alertasLista");
    lista.replaceChildren();
    if (!alertas.length) {
      const li = document.createElement("li");
      li.className = "empty";
      li.textContent = "Todas las zonas están dentro de sus criterios.";
      lista.appendChild(li);
      return;
    }
    alertas.forEach(a => {
      const li = document.createElement("li");
      li.className = a.tipo;
      const titulo = document.createElement("strong");
      titulo.textContent = a.titulo;
      const detalle = document.createElement("small");
      detalle.textContent = a.detalle;
      li.append(titulo, detalle);
      lista.appendChild(li);
    });
  }

  function badge(n) {
    const b = $("badgeAlertas");
    b.textContent = n;
    b.hidden = n === 0;
  }

  async function actualizar() {
    try {
      const r = await fetch("/api/estado", { cache: "no-store" });
      if (r.status === 401) { location.href = "/login?error=sesion"; return; }
      if (r.status === 409) { location.reload(); return; }
      if (!r.ok) throw new Error(r.status);
      const datos = await r.json();

      pintarMapa(datos.zonas);
      pintarGenerales(datos.generales);
      pintarAlertas(datos.alertas);
      badge(datos.alertas.length);

      const ultima = datos.ultima ? Date.parse(datos.ultima) : null;
      const viejo = !ultima || Date.now() - ultima > 2 * 60 * 1000;
      $("estadoConexion").classList.toggle("offline", viejo);
      $("estadoTexto").textContent = viejo ? "Sin datos recientes" : "En línea";
    } catch {
      $("estadoConexion").classList.add("offline");
      $("estadoTexto").textContent = "Sin conexión";
    }
  }

  actualizar();
  let timer = setInterval(actualizar, INTERVALO_MS);
  document.addEventListener("visibilitychange", () => {
    clearInterval(timer);
    if (!document.hidden) {
      actualizar();
      timer = setInterval(actualizar, INTERVALO_MS);
    }
  });
})();
