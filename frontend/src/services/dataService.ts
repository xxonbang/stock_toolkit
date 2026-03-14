const BASE_URL = import.meta.env.BASE_URL + "data/";

async function fetchJson<T>(path: string): Promise<T | null> {
  try {
    const res = await fetch(BASE_URL + path);
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export const dataService = {
  getPerformance: () => fetchJson<any>("performance.json"),
  getAnomalies: () => fetchJson<any[]>("anomalies.json"),
  getSmartMoney: () => fetchJson<any[]>("smart_money.json"),
  getSectorFlow: () => fetchJson<Record<string, any>>("sector_flow.json"),
  getNewsImpact: () => fetchJson<Record<string, any>>("news_impact.json"),
  getSimulation: () => fetchJson<any[]>("simulation.json"),
};
