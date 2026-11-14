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

// 매수 주문

function buy(event) {
  event.preventDefault();
  // 주문을 저장할 곳이 아직 없다. 미니 DBMS를 붙이면 여기서 api.buy(selectedStock(), orderQuantity())를 부른다.
}

async function changePrice(event) {
  event.preventDefault();
  const stock = selectedStock();
  if (!stock) return;
  page.priceButton.disabled = true;
  try {
    await api.changePrice(stock.id, Number(page.newPrice.value));
    await loadRanking();
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
  } catch (error) {
    showError(error.message);
  }
}

async function logOut() {
  const token = rememberedToken();
  forgetToken();
  showLoggedOut();
  if (token) await api.logOut(token).catch(() => {});
}

async function restoreSession() {
  const token = rememberedToken();
  if (!token) return;
  try {
    const answer = await api.me(token);
    showLoggedIn(answer.user);
  } catch {
    forgetToken();
    showLoggedOut();
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

// 데모 API 호출. 데모 API는 "상품, 판매량"이라는 말을 쓰므로 여기서 "종목, 거래량"으로 바꿔 준다.
// 나중에 미니 DBMS를 붙일 때는 이 묶음만 바꾸면 된다.

const api = {
  ranking: async (useCache) => {
    const answer = await call("GET", `/products/popular${useCache ? "" : "?nocache=1"}`);
    return {
      server: answer.server,
      source: answer.source,
      elapsedMs: answer.elapsed_ms,
      stocks: answer.products.map(stockFromProduct),
    };
  },
  changePrice: (stockId, price) => call("PUT", `/products/${stockId}/price`, { price }),
  logIn: (user) => call("POST", "/login", { user }),
  logOut: (token) => call("POST", `/logout?token=${encodeURIComponent(token)}`),
  me: (token) => call("GET", `/me?token=${encodeURIComponent(token)}`),
  dbQueryCount: async () => (await call("GET", "/stats")).db_query_count,
  resetDbQueryCount: () => call("POST", "/stats/reset"),
  clearCache: () => call("DELETE", "/cache"),
};

// 데모 API의 원본 데이터는 상품 이름(키보드 등)이라서, 화면에서만 상품 id에 종목 이름을 붙인다.
const STOCK_NAME_BY_PRODUCT_ID = {
  1: "SW-AI",
  2: "게임 랩",
  3: "게임 테크 랩",
};

function stockFromProduct(product) {
  return {
    id: product.id,
    name: STOCK_NAME_BY_PRODUCT_ID[product.id] || product.name,
    price: product.price,
    volume: product.sales,
  };
}

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
