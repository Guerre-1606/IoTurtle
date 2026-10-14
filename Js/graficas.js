(() => {
  "use strict";

  const COLOR_FIELD = {
    field1: "#2a78d6",
    field2: "#eb6834",
    field3: "#1baf7a",
    field4: "#eda100",
    field5: "#6250d6",
    field6: "#e87ba4",
    field7: "#008300"
  };

  const TINTA = "#1E2B2F";
  const TINTA_SUAVE = "#5A6B68";
  const REJILLA = "rgba(23, 52, 79, .08)";
  const UMBRAL = "#5A6B68";
  const FUENTE = '"Source Sans 3", "Segoe UI", system-ui, sans-serif';

  const horaCorta = ms => new Date(ms).toLocaleTimeString("es-CO", { hour: "2-digit", minute: "2-digit" });
  const fechaHora = ms => new Date(ms).toLocaleString("es-CO", {
    day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit"
  });

  function formatoValor(valor, unidad) {
    if (valor === null || valor === undefined) return "--";
    return unidad === "%" ? `${Math.round(valor)} %` : `${valor.toFixed(1)} ${unidad}`;
  }

  const extras = {
    id: "ioturtleExtras",

    afterDatasetsDraw(chart, _args, opciones) {
      const { ctx, chartArea: area, scales: { y } } = chart;
      ctx.save();

      (opciones.umbrales || []).forEach(u => {
        if (u.valor === null || u.valor === undefined) return;
        const py = y.getPixelForValue(u.valor);
        if (py < area.top || py > area.bottom) return;

        ctx.strokeStyle = UMBRAL;
        ctx.lineWidth = 1;
        ctx.setLineDash([5, 4]);
        ctx.beginPath();
        ctx.moveTo(area.left, py);
        ctx.lineTo(area.right, py);
        ctx.stroke();
        ctx.setLineDash([]);

        ctx.font = `600 11px ${FUENTE}`;
        ctx.textAlign = "left";
        ctx.textBaseline = "bottom";
        const ancho = ctx.measureText(u.texto).width;
        ctx.fillStyle = "rgba(255, 255, 255, .9)";
        ctx.fillRect(area.left + 2, py - 17, ancho + 8, 14);
        ctx.fillStyle = TINTA_SUAVE;
        ctx.fillText(u.texto, area.left + 6, py - 3);
      });

      const etiquetas = [];
      const conEtiquetas = chart.data.datasets.length > 1 && !chart.$angosto;
      if (conEtiquetas) chart.data.datasets.forEach((ds, i) => {
        if (!chart.isDatasetVisible(i)) return;
        const puntos = chart.getDatasetMeta(i).data;
        for (let k = ds.data.length - 1; k >= 0; k--) {
          if (ds.data[k].y !== null) {
            etiquetas.push({ y: puntos[k].y, x: puntos[k].x, texto: ds.label, color: ds.borderColor });
            break;
          }
        }
      });

      etiquetas.sort((a, b) => a.y - b.y);
      for (let k = 1; k < etiquetas.length; k++) {
        if (etiquetas[k].y - etiquetas[k - 1].y < 15) etiquetas[k].y = etiquetas[k - 1].y + 15;
      }

      ctx.font = `600 12px ${FUENTE}`;
      ctx.textBaseline = "middle";
      ctx.textAlign = "left";
      etiquetas.forEach(e => {
        const x = area.right + 10;
        ctx.fillStyle = e.color;
        ctx.beginPath();
        ctx.arc(x, e.y, 4, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = TINTA;
        ctx.fillText(e.texto, x + 8, e.y);
      });

      const activos = chart.tooltip && chart.tooltip.getActiveElements();
      if (activos && activos.length) {
        const x = activos[0].element.x;
        ctx.strokeStyle = "rgba(23, 52, 79, .35)";
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(x, area.top);
        ctx.lineTo(x, area.bottom);
        ctx.stroke();
      }

      ctx.restore();
    }
  };

  function crear(canvas, { series, unidad, umbrales = [] }) {
    const largo = { value: false };
    const angosto = canvas.parentElement.clientWidth < 480;
    const espacioEtiquetas = series.length > 1 && !angosto ? 96 : 8;

    const grafica = new Chart(canvas, {
      type: "line",
      data: {
        datasets: series.map(s => ({
          label: s.nombre,
          field: s.field,
          data: [],
          borderColor: COLOR_FIELD[s.field],
          backgroundColor: COLOR_FIELD[s.field],
          borderWidth: 2,
          pointRadius: 0,
          pointHoverRadius: 5,
          pointHoverBorderWidth: 2,
          pointHoverBorderColor: "#fff",
          pointHitRadius: 10,
          tension: 0,
          spanGaps: false
        }))
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        parsing: false,
        interaction: { mode: "index", intersect: false, axis: "x" },
        layout: { padding: { right: espacioEtiquetas, top: 4 } },
        scales: {
          x: {
            type: "linear",
            grid: { color: REJILLA, drawTicks: false },
            border: { display: false },
            ticks: {
              color: TINTA_SUAVE,
              font: { family: FUENTE, size: 12 },
              maxRotation: 0,
              autoSkipPadding: 24,
              padding: 8,
              callback: v => (largo.value ? fechaHora(v) : horaCorta(v))
            }
          },
          y: {
            grid: { color: REJILLA, drawTicks: false },
            border: { display: false },
            ticks: {
              color: TINTA_SUAVE,
              font: { family: FUENTE, size: 12 },
              padding: 8,
              maxTicksLimit: 6,
              callback: v => (unidad === "%" ? `${v} %` : `${v}°`)
            }
          }
        },
        plugins: {
          legend: {
            display: series.length > 1,
            position: "top",
            align: "start",
            labels: {
              color: TINTA,
              font: { family: FUENTE, size: 13 },
              usePointStyle: true,
              pointStyle: "line",
              boxWidth: 22,
              padding: 14
            }
          },
          tooltip: {
            backgroundColor: "#fff",
            titleColor: TINTA,
            bodyColor: TINTA,
            borderColor: "rgba(23, 52, 79, .15)",
            borderWidth: 1,
            padding: 10,
            boxPadding: 4,
            usePointStyle: true,
            titleFont: { family: FUENTE, weight: "600" },
            bodyFont: { family: FUENTE },
            callbacks: {
              title: items => (items.length ? fechaHora(items[0].parsed.x) : ""),
              label: item => ` ${item.dataset.label}: ${formatoValor(item.parsed.y, unidad)}`,
              labelPointStyle: () => ({ pointStyle: "circle", rotation: 0 })
            }
          },
          ioturtleExtras: { umbrales }
        }
      },
      plugins: [extras]
    });

    grafica.$largo = largo;
    grafica.$angosto = angosto;
    grafica.$unidad = unidad;
    return grafica;
  }

  function actualizar(grafica, puntos, umbrales) {
    const tiempos = puntos.map(p => Date.parse(p.t));
    grafica.$largo.value = tiempos.length > 1 && tiempos[tiempos.length - 1] - tiempos[0] > 36 * 3600 * 1000;

    grafica.data.datasets.forEach(ds => {
      ds.data = puntos.map((p, i) => ({ x: tiempos[i], y: p[ds.field] }));
    });

    if (umbrales) grafica.options.plugins.ioturtleExtras.umbrales = umbrales;

    const valores = puntos.flatMap(p => grafica.data.datasets.map(ds => p[ds.field])).filter(v => v !== null);
    const limites = (grafica.options.plugins.ioturtleExtras.umbrales || []).map(u => u.valor);
    const todos = valores.concat(limites);
    if (todos.length) {
      const min = Math.min(...todos);
      const max = Math.max(...todos);
      const margen = Math.max(1, (max - min) * 0.08);
      grafica.options.scales.y.suggestedMin = Math.floor(min - margen);
      grafica.options.scales.y.suggestedMax = Math.ceil(max + margen);
    }

    grafica.update("none");

    const vacio = grafica.canvas.parentElement.querySelector(".chart-empty");
    if (vacio) vacio.hidden = valores.length > 0;
  }

  function tabla(contenedor, puntos, columnas, maximo = 50) {
    const filas = puntos.filter(p => columnas.some(c => p[c.field] !== null)).slice(-maximo).reverse();

    const tablaEl = document.createElement("table");
    tablaEl.className = "zone-table";
    const cabeza = tablaEl.createTHead().insertRow();
    ["Hora"].concat(columnas.map(c => c.nombre)).forEach(texto => {
      const th = document.createElement("th");
      th.textContent = texto;
      cabeza.appendChild(th);
    });

    const cuerpo = tablaEl.createTBody();
    filas.forEach(p => {
      const fila = cuerpo.insertRow();
      fila.insertCell().textContent = fechaHora(Date.parse(p.t));
      columnas.forEach(c => { fila.insertCell().textContent = formatoValor(p[c.field], c.unidad); });
    });

    if (!filas.length) {
      const celda = cuerpo.insertRow().insertCell();
      celda.colSpan = columnas.length + 1;
      celda.textContent = "No hay lecturas en este rango.";
    }

    contenedor.replaceChildren(tablaEl);
  }

  function umbralesTemperatura(c) {
    return [
      { valor: c.tmax, texto: `Máx. ${c.tmax.toFixed(1)} °C` },
      { valor: c.tmin, texto: `Mín. ${c.tmin.toFixed(1)} °C` }
    ];
  }

  function umbralesHumedad(c) {
    return [{ valor: c.hmin, texto: `Mín. ${Math.round(c.hmin)} %` }];
  }

  window.IoGraficas = {
    COLOR_FIELD, crear, actualizar, tabla, formatoValor, fechaHora,
    umbralesTemperatura, umbralesHumedad
  };
})();
