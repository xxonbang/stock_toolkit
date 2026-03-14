import { useEffect, useState } from "react";
import { dataService } from "../services/dataService";

export default function Dashboard() {
  const [performance, setPerformance] = useState<any>(null);
  const [sectors, setSectors] = useState<Record<string, any> | null>(null);
  const [anomalies, setAnomalies] = useState<any[] | null>(null);
  const [smartMoney, setSmartMoney] = useState<any[] | null>(null);

  useEffect(() => {
    dataService.getPerformance().then(setPerformance);
    dataService.getSectorFlow().then(setSectors);
    dataService.getAnomalies().then(setAnomalies);
    dataService.getSmartMoney().then(setSmartMoney);
  }, []);

  return (
    <div className="min-h-screen bg-gray-950 text-white p-4 max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">Stock Toolkit</h1>

      {/* 시장 국면 */}
      <section className="mb-6">
        <h2 className="text-lg font-semibold mb-2">시장 현황</h2>
        <div className="bg-gray-900 rounded-lg p-4">
          <span className="text-gray-400">현재 국면: </span>
          <span className="text-xl font-bold">{performance?.current_regime || "—"}</span>
        </div>
      </section>

      {/* 시스템 성과 */}
      {performance?.by_source && (
        <section className="mb-6">
          <h2 className="text-lg font-semibold mb-2">시스템 성과</h2>
          <div className="grid grid-cols-1 gap-2">
            {Object.entries(performance.by_source).map(([source, data]: [string, any]) => (
              <div key={source} className="bg-gray-900 rounded-lg p-3 flex justify-between">
                <span className="font-medium capitalize">{source}</span>
                <span className="text-gray-400">
                  평균 {data?.mean ?? "—"}% | 최대 {data?.max ?? "—"}%
                </span>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* 이상 거래 */}
      {anomalies && anomalies.length > 0 && (
        <section className="mb-6">
          <h2 className="text-lg font-semibold mb-2">이상 거래 감지</h2>
          {anomalies.slice(0, 5).map((a, i) => (
            <div key={i} className="bg-red-950 border border-red-800 rounded-lg p-3 mb-2">
              <span className="text-red-400 font-medium">{a.type}</span>
              {a.name && <span className="ml-2">{a.name}</span>}
              {a.ratio && <span className="text-gray-400 ml-2">×{a.ratio}</span>}
              {a.theme && <span className="text-gray-400 ml-2">{a.theme} {a.count}종목</span>}
            </div>
          ))}
        </section>
      )}

      {/* 스마트 머니 */}
      {smartMoney && smartMoney.length > 0 && (
        <section className="mb-6">
          <h2 className="text-lg font-semibold mb-2">스마트 머니 TOP</h2>
          {smartMoney.slice(0, 5).map((s, i) => (
            <div key={i} className="bg-gray-900 rounded-lg p-3 mb-2 flex justify-between">
              <span>{s.name} ({s.code})</span>
              <span className="text-yellow-400">스코어 {s.smart_money_score}</span>
            </div>
          ))}
        </section>
      )}

      {/* 섹터 흐름 */}
      {sectors && (
        <section className="mb-6">
          <h2 className="text-lg font-semibold mb-2">섹터 자금 흐름</h2>
          {Object.entries(sectors)
            .sort(([, a]: any, [, b]: any) => (b.total_foreign_net || 0) - (a.total_foreign_net || 0))
            .slice(0, 8)
            .map(([name, data]: [string, any]) => (
              <div key={name} className="flex justify-between bg-gray-900 rounded-lg p-2 mb-1">
                <span>{name} <span className="text-gray-500 text-sm">[{data.stock_count}]</span></span>
                <span className={data.total_foreign_net >= 0 ? "text-red-400" : "text-blue-400"}>
                  {data.total_foreign_net >= 0 ? "+" : ""}{data.total_foreign_net}억
                </span>
              </div>
            ))}
        </section>
      )}
    </div>
  );
}
