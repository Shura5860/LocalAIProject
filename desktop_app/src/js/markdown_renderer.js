// Markdown, Smart Code Block (JetBrains Mono + Line Numbers), and KaTeX Math Renderer

function renderMarkdown(content) {
  if (!content) return "";

  // 1. Math formulas: $$formula$$ (Display) or $formula$ (Inline)
  let html = content.replace(/\$\$([\s\S]*?)\$\$/g, (match, formula) => {
    try {
      if (window.katex) {
        return `<div class="katex-display-wrapper">${window.katex.renderToString(formula.trim(), { displayMode: true })}</div>`;
      }
    } catch (e) {}
    return `<div class="katex-display-wrapper"><code>${formula}</code></div>`;
  });

  html = html.replace(/\$([^\$\n]+)\$/g, (match, formula) => {
    try {
      if (window.katex) {
        return window.katex.renderToString(formula.trim(), { displayMode: false });
      }
    } catch (e) {}
    return `<code>${formula}</code>`;
  });

  // 2. Multi-line Code blocks: ```lang ... ```
  html = html.replace(/```([a-zA-Z0-9_\-\.]*)\n([\s\S]*?)```/g, (match, lang, code) => {
    const language = lang.trim() || "code";
    const cleanCode = code.trim();
    const lines = cleanCode.split("\n");

    const linesHtml = lines.map((line, idx) => {
      // Basic syntax highlight tokens
      let highlighted = line
        .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
        .replace(/\b(fn|def|let|mut|const|struct|impl|class|import|from|pub|return|if|else|match|for|in|while|async|await)\b/g, '<span class="token-keyword">$1</span>')
        .replace(/\b(String|str|bool|u32|i32|usize|Vec|Option|Result|int|float|dict|list)\b/g, '<span class="token-type">$1</span>')
        .replace(/(["'])(.*?)\1/g, '<span class="token-string">$1$2$1</span>')
        .replace(/(\/\/.*$|#.*$)/g, '<span class="token-comment">$1</span>');

      return `<tr><td class="code-line-num">${idx + 1}</td><td class="code-line-text">${highlighted || "&nbsp;"}</td></tr>`;
    }).join("");

    const blockId = "code-" + Math.random().toString(36).substring(2, 9);

    return `
      <div class="code-container" id="${blockId}">
        <div class="code-header">
          <span class="code-lang">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="16 18 22 12 16 6"></polyline><polyline points="8 6 2 12 8 18"></polyline></svg>
            ${language}
          </span>
          <div class="code-actions">
            <button class="btn-code-action btn-copy" onclick="copyCodeContent('${blockId}')">📋 Kopyala</button>
          </div>
        </div>
        <div class="code-content">
          <table class="code-table"><tbody>${linesHtml}</tbody></table>
        </div>
      </div>
    `;
  });

  // 3. Markdown Tables: | col1 | col2 |
  html = html.replace(/((?:\|[^\n]+\|\r?\n?)+)/g, (match, tableText) => {
    const rows = tableText.trim().split("\n");
    if (rows.length < 2) return match;

    let tableHtml = '<table class="markdown-table"><thead>';
    const headerCols = rows[0].split("|").filter((c, i, a) => i !== 0 && i !== a.length - 1);
    tableHtml += '<tr>' + headerCols.map(c => `<th>${c.trim()}</th>`).join("") + '</tr></thead><tbody>';

    for (let i = 2; i < rows.length; i++) {
      const cols = rows[i].split("|").filter((c, idx, a) => idx !== 0 && idx !== a.length - 1);
      if (cols.length === headerCols.length) {
        tableHtml += '<tr>' + cols.map(c => `<td>${c.trim()}</td>`).join("") + '</tr>';
      }
    }
    tableHtml += '</tbody></table>';
    return tableHtml;
  });

  // 4. Inline formatting: bold, italic, inline code
  html = html
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/`([^`]+)`/g, '<code style="background:rgba(255,255,255,0.08); padding:2px 6px; border-radius:4px; font-family:var(--font-code); color:var(--accent-cyan); font-size:0.85rem;">$1</code>')
    .replace(/\n\n/g, '<br><br>')
    .replace(/\n/g, '<br>');

  return html;
}

function copyCodeContent(blockId) {
  const container = document.getElementById(blockId);
  if (!container) return;
  const lineTexts = container.querySelectorAll(".code-line-text");
  const fullText = Array.from(lineTexts).map(el => el.textContent).join("\n");

  navigator.clipboard.writeText(fullText).then(() => {
    const btn = container.querySelector(".btn-copy");
    if (btn) {
      btn.textContent = "✅ Kopyalandı!";
      setTimeout(() => { btn.textContent = "📋 Kopyala"; }, 2000);
    }
  });
}
