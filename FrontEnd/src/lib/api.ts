const API_BASE = "http://localhost:8000";

export async function fetchMarketplaces() {
  const res = await fetch(`${API_BASE}/api/marketplaces`);
  if (!res.ok) throw new Error("Failed to fetch marketplaces");
  return res.json();
}