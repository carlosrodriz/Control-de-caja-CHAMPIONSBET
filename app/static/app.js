const money = (value) => `$${Number(value || 0).toFixed(2)}`;
const el = (id) => document.getElementById(id);

let state = null;
let soundEnabled = true;
let criticalPlatforms = new Set();
let socket = null;

function statusLabel(status) {
  return { optimo: "Óptimo", advertencia: "Advertencia", critico: "Crítico" }[status] || status;
}

function beep() {
  if (!soundEnabled) return;
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "square";
    osc.frequency.value = 880;
    gain.gain.value = 0.08;
    osc.connect(gain).connect(ctx.destination);
    osc.start();
    setTimeout(() => { osc.stop(); ctx.close(); }, 350);
  } catch (err) {
    console.warn("No se pudo reproducir la alerta sonora", err);
  }
}

function keepSelection(select, options, valueKey, labelFn) {
  const previous = select.value;
  select.innerHTML = options
    .map((o) => `<option value="${o[valueKey]}">${labelFn(o)}</option>`)
    .join("");
  if (previous && options.some((o) => String(o[valueKey]) === previous)) select.value = previous;
}

function renderPlatforms() {
  const container = el("platforms");
  container.innerHTML = state.platforms
    .map(
      (p) => `
      <div class="col-12 col-sm-6 col-lg-3">
        <div class="card shadow-sm h-100 platform-card status-${p.status}">
          <div class="card-body">
            <div class="d-flex justify-content-between align-items-start">
              <h3 class="h6 mb-1">${p.name}</h3>
              <span class="badge text-bg-${p.status === "critico" ? "danger" : p.status === "advertencia" ? "warning" : "success"}">${statusLabel(p.status)}</span>
            </div>
            <div class="fs-4 fw-bold">${money(p.balance)}</div>
            <div class="small text-muted">Mín ${money(p.min_balance)} · Aviso ${money(p.warning_balance)}</div>
            <button class="btn btn-sm btn-outline-secondary mt-2" data-threshold="${p.id}">Umbrales</button>
          </div>
        </div>
      </div>`
    )
    .join("");

  container.querySelectorAll("[data-threshold]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const platform = state.platforms.find((p) => p.id === Number(btn.dataset.threshold));
      el("thresholdPlatformId").value = platform.id;
      el("minBalance").value = platform.min_balance;
      el("warningBalance").value = platform.warning_balance;
      bootstrap.Modal.getOrCreateInstance(el("thresholdModal")).show();
    });
  });
}

function renderAlerts() {
  const criticals = state.platforms.filter((p) => p.status === "critico");
  const badge = el("alertBadge");
  if (criticals.length) {
    badge.className = "badge text-bg-danger";
    badge.textContent = `⚠ ${criticals.length} plataforma(s) en nivel crítico`;
  } else {
    badge.className = "badge text-bg-success";
    badge.textContent = "Abastecimiento OK";
  }
  const current = new Set(criticals.map((p) => p.id));
  const isNew = [...current].some((id) => !criticalPlatforms.has(id));
  if (isNew) beep();
  criticalPlatforms = current;
}

function renderAccounts() {
  el("accounts").innerHTML = state.accounts
    .map(
      (a) => `
      <li class="list-group-item d-flex justify-content-between align-items-center">
        <span>${a.name} <span class="badge text-bg-light">${a.kind}</span></span>
        <span class="fw-semibold ${a.balance < 0 ? "text-danger" : ""}">${money(a.balance)}</span>
      </li>`
    )
    .join("");
}

function renderPending() {
  const accountOptions = state.accounts
    .map((a) => `<option value="${a.id}">${a.name}</option>`)
    .join("");

  el("credits").innerHTML = state.credits.length
    ? state.credits
        .map(
          (t) => `
        <tr>
          <td>${t.client_name || "-"}</td>
          <td>${t.platform || "-"}</td>
          <td class="text-end">${money(t.outstanding)}</td>
          <td class="text-end text-nowrap">
            <input type="number" step="0.01" min="0.01" class="form-control form-control-sm d-inline-block" style="width:6rem" value="${t.outstanding.toFixed(2)}" data-amount="${t.id}" />
            <select class="form-select form-select-sm d-inline-block" style="width:9rem" data-account="${t.id}">${accountOptions}</select>
            <button class="btn btn-sm btn-success" data-pay="${t.id}">Abonar</button>
          </td>
        </tr>`
        )
        .join("")
    : `<tr><td colspan="4" class="text-muted text-center py-3">Sin créditos pendientes</td></tr>`;

  el("debts").innerHTML = state.debts.length
    ? state.debts
        .map(
          (t) => `
        <tr>
          <td>${t.platform || "-"}</td>
          <td class="small text-muted">${t.note || ""}</td>
          <td class="text-end">${money(t.outstanding)}</td>
          <td class="text-end text-nowrap">
            <input type="number" step="0.01" min="0.01" class="form-control form-control-sm d-inline-block" style="width:6rem" value="${t.outstanding.toFixed(2)}" data-amount="${t.id}" />
            <select class="form-select form-select-sm d-inline-block" style="width:9rem" data-account="${t.id}">${accountOptions}</select>
            <button class="btn btn-sm btn-danger" data-pay="${t.id}">Liquidar</button>
          </td>
        </tr>`
        )
        .join("")
    : `<tr><td colspan="4" class="text-muted text-center py-3">Sin deudas pendientes</td></tr>`;

  document.querySelectorAll("[data-pay]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = Number(btn.dataset.pay);
      const row = btn.closest("tr");
      await postJSON("/api/payments", {
        transaction_id: id,
        amount: Number(row.querySelector(`[data-amount="${id}"]`).value),
        account_id: Number(row.querySelector(`[data-account="${id}"]`).value),
        collaborator_id: Number(el("activeCollaborator").value) || null,
      });
    });
  });
}

