let currentRun = null;
let providerStatus = null;
let keywordSort = { key: "opportunity_score", direction: -1 };
let listingPage = 1;
const listingPageSize = 50;
const $ = selector => document.querySelector(selector);
const esc = value => String(value ?? "").replace(/[&<>"']/g, character => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
}[character]));

async function init() {
  providerStatus = await fetch("/api/etsy-research/provider-status").then(response => response.json());
  $("#provider").innerHTML = `<strong>${providerStatus.live_configured ? "Live provider ready" : "Fixture mode ready"}</strong><br><small>${providerStatus.live_configured ? "Omkar key configured" : "Add OMKAR_API_KEY for live data"}</small>`;
  $("#mock").checked = !providerStatus.live_configured;
  $("#presets").innerHTML = providerStatus.presets.map(value => `<button type="button" class="chip">${esc(value)}</button>`).join("");
  document.querySelectorAll(".chip").forEach(button => button.onclick = () => { $("#seeds").value = button.textContent; estimate(); });
  $("#miDate").value = new Date().toISOString().slice(0, 10);
  bindTables();
  estimate();
}

function seeds() { return $("#seeds").value.split(/[\n,]+/).map(value => value.trim()).filter(Boolean); }
function estimate() {
  const keys = Math.min(10, Math.max(1, +$("#maxKeywords").value || 1));
  const details = { search_only: 0, top_10: 10, top_20: 20 }[$("#mode").value];
  const detailBudget = Math.min(details, providerStatus?.max_details || 20);
  $("#estimate").textContent = `Estimated API calls: ${$("#mock").checked ? 0 : keys + detailBudget}`;
}

["maxKeywords", "mode", "mock"].forEach(id => document.addEventListener("change", event => { if (event.target.id === id) estimate(); }));

