/* static/assets/js/invoice.js
   Generic Invoice helpers (reusable across modules).
*/
(function (w) {
  const LS_KEY = "toc_last_invoice";

  const state = {
    last: null, // {invoice_id, invoice_no, source_type, source_id}
    cfg: {
      printButtonSelector: null,
      getSource: null, // function -> {source_type, source_id}
    },
    bound: false
  };

  function loadLastFromStorage() {
    try {
      const raw = localStorage.getItem(LS_KEY);
      if (!raw) return null;
      const obj = JSON.parse(raw);
      return obj && obj.invoice_id ? obj : null;
    } catch (e) {
      return null;
    }
  }

  function saveLastToStorage(last) {
    try {
      if (!last || !last.invoice_id) {
        localStorage.removeItem(LS_KEY);
        return;
      }
      localStorage.setItem(LS_KEY, JSON.stringify(last));
    } catch (e) {}
  }

  async function lookupInvoiceBySource(source_type, source_id) {
    const params = new URLSearchParams({ source_type, source_id });
    const res = await fetch(`/invoice/lookup?${params.toString()}`, { method: "GET" });
    const out = await res.json();
    if (out.status !== "success") return null;
    return out.invoice; // {invoice_id, invoice_no, ...}
  }

  function openPrint(invoice_id) {
    if (!invoice_id) return;
    w.open(`/invoice/${invoice_id}/print`, "_blank");
  }

  function enablePrintBtn(enable) {
    const sel = state.cfg.printButtonSelector;
    if (!sel) return;

    const btn = document.querySelector(sel);
    if (!btn) return;

    btn.disabled = !enable;
  }

  function bindPrintClick() {
    if (state.bound) return;
    state.bound = true;

    const sel = state.cfg.printButtonSelector;
    if (!sel) return;

    const btn = document.querySelector(sel);
    if (!btn) return;

    btn.addEventListener("click", async function () {
      // Prefer last invoice in memory/storage
      if (state.last && state.last.invoice_id) {
        openPrint(state.last.invoice_id);
        return;
      }

      // Otherwise lookup by source (after refresh etc.)
      if (typeof state.cfg.getSource === "function") {
        const s = state.cfg.getSource() || {};
        const source_type = (s.source_type || "").trim();
        const source_id = (s.source_id || "").trim();

        if (!source_type || !source_id) {
          if (w.dialog) w.dialog("Print Invoice", "Missing source info (cannot locate invoice).");
          return;
        }

        const inv = await lookupInvoiceBySource(source_type, source_id);
        if (!inv) {
          enablePrintBtn(false);
          if (w.dialog) w.dialog("Print Invoice", "No invoice found for this order yet.");
          return;
        }

        state.last = {
          invoice_id: inv.invoice_id,
          invoice_no: inv.invoice_no,
          source_type,
          source_id
        };
        saveLastToStorage(state.last);
        enablePrintBtn(true);
        openPrint(inv.invoice_id);
        return;
      }

      if (w.dialog) w.dialog("Print Invoice", "Print is not configured on this page.");
    });
  }

  async function refresh() {
    // If we already have one, keep enabled
    if (state.last && state.last.invoice_id) {
      enablePrintBtn(true);
      return state.last;
    }

    if (typeof state.cfg.getSource !== "function") {
      enablePrintBtn(false);
      return null;
    }

    const s = state.cfg.getSource() || {};
    const source_type = (s.source_type || "").trim();
    const source_id = (s.source_id || "").trim();

    if (!source_type || !source_id) {
      enablePrintBtn(false);
      return null;
    }

    const inv = await lookupInvoiceBySource(source_type, source_id);
    if (!inv) {
      enablePrintBtn(false);
      return null;
    }

    state.last = {
      invoice_id: inv.invoice_id,
      invoice_no: inv.invoice_no,
      source_type,
      source_id
    };
    saveLastToStorage(state.last);
    enablePrintBtn(true);
    return state.last;
  }

  const InvoiceUI = {
    init(cfg) {
      state.cfg = Object.assign(state.cfg, cfg || {});

      // Load from storage if present
      state.last = state.last || loadLastFromStorage();

      bindPrintClick();

      // enable/disable based on existing last invoice
      enablePrintBtn(!!(state.last && state.last.invoice_id));
    },

    setLastInvoice(last) {
      state.last = last || null;
      saveLastToStorage(state.last);
      enablePrintBtn(!!(state.last && state.last.invoice_id));
    },

    refresh
  };

  w.InvoiceUI = InvoiceUI;
})(window);
