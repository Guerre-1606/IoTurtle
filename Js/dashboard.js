(() => {
  "use strict";

  const INTERVALO_MS = 15000;
  const TEXTO_ESTADO = { ok: "Óptima", high: "Alerta alta", low: "Alerta baja", none: "Sin datos" };

  const $ = id => document.getElementById(id);
  let ultimaHora = null;

  function celda(texto) {
    const td = document.createElement("td");
    td.textContent = texto;
    return td;
  }

  function pintarZonas(zonas) {
    const body = $("zonasBody");
    body.replaceChildren();

    if (!zonas.length) {
      const tr = document.createElement("tr");
      const td = celda("Todavía no hay lecturas.");
      td.colSpan = 3;
      tr.appendChild(td);
      body.appendChild(tr);
      return;
    }

    zonas.forEach(z => {
      const tr = document.createElement("tr");
      tr.appendChild(celda(z.nombre));
      tr.appendChild(celda(z.temp !== null ? `${z.temp.toFixed(1)} °C` : "--"));

      const td = document.createElement("td");
      const pill = document.createElement("span");
      pill.className = "pill " + z.estado;
      pill.textContent = TEXTO_ESTADO[z.estado];
      td.appendChild(pill);
      tr.appendChild(td);

      body.appendChild(tr);
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
      if (g.valor === null) valor.textContent = "--";
      else valor.textContent = g.unidad === "%" ? `${Math.round(g.valor)} %` : `${g.valor.toFixed(1)} ${g.unidad}`;
      li.append(nombre, valor);
      lista.appendChild(li);
    });
  }

  function pintarAlertas(alertas, hora) {
    const lista = $("alertasLista");
    lista.replaceChildren();

    if (!alertas.length) {
      const li = document.createElement("li");
      li.className = "empty";
      li.textContent = "Todas las zonas están dentro de sus criterios.";
      lista.appendChild(li);
      return;
    }

    const horaTexto = hora ? hora.toLocaleTimeString("es-CO", { hour: "2-digit", minute: "2-digit" }) : "";
    alertas.forEach(a => {
      const li = document.createElement("li");
      li.className = a.tipo;
      const titulo = document.createElement("strong");
      titulo.textContent = a.titulo;
      const detalle = document.createElement("small");
      detalle.textContent = horaTexto ? `${a.detalle} · ${horaTexto}` : a.detalle;
      li.append(titulo, detalle);
      lista.appendChild(li);
    });
  }

  function pintarKpis(k) {
    $("kpiOptimas").textContent = k ? k.optimas : "--";
    $("kpiTotal").textContent = k ? k.total : "--";
    $("kpiGradiente").textContent = k && k.gradiente !== null ? k.gradiente.toFixed(1) : "--";

    const alertas = $("kpiAlertas");
    alertas.textContent = k ? k.alertas : "--";
    alertas.classList.toggle("t-high", !!k && k.alertas > 0);

    const badge = $("badgeAlertas");
    badge.textContent = k ? k.alertas : 0;
    badge.hidden = !k || k.alertas === 0;
  }

  function pintarHace() {
    const el = $("kpiUltima");
    if (!ultimaHora) { el.textContent = "--"; return; }

    const seg = Math.max(0, Math.round((Date.now() - ultimaHora) / 1000));
    if (seg < 60) el.textContent = `hace ${seg} s`;
    else if (seg < 3600) el.textContent = `hace ${Math.floor(seg / 60)} min`;
    else el.textContent = ultimaHora.toLocaleTimeString("es-CO", { hour: "2-digit", minute: "2-digit" });
  }

  let graficaAwag = null;

  function pintarAwag(a) {
    const indice = $("awagIndice"), categoria = $("awagCategoria"), lista = $("awagLista");
    if (!a) {
      indice.textContent = "--";
      $("awagCwas").textContent = "--";
      categoria.className = "pill none";
      categoria.textContent = "Sin datos";
      lista.innerHTML = '<li class="empty">No hay lecturas en las últimas 24 h.</li>';
      return;
    }

    indice.textContent = a.indice;
    $("awagCwas").textContent = a.cwas.toFixed(1);
    categoria.className = "pill " + a.clase;
    categoria.textContent = a.categoria;

    lista.replaceChildren();
    a.parametros.forEach(p => {
      const li = document.createElement("li");
      const nivel = p.puntaje <= 3 ? "ok" : p.puntaje <= 6 ? "low" : "high";
      const cab = document.createElement("div");
      const nombre = document.createElement("span");
      nombre.textContent = p.nombre;
      const valor = document.createElement("strong");
      valor.className = "t-" + nivel;
      valor.textContent = p.puntaje.toFixed(1);
      cab.append(nombre, valor);
      const barra = document.createElement("span");
      barra.className = "awag-barra " + nivel;
      barra.style.setProperty("--p", ((p.puntaje - 1) / 9 * 100).toFixed(0) + "%");
      const det = document.createElement("small");
      det.textContent = p.detalle;
      li.append(cab, barra, det);
      lista.appendChild(li);
    });

    if (typeof Chart === "undefined") return;
    const css = getComputedStyle(document.documentElement);
    const color = css.getPropertyValue("--" + (a.clase === "high" ? "high" : a.clase === "low" ? "low" : "forest")).trim();
    const datos = a.parametros.map(p => p.puntaje);
    if (graficaAwag) {
      graficaAwag.data.datasets[0].data = datos;
      graficaAwag.data.datasets[0].borderColor = color;
      graficaAwag.data.datasets[0].backgroundColor = color + "33";
      graficaAwag.update();
      return;
    }
    graficaAwag = new Chart($("graficaAwag"), {
      type: "radar",
      data: {
        labels: a.parametros.map(p => p.nombre),
        datasets: [{ data: datos, borderColor: color, backgroundColor: color + "33", borderWidth: 2, pointRadius: 3, pointBackgroundColor: color }]
      },
      options: {
        responsive: true, maintainAspectRatio: false, animation: { duration: 400 }, layout: { padding: 6 },
        plugins: { legend: { display: false }, tooltip: { callbacks: { label: c => ` ${c.raw.toFixed(1)} / 10` } } },
        scales: { r: { min: 0, max: 10, ticks: { stepSize: 2, backdropColor: "transparent", font: { size: 10 } },
                       pointLabels: { font: { size: 11, weight: "600" } } } }
      }
    });
  }

  function conexion(ok, texto) {
    $("estadoConexion").classList.toggle("offline", !ok);
    $("estadoTexto").textContent = texto;
  }

  async function actualizar() {
    try {
      const r = await fetch("/api/estado", { cache: "no-store" });
      if (r.status === 401) { location.href = "/login?error=sesion"; return; }
      if (r.status === 409) { location.reload(); return; }
      if (!r.ok) throw new Error(r.status);

      const datos = await r.json();
      ultimaHora = datos.ultima ? new Date(datos.ultima) : null;

      pintarZonas(datos.zonas);
      pintarGenerales(datos.generales);
      pintarAlertas(datos.alertas, ultimaHora);
      pintarKpis(datos.kpis);
      pintarAwag(datos.awag);
      pintarHace();

      const viejo = ultimaHora && Date.now() - ultimaHora > 2 * 60 * 1000;
      conexion(!viejo, viejo ? "Sin datos recientes" : "En línea");
    } catch {
      conexion(false, "Sin conexión");
    }
  }

  actualizar();
  let timer = setInterval(actualizar, INTERVALO_MS);
  setInterval(pintarHace, 1000);

  document.addEventListener("visibilitychange", () => {
    clearInterval(timer);
    if (!document.hidden) {
      actualizar();
      timer = setInterval(actualizar, INTERVALO_MS);
    }
  });
})();
