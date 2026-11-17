// ==============================================================================
// AURA STUDIO — Markdown, Claude Thinking Blocks, and Code Renderer
// ==============================================================================

function renderMarkdown(content) {
  if (!content) return "";

  // 1. Claude-style Thinking Tag: <think>...</think>
  let html = content.replace(/<think>([\s\S]*?)<\/think>/gi, (match, thought) => {
    const cleanThought = thought.trim();
    if (!cleanThought) return "";
    return `
      <details class="thought-box">
        <summary class="thought-toggle">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>
          <span>Düşünce Süreci</span>
          <span class="thought-badge">Gizle / Göster</span>
        </summary>
        <div class="thought-content">${cleanThought.replace(/\n/g, '<br>')}</div>
      </details>
    `;
  });

  // 2. Math formulas: $$formula$$ (Display) or $formula$ (Inline)
  html = html.replace(/\$\$([\s\S]*?)\$\$/g, (match, formula) => {
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

  // 3. Multi-line Code blocks: ```lang ... ```
  html = html.replace(/```([a-zA-Z0-9_\-\.]*)\n([\s\S]*?)```/g, (match, lang, code) => {
    const language = lang.trim().toLowerCase() || "code";
    const cleanCode = code.trim();
    const lines = cleanCode.split("\n");

    const linesHtml = lines.map((line, idx) => {
      let isAdd = false;
      let isDel = false;
      if (language === "diff" || language === "patch") {
        if (line.startsWith("+") && !line.startsWith("+++")) isAdd = true;
        if (line.startsWith("-") && !line.startsWith("---")) isDel = true;
      }

      // 1. HTML escape
      let safe = line.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

      // 2. Extract strings and comments into placeholders to prevent attribute quote collisions
      const tokens = [];
      safe = safe.replace(/(\/\/.*$|#.*$|"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')/g, (match) => {
        const id = `___TOKEN_${tokens.length}___`;
        if (match.startsWith("//") || match.startsWith("#")) {
          tokens.push(`<span class="token-comment">${match}</span>`);
        } else {
          tokens.push(`<span class="token-string">${match}</span>`);
        }
        return id;
      });

      // 3. Highlight keywords and types safely
      safe = safe
        .replace(/\b(fn|def|let|mut|const|struct|impl|class|import|from|pub|return|if|else|match|for|in|while|async|await)\b/g, '<span class="token-keyword">$1</span>')
        .replace(/\b(String|str|bool|u32|i32|u64|i64|f64|f32|usize|Vec|Option|Result|int|float|dict|list)\b/g, '<span class="token-type">$1</span>');

      // 4. Restore strings and comments
      tokens.forEach((t, i) => {
        safe = safe.replace(`___TOKEN_${i}___`, t);
      });

      const trClass = isAdd ? ' class="diff-line-add"' : isDel ? ' class="diff-line-del"' : '';
      return `<tr${trClass}><td class="code-line-num">${idx + 1}</td><td class="code-line-text">${safe || "&nbsp;"}</td></tr>`;
    }).join("");

    const blockId = "code-" + Math.random().toString(36).substring(2, 9);

    return `
      <div class="code-container" id="${blockId}">
        <div class="code-header">
          <span class="code-lang">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="16 18 22 12 16 6"></polyline><polyline points="8 6 2 12 8 18"></polyline></svg>
            ${language}
          </span>
          <div class="code-actions">
            <button class="btn-code-action btn-copy" onclick="copyCodeContent('${blockId}')">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
              <span>Kopyala</span>
            </button>
          </div>
        </div>
        <div class="code-content">
          <table class="code-table"><tbody>${linesHtml}</tbody></table>
        </div>
      </div>
    `;
  });

  // 4. Markdown Tables: | col1 | col2 |
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

  // 5. Inline formatting: bold, italic, inline code
  html = html
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/`([^`]+)`/g, '<code style="background:rgba(255,255,255,0.06); padding:2px 5px; border-radius:4px; font-family:var(--font-code); color:var(--text-main); font-size:0.82rem; border:1px solid var(--border-hairline);">$1</code>')
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
    const btn = container.querySelector(".btn-copy span");
    if (btn) {
      const oldText = btn.textContent;
      btn.textContent = "Kopyalandı!";
      setTimeout(() => { btn.textContent = oldText; }, 1800);
    }
  });
}
