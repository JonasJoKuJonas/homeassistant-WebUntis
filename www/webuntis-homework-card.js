/**
 * WebUntis Homework Card
 *
 * Renders the "homeworks" attribute of a WebUntis homework-list sensor
 * (sensor.<name>_homework_list) as a grouped list, similar to the
 * "Hausaufgaben" view on webuntis.com, including a print button.
 *
 * Installation:
 *   1. Copy this file to <config>/www/webuntis-homework-card.js
 *   2. Add it as a Lovelace resource:
 *        Settings -> Dashboards -> ... (top right) -> Resources -> Add resource
 *        URL: /local/webuntis-homework-card.js   Type: JavaScript module
 *   3. Add a card to your dashboard:
 *        type: custom:webuntis-homework-card
 *        entity: sensor.<name>_homework_list
 *        hide_overdue: false # optional, hides the "Verpasst" group entirely when true
 */

const GROUP_ORDER = ["due_soon", "open", "overdue", "completed"];

const DEFAULT_LABELS_DE = {
  title: "Hausaufgaben",
  due_soon: "Bald fällig",
  open: "Noch nicht abgeschlossen",
  overdue: "Verpasst",
  completed: "Erledigt",
  subject: "Fach",
  teacher: "Lehrkraft",
  assigned: "Aufgabedatum",
  due: "Fälligkeitsdatum",
  empty: "Keine Hausaufgaben",
  print: "Drucken",
};

const DEFAULT_LABELS_EN = {
  title: "Homework",
  due_soon: "Due soon",
  open: "Not yet completed",
  overdue: "Missed",
  completed: "Completed",
  subject: "Subject",
  teacher: "Teacher",
  assigned: "Assigned",
  due: "Due date",
  empty: "No homework",
  print: "Print",
};

const GROUP_ROW_COLOR = {
  due_soon: "rgba(255, 152, 0, 0.15)",
  open: "transparent",
  overdue: "rgba(244, 67, 54, 0.15)",
  completed: "rgba(76, 175, 80, 0.12)",
};

class WebuntisHomeworkCard extends HTMLElement {
  setConfig(config) {
    if (!config.entity) {
      throw new Error("Bitte eine 'entity' angeben (sensor.<name>_homework_list)");
    }
    this._config = config;
    this._dueSoonDays = Number.isFinite(config.due_soon_days)
      ? config.due_soon_days
      : 3;
    this._showCompleted = !!config.show_completed;
    this._hideOverdue = !!config.hide_overdue;

    if (!this.shadowRoot) {
      this.attachShadow({ mode: "open" });
    }
    this._built = false;
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    const state = this._hass && this._hass.states[this._config.entity];
    const homeworks =
      (state && state.attributes && state.attributes.homeworks) || [];
    return 2 + Math.ceil(homeworks.length / 2);
  }

  _labels() {
    const lang = (this._hass && this._hass.language) || "de";
    const base = lang.startsWith("de") ? DEFAULT_LABELS_DE : DEFAULT_LABELS_EN;
    return { ...base, ...(this._config.labels || {}) };
  }

  _formatDate(isoDate) {
    if (!isoDate) return "";
    const lang = (this._hass && this._hass.language) || "de-DE";
    try {
      const d = new Date(isoDate + "T00:00:00");
      const formatted = new Intl.DateTimeFormat(lang, {
        weekday: "long",
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
      }).format(d);
      return formatted.charAt(0).toUpperCase() + formatted.slice(1);
    } catch (err) {
      return isoDate;
    }
  }

  _group(homework) {
    if (homework.completed) return "completed";
    if (!homework.due_date) return "open";
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const due = new Date(homework.due_date + "T00:00:00");
    const soonCutoff = new Date(today);
    soonCutoff.setDate(soonCutoff.getDate() + this._dueSoonDays);

    if (due < today) return "overdue";
    if (due <= soonCutoff) return "due_soon";
    return "open";
  }

