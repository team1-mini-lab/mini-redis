const SESSION_TOKEN_STORAGE_KEY = "mini-stock-session-token";

const page = {
  loginForm: document.getElementById("login-form"),
  loggedIn: document.getElementById("logged-in"),
  loggedInUser: document.getElementById("logged-in-user"),
  logoutButton: document.getElementById("logout-button"),
  useCache: document.getElementById("use-cache"),
  reloadButton: document.getElementById("reload-button"),
  responseInfo: document.getElementById("response-info"),
  rankingRows: document.getElementById("ranking-rows"),
  rankingRow: document.getElementById("ranking-row"),
  orderStock: document.getElementById("order-stock"),
  orderPrice: document.getElementById("order-price"),
  orderForm: document.getElementById("order-form"),
  orderQuantity: document.getElementById("order-quantity"),
  orderTotal: document.getElementById("order-total"),
  buyButton: document.getElementById("buy-button"),
  priceForm: document.getElementById("price-form"),
  newPrice: document.getElementById("new-price"),
  priceButton: document.getElementById("price-button"),
  factServer: document.getElementById("fact-server"),
  factSource: document.getElementById("fact-source"),
  factElapsed: document.getElementById("fact-elapsed"),
  factDbQueries: document.getElementById("fact-db-queries"),
  clearCacheButton: document.getElementById("clear-cache-button"),
  resetStatsButton: document.getElementById("reset-stats-button"),
  accountEmpty: document.getElementById("account-empty"),
  accountBody: document.getElementById("account-body"),
  accountCash: document.getElementById("account-cash"),
  accountValue: document.getElementById("account-value"),
  accountStartingCash: document.getElementById("account-starting-cash"),
  holdingRows: document.getElementById("holding-rows"),
  holdingRow: document.getElementById("holding-row"),
  orderRows: document.getElementById("order-rows"),
  orderRow: document.getElementById("order-row"),
  emptyRow: document.getElementById("empty-row"),
};

let stocks = [];
let selectedStockId = null;

function startPage() {
  connectButtons();
  restoreSession();
  loadRanking();
}

function connectButtons() {
  page.loginForm.addEventListener("submit", logIn);
  page.logoutButton.addEventListener("click", logOut);
  page.reloadButton.addEventListener("click", loadRanking);
  page.useCache.addEventListener("change", loadRanking);
  page.orderQuantity.addEventListener("input", showOrderTotal);
  page.orderForm.addEventListener("submit", buy);
  page.priceForm.addEventListener("submit", changePrice);
  page.clearCacheButton.addEventListener("click", clearCache);
  page.resetStatsButton.addEventListener("click", resetDbQueryCount);
}

// 거래량 상위 종목

async function loadRanking() {
  showLoading();
  try {
    const answer = await api.ranking(page.useCache.checked);
    stocks = answer.stocks;
    showRanking();
    showOrderPanel();
    showResponseFacts(answer);
  } catch (error) {
    showError(error.message);
  } finally {
    page.reloadButton.disabled = false;
    await showDbQueryCount();
  }
}

function selectStock(stockId) {
  selectedStockId = stockId;
  showRanking();
  showOrderPanel();
}

function selectedStock() {
  return stocks.find((stock) => stock.id === selectedStockId) || null;
}

// 매수 주문 (미니 DBMS에 저장)

async function buy(event) {
  event.preventDefault();
  const stock = selectedStock();
  const token = rememberedToken();
  if (!stock) return;
  if (!token) {
    showError("로그인하고 매수하세요.");
    return;
  }
  page.buyButton.disabled = true;
  try {
    const answer = await api.buy(token, stock.id, orderQuantity());
    showResponseFacts(answer);
    page.responseInfo.dataset.speed = "";
    page.responseInfo.textContent =
      `${answer.order.stock_name} ${answer.order.quantity.toLocaleString("ko-KR")}주를 ${won(answer.order.price)}에 샀어요.`;
    await loadAccount();
  } catch (error) {
    showError(error.message);
  } finally {
    page.buyButton.disabled = !selectedStock();
  }
}

// 내 계좌 (잔고, 보유 종목, 체결 내역)

