(() => {
  const lista = document.getElementById("chatMensajes");
  const form = document.getElementById("chatForm");
  const texto = document.getElementById("chatTexto");
  const enviar = document.getElementById("chatEnviar");
  const sugerencias = document.getElementById("chatSugerencias");
  const historial = [];

  // Convierte la respuesta en HTML seguro: escapa todo y solo permite **negrilla** y listas con "- "
  function formatear(contenido) {
    const seguro = contenido
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
    let html = "", enLista = false;
    for (const linea of seguro.split("\n")) {
      const item = linea.match(/^\s*[-*•]\s+(.*)/);
      if (item) {
        if (!enLista) { html += "<ul>"; enLista = true; }
        html += `<li>${item[1]}</li>`;
        continue;
      }
      if (enLista) { html += "</ul>"; enLista = false; }
      if (linea.trim()) html += `<p>${linea}</p>`;
    }
    return html + (enLista ? "</ul>" : "");
  }

  function agregar(rol, contenido, clase = "") {
    const div = document.createElement("div");
    div.className = `chat-msg ${rol} ${clase}`.trim();
    if (rol === "asistente") div.innerHTML = formatear(contenido);
    else div.textContent = contenido;
    lista.appendChild(div);
    lista.scrollTop = lista.scrollHeight;
    return div;
  }

  async function preguntar(pregunta) {
    pregunta = pregunta.trim();
    if (!pregunta || enviar.disabled) return;

    agregar("usuario", pregunta);
    sugerencias.hidden = true;
    texto.value = "";
    ajustarAltura();
    enviar.disabled = true;
    const pensando = agregar("asistente", "Analizando tus datos…", "pensando");

    try {
      const r = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mensaje: pregunta, historial })
      });
      if (r.status === 401) return location.assign("/login?error=sesion");
      if (r.status === 409) return location.reload();
      const datos = await r.json();
      pensando.remove();

      if (!r.ok) {
        agregar("asistente", datos.error || "Algo falló. Intenta de nuevo.", "error");
        return;
      }
      agregar("asistente", datos.respuesta);
      historial.push({ rol: "usuario", texto: pregunta }, { rol: "asistente", texto: datos.respuesta });
      historial.splice(0, Math.max(0, historial.length - 6));
    } catch {
      pensando.remove();
      agregar("asistente", "No hay conexión con el servidor. Revisa tu internet e intenta de nuevo.", "error");
    } finally {
      enviar.disabled = false;
      texto.focus();
    }
  }

  function ajustarAltura() {
    texto.style.height = "auto";
    texto.style.height = Math.min(texto.scrollHeight, 160) + "px";
  }

  form.addEventListener("submit", e => { e.preventDefault(); preguntar(texto.value); });
  texto.addEventListener("input", ajustarAltura);
  texto.addEventListener("keydown", e => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); preguntar(texto.value); }
  });
  sugerencias.addEventListener("click", e => {
    if (e.target.matches("button")) preguntar(e.target.textContent);
  });
})();