  _escape(str) {
    if (str === null || str === undefined) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  _buildGroups(homeworks) {
    const groups = { due_soon: [], open: [], overdue: [], completed: [] };
    for (const hw of homeworks) {
      const group = this._group(hw);
      if (group === "completed" && !this._showCompleted) continue;
      if (group === "overdue" && this._hideOverdue) continue;
      groups[group].push(hw);
    }
    for (const key of Object.keys(groups)) {
      groups[key].sort((a, b) => (a.due_date || "").localeCompare(b.due_date || ""));
    }
    return groups;
  }

  _tableHtml(groups, labels, forPrint) {
    let html = "";
    for (const groupKey of GROUP_ORDER) {
      const items = groups[groupKey];
      if (!items || items.length === 0) continue;

      html += `<div class="group-header">${this._escape(labels[groupKey])}</div>`;
      html += `<table class="hw-table"><thead><tr>
        <th>${this._escape(labels.subject)}</th>
        <th>${this._escape(labels.teacher)}</th>
        <th>${this._escape(labels.assigned)}</th>
        <th>${this._escape(labels.due)}</th>
        <th>${this._escape(labels.text || "")}</th>
      </tr></thead><tbody>`;

      for (const hw of items) {
        const bg = forPrint ? "" : `style="background:${GROUP_ROW_COLOR[groupKey]}"`;
        const strike = hw.completed ? "text-decoration:line-through;opacity:0.7;" : "";
        html += `<tr ${bg}>
          <td style="${strike}">${this._escape(hw.subject)}</td>
          <td style="${strike}">${this._escape(hw.teacher)}</td>
          <td style="${strike}">${this._escape(this._formatDate(hw.date_assigned))}</td>
          <td style="${strike}"><strong>${this._escape(this._formatDate(hw.due_date))}</strong></td>
          <td style="${strike}">${this._escape(hw.text)}</td>
        </tr>`;
      }
      html += `</tbody></table>`;
    }
    return html;
  }

  _print(groups, labels) {
    const title = this._escape(this._config.title || labels.title);
    const tableHtml = this._tableHtml(groups, labels, true);

    const iframe = document.createElement("iframe");
    iframe.style.position = "fixed";
    iframe.style.right = "0";
    iframe.style.bottom = "0";
    iframe.style.width = "0";
    iframe.style.height = "0";
    iframe.style.border = "0";
    document.body.appendChild(iframe);

    const doc = iframe.contentWindow.document;
    doc.open();
    doc.write(`<!DOCTYPE html><html><head><meta charset="utf-8"><title>${title}</title>
      <style>
        body { font-family: sans-serif; color: #000; padding: 16px; }
        h1 { font-size: 1.4em; margin-bottom: 12px; }
        .group-header { font-weight: bold; text-transform: uppercase; font-size: 0.8em;
          letter-spacing: 0.04em; margin-top: 16px; margin-bottom: 4px; border-bottom: 2px solid #000; }
        table.hw-table { width: 100%; border-collapse: collapse; margin-bottom: 8px; }
        table.hw-table th, table.hw-table td { text-align: left; padding: 4px 8px;
          border-bottom: 1px solid #ccc; font-size: 0.9em; vertical-align: top; }
        table.hw-table th { border-bottom: 2px solid #000; }
      </style>
      </head><body>
      <h1>${title}</h1>
      ${tableHtml || `<p>${this._escape(labels.empty)}</p>`}
      </body></html>`);
    doc.close();

    iframe.contentWindow.focus();
    iframe.contentWindow.print();
    setTimeout(() => document.body.removeChild(iframe), 1000);
  }

  _render() {
    if (!this._hass || !this._config) return;

    const entityId = this._config.entity;
    const state = this._hass.states[entityId];
    const labels = this._labels();
    const title = this._config.title || labels.title;

    if (!this._built) {
      this.shadowRoot.innerHTML = `
        <style>
          ha-card { padding: 0; }
          /* Fallback styling when ha-card isn't registered (e.g. standalone preview) */
          ha-card:not(:defined) { display: block; border-radius: 12px; background: var(--card-background-color, #fff);
            box-shadow: 0 2px 4px rgba(0,0,0,0.14), 0 2px 2px rgba(0,0,0,0.12); }
          .card-header { display: flex; align-items: center; justify-content: space-between;
            padding: 16px 16px 0 16px; }
          .card-header .name { font-size: 1.2em; font-weight: 400; }
          .print-button { cursor: pointer; color: var(--primary-color); background: none;
            border: none; padding: 8px; border-radius: 50%; display: flex; }
          .print-button:hover { background: var(--secondary-background-color); }
          .print-button svg { fill: currentColor; width: 22px; height: 22px; }
          .content { padding: 8px 16px 16px 16px; }
          .group-header { background: var(--secondary-background-color, #eee);
            color: var(--secondary-text-color); padding: 6px 10px; font-weight: 600;
            text-transform: uppercase; font-size: 0.72em; letter-spacing: 0.04em;
            margin-top: 12px; border-radius: 4px; }
          table.hw-table { width: 100%; border-collapse: collapse; }
          table.hw-table th { text-align: left; padding: 6px 10px; font-size: 0.8em;
            color: var(--secondary-text-color); border-bottom: 1px solid var(--divider-color); }
          table.hw-table td { padding: 6px 10px; font-size: 0.9em;
            border-bottom: 1px solid var(--divider-color); }
          .empty { padding: 16px 0; color: var(--secondary-text-color); }
        </style>
        <ha-card>
          <div class="card-header">
            <div class="name"></div>
            <button class="print-button" title="${this._escape(labels.print)}">
              <svg viewBox="0 0 24 24"><path d="M19,8H5A3,3 0 0,0 2,11V17H6V21H18V17H22V11A3,3 0 0,0 19,8M16,19H8V14H16V19M19,12A1,1 0 0,1 18,11A1,1 0 0,1 19,10A1,1 0 0,1 20,11A1,1 0 0,1 19,12M18,3H6V7H18V3Z" /></svg>
            </button>
          </div>
          <div class="content"></div>
        </ha-card>
      `;
      this.shadowRoot
        .querySelector(".print-button")
        .addEventListener("click", () => {
          const currentState = this._hass.states[this._config.entity];
          const homeworks =
            (currentState && currentState.attributes.homeworks) || [];
          this._print(this._buildGroups(homeworks), this._labels());
        });
      this._built = true;
    }

    this.shadowRoot.querySelector(".name").textContent = title;

    const content = this.shadowRoot.querySelector(".content");

    if (!state) {
      content.innerHTML = `<div class="empty">Entity '${this._escape(
        entityId
      )}' nicht gefunden.</div>`;
      return;
    }

    const homeworks = state.attributes.homeworks || [];
    const groups = this._buildGroups(homeworks);
    const html = this._tableHtml(groups, labels, false);

    content.innerHTML = html || `<div class="empty">${this._escape(labels.empty)}</div>`;
  }
}

customElements.define("webuntis-homework-card", WebuntisHomeworkCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "webuntis-homework-card",
  name: "WebUntis Homework Card",
  description:
    "Zeigt die WebUntis-Hausaufgabenliste gruppiert (Bald fällig / Noch nicht abgeschlossen / Verpasst) inkl. Druckfunktion an.",
});