$("#researchForm").onsubmit = async event => {
  event.preventDefault();
  $("#formError").textContent = "";
  $("#progressPanel").classList.remove("hidden");
  $("#results").classList.add("hidden");
  renderProgress({ keywords_total: +$("#maxKeywords").value, keywords_processed: 0, searches_completed: 0, details_fetched: 0, cache_hits: 0, api_calls_made: 0, errors: [] });
  const payload = {
    seed_keywords: seeds(), target_marketplace: $("#market").value, product_type: $("#productType").value,
    digital_only: $("#digitalOnly").checked, min_price: num("#minPrice"), max_price: num("#maxPrice"),
    listings_to_analyze: +$("#listingLimit").value, enrichment_mode: $("#mode").value,
    customer_or_style: $("#style").value || null, negative_keywords: $("#negatives").value.split(",").map(value => value.trim()).filter(Boolean),
    include_generated_keywords: $("#generated").checked, max_keywords: +$("#maxKeywords").value, use_mock: $("#mock").checked,
    score_weights: Object.fromEntries([...document.querySelectorAll(".score-weight")].map(input => [input.dataset.weight, +input.value]))
  };
  try {
    const response = await fetch("/api/etsy-research/runs", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    if (!response.ok) throw new Error((await response.json()).detail || "Research failed");
    currentRun = await response.json();
    listingPage = 1;
    render(currentRun);
  } catch (error) {
    $("#formError").textContent = error.message;
    $("#runStatus").textContent = "Failed";
  }
};

function num(id) { const value = $(id).value; return value === "" ? null : +value; }
function renderProgress(progress) {
  $("#progress").innerHTML = [["Keywords", `${progress.keywords_processed}/${progress.keywords_total}`], ["Searches", progress.searches_completed], ["Details", progress.details_fetched], ["Cache hits", progress.cache_hits], ["API calls", progress.api_calls_made], ["Errors", progress.errors?.length || 0]]
    .map(([label, value]) => `<div class="metric"><strong>${value}</strong><span>${label}</span></div>`).join("");
}

function render(data) {
  renderProgress(data.run.progress);
  $("#runStatus").textContent = data.run.status;
  $("#results").classList.remove("hidden");
  const best = [...data.keywords].sort((left, right) => (right.opportunity_score || 0) - (left.opportunity_score || 0))[0];
  $("#summary").innerHTML = [["Provider", data.run.summary?.provider], ["Unique listings", data.run.summary?.unique_listings], ["Keywords", data.keywords.length], ["Top opportunity", best?.keyword], ["Opportunity score", best?.opportunity_score], ["Evidence score", best?.evidence_score]]
    .map(([label, value]) => `<div class="summary-card"><strong>${esc(value ?? "-")}</strong><span>${label}</span></div>`).join("");
  renderKeywords(data.keywords); renderListings(data.listings); renderClusters(data.clusters); renderRecommendations(data.recommendations); renderSignals(best?.metrics || {});
}

function metricValue(row, key) {
  const metrics = row.metrics || {}, insight = metrics.marketplace_insight || {};
  const values = { keyword: row.keyword, source: row.source, observed_result_count: row.observed_result_count, digital_percentage: metrics.digital_percentage, median_price: metrics.median_price, median_favorites: metrics.median_favorites, bestseller_percentage: metrics.bestseller_percentage, marketplace_searches: insight.searches_last_30_days, marketplace_listings: insight.listings_last_30_days, evidence_score: row.evidence_score, opportunity_score: row.opportunity_score, created_at: row.created_at };
  return values[key];
}

function renderKeywords(rows) {
  const query = ($("#tableSearch").value || "").toLowerCase();
  const sorted = rows.filter(row => row.keyword.toLowerCase().includes(query)).sort((left, right) => {
    const a = metricValue(left, keywordSort.key), b = metricValue(right, keywordSort.key);
    return (typeof a === "string" ? a.localeCompare(b || "") : (a ?? -Infinity) - (b ?? -Infinity)) * keywordSort.direction;
  });
  $("#keywordTable tbody").innerHTML = sorted.map(row => {
    const metrics = row.metrics || {}, insight = metrics.marketplace_insight || {};
    const calculation = (metrics.score_calculation || []).map(item => `${item.component}: ${item.value} x ${item.weight}% = ${item.contribution}`).join("; ");
    return `<tr><td><strong>${esc(row.keyword)}</strong><br><small>${esc(metrics.score_warning || "Verified Marketplace Insights included")}</small></td><td><span class="badge ${row.source.includes("Generated") ? "calculated" : "observed"}">${esc(row.source)}</span></td><td>${row.observed_result_count ?? "-"}</td><td>${fmt(metrics.digital_percentage, "%")}</td><td>${money(metrics.median_price)}</td><td>${metrics.median_favorites ?? "-"}</td><td>${fmt(metrics.bestseller_percentage, "%")}</td><td>${insight.searches_last_30_days ?? "-"}</td><td>${insight.listings_last_30_days ?? "-"}</td><td>${row.evidence_score ?? "-"}</td><td><strong>${row.opportunity_score ?? "-"}</strong><br><small>${esc(row.score_label || "")}</small><details><summary>Calculation</summary><small>${esc(calculation)}</small></details></td><td>${confidence(row.evidence_score)}</td><td>${shortDate(row.created_at)}</td></tr>`;
  }).join("");
}

function bindTables() {
  const keys = ["keyword", "source", "observed_result_count", "digital_percentage", "median_price", "median_favorites", "bestseller_percentage", "marketplace_searches", "marketplace_listings", "evidence_score", "opportunity_score", null, "created_at"];
  document.querySelectorAll("#keywordTable th").forEach((header, index) => header.onclick = () => {
    const key = keys[index]; if (!key) return;
    keywordSort = { key, direction: keywordSort.key === key ? keywordSort.direction * -1 : -1 };
    if (currentRun) renderKeywords(currentRun.keywords);
  });
  $("#toggleColumns").onclick = () => document.querySelectorAll("#keywordTable tr").forEach(row => [...row.children].slice(7, 10).forEach(cell => cell.classList.toggle("hidden-col")));
}

$("#tableSearch").oninput = () => currentRun && renderKeywords(currentRun.keywords);
function renderListings(rows) {
  const pageCount = Math.max(1, Math.ceil(rows.length / listingPageSize));
  listingPage = Math.min(pageCount, Math.max(1, listingPage));
  const pageRows = rows.slice((listingPage - 1) * listingPageSize, listingPage * listingPageSize);
  $("#listingTable tbody").innerHTML = pageRows.map(row => `<tr><td>${safeUrl(row.url) ? `<a target="_blank" rel="noopener" href="${esc(row.url)}">${esc(row.title)}</a>` : esc(row.title)}</td><td>${esc(row.shop_name || "Unknown")}</td><td>${money(row.price_usd ?? row.price)}</td><td>${row.favorites_count ?? "Unavailable"}</td><td><span class="badge ${row.digital_classification_source === "ConfirmedProviderFlag" ? "observed" : "calculated"}">${esc(row.digital_classification_source)}</span></td><td>${row.is_bestseller ? "Bestseller " : ""}${row.is_top_rated ? "Top rated" : ""}</td></tr>`).join("");
  $("#listingPage").textContent = `Page ${listingPage} of ${pageCount}`;
  $("#listingPrev").disabled = listingPage <= 1; $("#listingNext").disabled = listingPage >= pageCount;
}
$("#listingPrev").onclick = () => { if (currentRun) { listingPage--; renderListings(currentRun.listings); } };
$("#listingNext").onclick = () => { if (currentRun) { listingPage++; renderListings(currentRun.listings); } };

function renderClusters(rows) { $("#clusters").innerHTML = rows.map(row => `<div class="card"><h3>${esc(row.name)}</h3><p>${esc(row.dimension)} - ${row.keywords?.length || 0} keywords - ${row.listing_ids?.length || 0} source listings</p><div class="tags">${(row.keywords || []).slice(0, 5).map(tag => `<span class="tag">${esc(tag)}</span>`).join("")}</div></div>`).join("") || "<p>No deterministic clusters found in this sample.</p>"; }
function renderRecommendations(rows) { $("#recommendations").innerHTML = rows.map(row => `<article class="recommendation"><div><span class="score">${row.opportunity_score ?? "-"}</span><span class="badge ${row.source_type === "AI recommendation" ? "ai" : "calculated"}">${esc(row.source_type || "Rule-based inference")}</span></div><h3>${esc(row.niche_name || "AI product recommendation")}</h3><p><strong>Product:</strong> ${esc(row.recommended_digital_product || row.product)}</p><p><strong>Buyer:</strong> ${esc(row.target_buyer)}</p><p><strong>Suggested price:</strong> ${esc(row.suggested_price_range)}</p><p><strong>Evidence:</strong> ${esc(row.demand_evidence)}</p><p><strong>Differentiation:</strong> ${esc(row.differentiation_strategy)}</p><p><strong>Suggested title:</strong> ${esc(row.suggested_etsy_title)}</p><div class="tags">${(row.suggested_etsy_tags || []).map(tag => `<span class="tag">${esc(tag)}</span>`).join("")}</div><details><summary>Evidence trace, assumptions, and risks</summary><p>Source keywords: ${esc((row.source_keywords || []).join(", "))}</p><p>Source listing IDs: ${esc((row.source_listing_ids || []).join(", "))}</p><p>Assumption: observed marketplace signals may indicate engagement or supply but do not establish sales or verified search demand.</p><p>Risks: ${esc((row.risks || []).join("; "))}</p></details></article>`).join(""); }
function chips(rows) { return (rows || []).map(([value, count]) => `<span class="tag">${esc(value)} - ${count}</span>`).join(""); }
function renderSignals(metrics) { $("#signals").innerHTML = `<h3>Frequent title phrases</h3><div class="tags">${chips(metrics.frequent_title_phrases)}</div><h3>Frequent tags</h3><div class="tags">${chips(metrics.frequent_tags)}</div><h3>Styles, colors, subjects & occasions</h3><div class="tags">${chips([...(metrics.common_styles || []), ...(metrics.common_colors || []), ...(metrics.common_subjects || []), ...(metrics.common_holidays || []), ...(metrics.common_occasions || [])])}</div><h3>Price distribution</h3>${(metrics.price_distribution || []).map(bucket => `<p>${esc(bucket.label)} <strong>${bucket.count}</strong></p>`).join("")}<h3>Dominant shops</h3>${(metrics.dominant_shops || []).map(([shop, count]) => `<p>${esc(shop)} <strong>${count}</strong></p>`).join("")}<h3>Title similarity</h3><p>Exact duplicates: <strong>${fmt(metrics.duplicate_title_percentage, "%")}</strong>; near-duplicate pairs: <strong>${fmt(metrics.near_duplicate_title_pair_percentage, "%")}</strong>.</p><p>Seller concentration is a supply signal, not proof of demand.</p>`; }

$("#exportBtn").onclick = () => currentRun && (location.href = `/api/etsy-research/export/${currentRun.run.id}`);
$("#saveInsight").onclick = async () => { const payload = { keyword: $("#miKeyword").value, searches_last_30_days: +$("#miSearches").value, listings_last_30_days: +$("#miListings").value, captured_at: $("#miDate").value }; const response = await fetch("/api/etsy-research/marketplace-insights", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }); $("#importResult").textContent = response.ok ? "Manual insight saved. Re-run research to include it." : (await response.json()).detail; };
$("#csvFile").onchange = async event => { const text = await event.target.files[0].text(), response = await fetch("/api/etsy-research/marketplace-insights/import", { method: "POST", headers: { "Content-Type": "text/csv" }, body: text }), data = await response.json(); $("#importResult").textContent = response.ok ? `Imported ${data.imported}; ${data.errors.length} invalid rows reported.` : data.detail; };
function safeUrl(value) { try { return ["http:", "https:"].includes(new URL(value).protocol); } catch { return false; } }
function fmt(value, suffix = "") { return value == null ? "-" : `${value}${suffix}`; }
function money(value) { return value == null ? "-" : `$${(+value).toFixed(2)}`; }
function confidence(value) { return value >= 70 ? "High" : value >= 40 ? "Moderate" : "Low"; }
function shortDate(value) { return value ? new Date(value).toLocaleDateString() : "-"; }
init();