async function loadAccount() {
  const token = rememberedToken();
  if (!token) {
    showAccountLoggedOut();
    return;
  }
  try {
    showAccount(await api.account(token));
  } catch (error) {
    showAccountMessage(error.message);
  }
}

async function changePrice(event) {
  event.preventDefault();
  const stock = selectedStock();
  if (!stock) return;
  page.priceButton.disabled = true;
  try {
    await api.changePrice(stock.id, Number(page.newPrice.value));
    await loadRanking();
    await loadAccount();   // 보유 종목의 현재가와 평가 금액이 바뀐다
  } catch (error) {
    showError(error.message);
  } finally {
    page.priceButton.disabled = false;
  }
}

function orderQuantity() {
  return Math.max(0, Math.floor(Number(page.orderQuantity.value) || 0));
}

// 캐시와 통계

async function clearCache() {
  await api.clearCache();
  page.responseInfo.dataset.speed = "";
  page.responseInfo.textContent = "캐시를 비웠어요. 다음 조회는 DB에서 가져와요.";
}

async function resetDbQueryCount() {
  await api.resetDbQueryCount();
  await showDbQueryCount();
}

// 로그인

async function logIn(event) {
  event.preventDefault();
  try {
    const answer = await api.logIn(page.loginForm.elements.user.value.trim());
    rememberToken(answer.token);
    showLoggedIn(answer.user);
    await loadAccount();
  } catch (error) {
    showError(error.message);
  }
}

async function logOut() {
  const token = rememberedToken();
  forgetToken();
  showLoggedOut();
  showAccountLoggedOut();
  if (token) await api.logOut(token).catch(() => {});
}

async function restoreSession() {
  const token = rememberedToken();
  if (!token) return;
  try {
    const answer = await api.me(token);
    showLoggedIn(answer.user);
    await loadAccount();
  } catch {
    forgetToken();
    showLoggedOut();
    showAccountLoggedOut();
  }
}

function rememberedToken() {
  try { return localStorage.getItem(SESSION_TOKEN_STORAGE_KEY); } catch { return null; }
}

function rememberToken(token) {
  try { localStorage.setItem(SESSION_TOKEN_STORAGE_KEY, token); } catch {}
}

function forgetToken() {
  try { localStorage.removeItem(SESSION_TOKEN_STORAGE_KEY); } catch {}
}

// 화면 그리기

function showLoading() {
  page.reloadButton.disabled = true;
  page.responseInfo.dataset.speed = "";
  page.responseInfo.textContent = "불러오는 중";
}

function showRanking() {
  page.rankingRows.replaceChildren(...stocks.map(rankingRow));
}

function rankingRow(stock, index) {
  const row = page.rankingRow.content.firstElementChild.cloneNode(true);
  row.setAttribute("aria-selected", String(stock.id === selectedStockId));
  row.querySelector(".rank").textContent = index + 1;
  row.querySelector(".stock-price").textContent = won(stock.price);
  row.querySelector(".stock-volume").textContent = stock.volume.toLocaleString("ko-KR");
  const nameButton = row.querySelector(".stock-name");
  nameButton.textContent = stock.name;
  nameButton.addEventListener("click", () => selectStock(stock.id));
  return row;
}

function showOrderPanel() {
  const stock = selectedStock();
  page.buyButton.disabled = !stock;
  page.newPrice.disabled = !stock;
  page.priceButton.disabled = !stock;
  page.orderStock.textContent = stock ? stock.name : "종목을 선택하세요";
  page.orderPrice.textContent = stock ? won(stock.price) : "-";
  if (stock) page.newPrice.value = stock.price;
  showOrderTotal();
}

function showOrderTotal() {
  const stock = selectedStock();
  page.orderTotal.textContent = stock ? won(stock.price * orderQuantity()) : "-";
}

function showResponseFacts(answer) {
  page.responseInfo.textContent = "";
  page.factServer.textContent = answer.server;
  page.factSource.textContent = answer.source;
  page.factElapsed.textContent = milliseconds(answer.elapsedMs);
}

async function showDbQueryCount() {
  try {
    page.factDbQueries.textContent = `${await api.dbQueryCount()}번`;
  } catch {
    page.factDbQueries.textContent = "-";
  }
}

function showLoggedIn(user) {
  page.loggedInUser.textContent = `${user} 님`;
  page.loginForm.hidden = true;
  page.loggedIn.hidden = false;
}

