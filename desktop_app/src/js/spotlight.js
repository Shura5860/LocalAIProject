// Expandable Mini Spotlight (Alt + Space) & Command Output Logic

document.addEventListener("DOMContentLoaded", () => {
  const overlay = document.getElementById("spotlight-overlay");
  const input = document.getElementById("spotlight-input");
  const terminal = document.getElementById("spotlight-terminal");

  // Global Kısayol Dinleyicisi: Alt + Space
  window.addEventListener("keydown", (e) => {
    if (e.altKey && (e.code === "Space" || e.keyCode === 32)) {
      e.preventDefault();
      toggleSpotlight();
    } else if (e.key === "Escape" && overlay.classList.contains("active")) {
      closeSpotlight();
    }
  });

  function toggleSpotlight() {
    if (overlay.classList.contains("active")) {
      closeSpotlight();
    } else {
      openSpotlight();
    }
  }

  function openSpotlight() {
    overlay.classList.add("active");
    input.value = "";
    input.focus();
    terminal.classList.remove("visible");
    terminal.innerHTML = "";
  }

  function closeSpotlight() {
    overlay.classList.remove("active");
    input.blur();
  }

  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) {
      closeSpotlight();
    }
  });

  // Spotlight Komut Gönderimi (Enter)
  input.addEventListener("keydown", async (e) => {
    if (e.key === "Enter") {
      const q = input.value.trim();
      if (!q) return;

      terminal.classList.add("visible");
      terminal.innerHTML = `<span style="color:var(--accent-purple);">⚡ [Komut Yürütülüyor]:</span> ${q}\n<span style="color:var(--text-dim);">Lütfen bekleyin...</span>`;

      try {
        const res = await fetch("http://127.0.0.1:8000/agent/react", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ query: q, max_steps: 3, require_approval: false })
        });
        if (res.ok) {
          const data = await res.json();
          let out = `\n<span style="color:var(--accent-cyan);">=== ÇIKTI / SONUÇ ===</span>\n${data.final_answer}\n`;
          if (data.trace && data.trace.length > 0) {
            out += `\n<span style="color:var(--text-dim);">[İşlenen Adımlar: ${data.total_steps}]</span>`;
          }
          terminal.innerHTML = out;
        } else {
          const err = await res.json();
          terminal.innerHTML = `<span style="color:var(--accent-red);">Hata: ${err.detail || 'Sunucu hatası'}</span>`;
        }
      } catch (err) {
        terminal.innerHTML = `<span style="color:var(--accent-red);">Bağlantı hatası: ${err.message}</span>`;
      }
    }
  });
});
