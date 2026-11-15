(() => {
  const panel = document.getElementById("ventilador");
  if (!panel) return;
  const pill = document.getElementById("ventPill");
  const nota = document.getElementById("ventNota");
  const mensaje = document.getElementById("ventMensaje");
  const botones = [...panel.querySelectorAll("button[data-estado]")];
  let esperado = null;   // estado que mandamos y que la Raspberry todavía no confirma

  function pintar(estado) {
    pill.className = "pill " + (estado === 1 ? "ok" : estado === 0 ? "apagado" : "");
    pill.textContent = estado === 1 ? "Encendido" : estado === 0 ? "Apagado" : "Sin datos";
    panel.classList.toggle("girando", estado === 1);
    botones.forEach(b => b.setAttribute("aria-pressed", String(Number(b.dataset.estado) === estado)));
  }

  function avisar(texto, tipo = "") {
    mensaje.textContent = texto;
    mensaje.className = "ventilador-mensaje " + tipo;
    mensaje.hidden = !texto;
  }

  async function consultar() {
    try {
      const r = await fetch("/api/ventilador");
      if (!r.ok) return;
      const d = await r.json();
      pintar(d.estado);
      if (d.confirmado) nota.textContent = "Confirmado por la Raspberry · " + d.confirmado;
      if (esperado !== null && d.estado === esperado) {
        avisar("La Raspberry confirmó el cambio.", "ok");
        esperado = null;
      }
    } catch { /* sin conexión: se intenta en la próxima vuelta */ }
  }

  async function enviar(estado) {
    botones.forEach(b => (b.disabled = true));
    avisar("Enviando la orden a ThingSpeak… puede tardar hasta 20 s si el canal está ocupado.");
    try {
      const r = await fetch("/api/ventilador", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ estado })
      });
      if (r.status === 401) return location.assign("/login?error=sesion");
      const d = await r.json();
      if (!r.ok) return avisar(d.error || "No se pudo enviar la orden.", "error");
      esperado = estado;
      avisar(`Orden enviada: ${estado ? "encender" : "apagar"}. Esperando que la Raspberry la aplique…`);
    } catch {
      avisar("No hay conexión con el servidor.", "error");
    } finally {
      botones.forEach(b => (b.disabled = false));
    }
  }

  botones.forEach(b => b.addEventListener("click", () => enviar(Number(b.dataset.estado))));
  const inicial = panel.dataset.estado === "" ? null : Number(panel.dataset.estado);
  pintar(inicial);
  setInterval(consultar, 10000);
})();
