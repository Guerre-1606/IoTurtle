(() => {
  "use strict";

  const G = window.IoGraficas;
  const raiz = document.querySelector("[data-rango]");
  if (!raiz || !window.Chart) return;

  const rango = raiz.dataset.rango;
  const intervalo = rango === "live" ? 15000 : 60000;
  const config = JSON.parse(document.getElementById("seriesConfig").textContent);
  const generales = config.generales || [];

  const temperatura = config.zonas.map(z => ({ field: z.field, nombre: z.nombre, unidad: "°C" }));
  const humedad = generales.filter(g => g.unidad === "%").map(g => ({ field: g.field, nombre: g.nombre, unidad: "%" }));
  const sueloAmbiente = generales.filter(g => g.unidad === "°C").map(g => ({
    field: g.field, nombre: g.nombre === "Temperatura del suelo" ? "Suelo" : g.nombre === "Temperatura ambiente" ? "Ambiente" : g.nombre, unidad: "°C"
  }));

  const definiciones = [
    { id: "graficaZonas", series: temperatura, unidad: "°C", umbrales: G.umbralesTemperatura },
    { id: "graficaHumedad", series: humedad, unidad: "%", umbrales: G.umbralesHumedad },
    { id: "graficaSuelo", series: sueloAmbiente, unidad: "°C", umbrales: null }
  ];

  const graficas = definiciones
    .filter(d => document.getElementById(d.id) && d.series.length)
    .map(d => ({ ...d, chart: G.crear(document.getElementById(d.id), { series: d.series, unidad: d.unidad }) }));

  const tabla = document.getElementById("tablaLecturas");
  const info = document.getElementById("rangoInfo");
  const estadoTexto = document.getElementById("estadoTexto");
  const estadoConexion = document.getElementById("estadoConexion");

  const TEXTO_GRUPO = { "5min": "5 min", "15min": "15 min", "1h": "1 hora", "6h": "6 horas" };

  async function actualizar() {
    try {
      const r = await fetch(`/api/serie?rango=${encodeURIComponent(rango)}`, { cache: "no-store" });
      if (r.status === 401) { location.href = "/login?error=sesion"; return; }
      if (r.status === 409) { location.reload(); return; }
      if (!r.ok) throw new Error(r.status);
      const datos = await r.json();

      graficas.forEach(g => {
        G.actualizar(g.chart, datos.puntos, g.umbrales ? g.umbrales(datos.criterios) : []);
      });

      if (tabla) {
        G.tabla(tabla, datos.puntos, temperatura.concat(humedad, sueloAmbiente));
      }

      if (info && datos.agrupado) {
        info.textContent = `Promedios cada ${TEXTO_GRUPO[datos.agrupado] || datos.agrupado}. Las líneas punteadas son los límites de temperatura.`;
      }

      if (estadoTexto && rango === "live") {
        const ultimo = datos.puntos.length ? Date.parse(datos.puntos[datos.puntos.length - 1].t) : null;
        const viejo = !ultimo || Date.now() - ultimo > 2 * 60 * 1000;
        estadoConexion.classList.toggle("offline", viejo);
        estadoTexto.textContent = viejo ? "Sin datos recientes" : "En línea";
      }
    } catch {
      if (estadoTexto) {
        estadoConexion.classList.add("offline");
        estadoTexto.textContent = "Sin conexión";
      }
    }
  }

  actualizar();
  let timer = setInterval(actualizar, intervalo);
  document.addEventListener("visibilitychange", () => {
    clearInterval(timer);
    if (!document.hidden) {
      actualizar();
      timer = setInterval(actualizar, intervalo);
    }
  });
})();