function renderTransactions() {
  el("transactions").innerHTML = state.transactions.length
    ? state.transactions
        .map(
          (t) => `
        <tr>
          <td class="small">${t.created_at.replace("T", " ").slice(11)}</td>
          <td>${t.kind}</td>
          <td>${t.collaborator || "-"}</td>
          <td class="small">${[t.platform, t.account, t.client_name].filter(Boolean).join(" · ")}</td>
          <td class="text-end">${money(t.amount)}</td>
          <td><span class="badge text-bg-${t.status === "pagada" ? "success" : "warning"}">${t.status}</span></td>
        </tr>`
        )
        .join("")
    : `<tr><td colspan="6" class="text-muted text-center py-3">Sin movimientos</td></tr>`;
}

function render(newState) {
  state = newState;
  keepSelection(el("activeCollaborator"), state.collaborators, "id", (c) => (c.active ? c.name : `${c.name} (inactivo)`));
  keepSelection(el("txPlatform"), state.platforms, "id", (p) => `${p.name} · ${money(p.balance)}`);
  keepSelection(el("txAccount"), state.accounts, "id", (a) => a.name);
  renderPlatforms();
  renderAlerts();
  renderAccounts();
  renderPending();
  renderTransactions();

  el("totalAccounts").textContent = money(state.totals.efectivo_y_bancos);
  el("totalSales").textContent = money(state.totals.ventas_total);
  el("salesPaid").textContent = money(state.totals.ventas_cobradas);
  el("salesCredit").textContent = money(state.totals.ventas_credito);
  el("totalReceivables").textContent = money(state.totals.cuentas_por_cobrar);
  el("totalPayables").textContent = money(state.totals.deuda_distribuidores);
}

async function postJSON(url, body, method = "POST") {
  const res = await fetch(url, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: "Error desconocido" }));
    showError(typeof detail.detail === "string" ? detail.detail : JSON.stringify(detail.detail));
    throw new Error(detail.detail);
  }
  hideError();
  return res.json();
}

function showError(message) {
  const box = el("formError");
  box.textContent = message;
  box.classList.remove("d-none");
}

function hideError() {
  el("formError").classList.add("d-none");
}

function syncFormFields() {
  const kind = el("txKind").value;
  const status = el("txStatus").value;
  el("platformField").classList.toggle("d-none", kind === "egreso");
  el("txStatus").parentElement.classList.toggle("d-none", kind === "egreso");
  el("clientField").classList.toggle("d-none", !(kind === "venta" && status === "pendiente"));
  el("accountField").classList.toggle("d-none", kind !== "egreso" && status === "pendiente");
}

function connect() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  socket = new WebSocket(`${proto}://${location.host}/ws`);
  socket.onopen = () => {
    el("wsStatus").className = "badge text-bg-success";
    el("wsStatus").textContent = "En vivo";
  };
  socket.onmessage = (event) => render(JSON.parse(event.data).state);
  socket.onclose = () => {
    el("wsStatus").className = "badge text-bg-danger";
    el("wsStatus").textContent = "Desconectado · reintentando";
    setTimeout(connect, 2000);
  };
}

el("txForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const kind = el("txKind").value;
  const status = kind === "egreso" ? "pagada" : el("txStatus").value;
  const payload = {
    kind,
    amount: Number(el("txAmount").value),
    collaborator_id: Number(el("activeCollaborator").value),
    platform_id: kind === "egreso" ? null : Number(el("txPlatform").value),
    account_id: status === "pendiente" && kind !== "egreso" ? null : Number(el("txAccount").value),
    status,
    client_name: el("txClient").value || null,
    note: el("txNote").value || null,
  };
  try {
    await postJSON("/api/transactions", payload);
    el("txAmount").value = "";
    el("txClient").value = "";
    el("txNote").value = "";
  } catch (err) {
    /* error ya mostrado */
  }
});

el("txKind").addEventListener("change", syncFormFields);
el("txStatus").addEventListener("change", syncFormFields);

el("saveCollaborator").addEventListener("click", async () => {
  const name = el("newCollaborator").value.trim();
  if (!name) return;
  await postJSON("/api/collaborators", { name });
  el("newCollaborator").value = "";
  bootstrap.Modal.getOrCreateInstance(el("collaboratorModal")).hide();
});

el("saveThresholds").addEventListener("click", async () => {
  await postJSON(
    `/api/platforms/${el("thresholdPlatformId").value}/thresholds`,
    { min_balance: Number(el("minBalance").value), warning_balance: Number(el("warningBalance").value) },
    "PATCH"
  );
  bootstrap.Modal.getOrCreateInstance(el("thresholdModal")).hide();
});

el("soundToggle").addEventListener("click", () => {
  soundEnabled = !soundEnabled;
  el("soundToggle").textContent = `🔔 Sonido: ${soundEnabled ? "ON" : "OFF"}`;
});

el("reportDate").addEventListener("change", () => {
  const day = el("reportDate").value;
  el("exportCsv").href = day ? `/api/report/csv?day=${day}` : "/api/report/csv";
});

fetch("/api/state")
  .then((res) => res.json())
  .then(render)
  .finally(() => {
    syncFormFields();
    connect();
  });
