(() => {
  "use strict";

  // ---------- Pestañas: Iniciar sesión / Crear cuenta ----------
  const tabs = [...document.querySelectorAll('.auth-tabs [role="tab"]')];

  function selectTab(tab) {
    tabs.forEach(t => {
      const on = t === tab;
      t.setAttribute("aria-selected", String(on));
      t.tabIndex = on ? 0 : -1;
      document.getElementById(t.getAttribute("aria-controls")).hidden = !on;
    });
    document.title = (tab.id === "tabRegistro" ? "Crear cuenta" : "Iniciar sesión") + " · IoTurtle";
  }

  tabs.forEach((tab, i) => {
    tab.addEventListener("click", () => selectTab(tab));
    tab.addEventListener("keydown", e => {
      if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
        e.preventDefault();
        const next = tabs[(i + (e.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length];
        next.focus();
        selectTab(next);
      }
    });
  });

  // /login#registro abre directo la pestaña "Crear cuenta"
  if (location.hash === "#registro") selectTab(document.getElementById("tabRegistro"));

  // ---------- Mensajes del backend (?error=... o ?ok=...) ----------
  const MENSAJES = {
    credenciales: "Correo o contraseña incorrectos.",
    existe: "Ya hay una cuenta con ese correo. Inicia sesión.",
    google: "No se pudo iniciar sesión con Google. Intenta de nuevo.",
    usa_google: "Esta cuenta se creó con Google. Usa el botón de Google.",
    datos: "Revisa los datos del formulario.",
    sesion: "Inicia sesión para entrar al dashboard.",
    registrado: "Cuenta creada. Ya puedes iniciar sesión.",
    salida: "Cerraste sesión."
  };
  const params = new URLSearchParams(location.search);
  const msg = document.getElementById("authMsg");
  const codigo = params.get("error") || params.get("ok");
  if (codigo) {
    msg.textContent = MENSAJES[codigo] || codigo;
    msg.className = "auth-msg " + (params.get("error") ? "error" : "ok");
    msg.hidden = false;
  }

  // ---------- Mostrar / ocultar contraseña ----------
  document.querySelectorAll(".pass-toggle").forEach(btn => {
    btn.addEventListener("click", () => {
      const input = btn.previousElementSibling;
      const mostrar = input.type === "password";
      input.type = mostrar ? "text" : "password";
      btn.textContent = mostrar ? "Ocultar" : "Ver";
      btn.setAttribute("aria-label", mostrar ? "Ocultar contraseña" : "Mostrar contraseña");
    });
  });

  // ---------- Validación antes de enviar ----------
  function marcarError(input, texto) {
    const campo = input.closest(".field");
    let nota = campo.querySelector(".field-error");
    if (!nota) {
      nota = document.createElement("small");
      nota.className = "field-error";
      campo.appendChild(nota);
    }
    nota.textContent = texto;
    input.setAttribute("aria-invalid", "true");
  }

  function limpiar(form) {
    form.querySelectorAll(".field-error").forEach(n => n.remove());
    form.querySelectorAll("[aria-invalid]").forEach(i => i.removeAttribute("aria-invalid"));
  }

  document.querySelectorAll(".auth-form").forEach(form => {
    form.addEventListener("submit", e => {
      limpiar(form);
      let primero = null;
      const fallo = (input, texto) => { marcarError(input, texto); primero ??= input; };

      form.querySelectorAll("input[required]").forEach(input => {
        if (!input.value.trim()) fallo(input, "Este campo es obligatorio.");
        else if (input.type === "email" && !input.checkValidity()) fallo(input, "Escribe un correo válido.");
      });

      const pass = form.querySelector('input[name="contrasena"]');
      const confirmar = form.querySelector('input[name="confirmar"]');
      if (confirmar) {
        if (pass.value && pass.value.length < 8) fallo(pass, "Debe tener mínimo 8 caracteres.");
        if (confirmar.value && confirmar.value !== pass.value) fallo(confirmar, "Las contraseñas no coinciden.");
      }

      if (primero) {
        e.preventDefault();
        primero.focus();
        return;
      }

      // Evita doble clic mientras Flask responde
      const boton = form.querySelector(".auth-submit");
      boton.disabled = true;
      boton.textContent = "Enviando…";
    });
  });
})();