function showLoggedOut() {
  page.loginForm.hidden = false;
  page.loggedIn.hidden = true;
}

function showAccount(account) {
  const stockValue = account.holdings.reduce((sum, holding) => sum + holding.value, 0);
  page.accountCash.textContent = won(account.cash);
  page.accountValue.textContent = won(stockValue);
  page.accountStartingCash.textContent = won(account.starting_cash);
  page.holdingRows.replaceChildren(
    ...(account.holdings.length ? account.holdings.map(holdingRow) : [emptyRow("아직 산 종목이 없어요")]),
  );
  page.orderRows.replaceChildren(
    ...(account.orders.length ? account.orders.map(orderRow) : [emptyRow("아직 체결된 주문이 없어요")]),
  );
  page.accountEmpty.hidden = true;
  page.accountBody.hidden = false;
}

function holdingRow(holding) {
  const row = page.holdingRow.content.firstElementChild.cloneNode(true);
  row.querySelector(".holding-name").textContent = holding.stock_name;
  row.querySelector(".holding-quantity").textContent = `${holding.quantity.toLocaleString("ko-KR")}주`;
  row.querySelector(".holding-average").textContent = won(holding.average_price);
  row.querySelector(".holding-price").textContent = won(holding.current_price);
  row.querySelector(".holding-value").textContent = won(holding.value);
  return row;
}

function orderRow(order) {
  const row = page.orderRow.content.firstElementChild.cloneNode(true);
  row.querySelector(".fill-time").textContent = new Date(order.ordered_at * 1000).toLocaleString("ko-KR");
  row.querySelector(".fill-name").textContent = order.stock_name;
  row.querySelector(".fill-quantity").textContent = `${order.quantity.toLocaleString("ko-KR")}주`;
  row.querySelector(".fill-price").textContent = won(order.price);
  row.querySelector(".fill-amount").textContent = won(order.price * order.quantity);
  return row;
}

function emptyRow(message) {
  const row = page.emptyRow.content.firstElementChild.cloneNode(true);
  row.querySelector(".empty").textContent = message;
  return row;
}

function showAccountLoggedOut() {
  showAccountMessage("로그인하면 잔고와 체결 내역이 보여요.");
}

function showAccountMessage(message) {
  page.accountEmpty.textContent = message;
  page.accountEmpty.hidden = false;
  page.accountBody.hidden = true;
}

function showError(message) {
  page.responseInfo.dataset.speed = "error";
  page.responseInfo.textContent = message;
}

function won(price) {
  return `${price.toLocaleString("ko-KR")}원`;
}

function milliseconds(elapsedMs) {
  return `${Math.round(elapsedMs).toLocaleString("ko-KR")}ms`;
}

// 데모 API 호출. 매수와 계좌 조회는 데모 API가 미니 DBMS에 SQL을 보내 처리한다.

const api = {
  ranking: async (useCache) => {
    const answer = await call("GET", `/stocks/top${useCache ? "" : "?nocache=1"}`);
    return {
      server: answer.server,
      source: answer.source,
      elapsedMs: answer.elapsed_ms,
      stocks: answer.stocks,
    };
  },
  changePrice: (stockId, price) => call("PUT", `/stocks/${stockId}/price`, { price }),
  logIn: (user) => call("POST", "/login", { user }),
  logOut: (token) => call("POST", `/logout?token=${encodeURIComponent(token)}`),
  me: (token) => call("GET", `/me?token=${encodeURIComponent(token)}`),
  dbQueryCount: async () => (await call("GET", "/stats")).db_query_count,
  resetDbQueryCount: () => call("POST", "/stats/reset"),
  clearCache: () => call("DELETE", "/cache"),
  buy: async (token, stockId, quantity) => {
    const answer = await call("POST", `/orders?token=${encodeURIComponent(token)}`, { stock_id: stockId, quantity });
    return { ...answer, elapsedMs: answer.elapsed_ms };
  },
  account: (token) => call("GET", `/account?token=${encodeURIComponent(token)}`),
};

async function call(method, path, body) {
  const response = await fetch(`/api${path}`, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  const answer = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(answer.error || `요청이 실패했어요 (${response.status})`);
  return answer;
}

startPage();
