import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { getAlibabaIntegrationStatus, receiveAlibabaInquiry } from "../services/crm";
import { useAuth } from "../store/auth";
import type { AlibabaInquiryResult, AlibabaIntegrationStatus } from "../types";

export function SettingsPage() {
  const { user } = useAuth();
  const [status, setStatus] = useState<AlibabaIntegrationStatus | null>(null);
  const [result, setResult] = useState<AlibabaInquiryResult | null>(null);
  const [testing, setTesting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    getAlibabaIntegrationStatus()
      .then(setStatus)
      .catch(() => setError("无法读取数据来源状态。"));
  }, []);

  async function simulateInquiry() {
    setTesting(true);
    setError("");
    setResult(null);
    const nonce = Date.now();
    try {
      const inquiry = await receiveAlibabaInquiry({
        company_name: `Alibaba Demo School ${nonce}`,
        contact_name: "Demo Buyer",
        country: "United States",
        email: `alibaba.demo.${nonce}@example.com`,
        whatsapp: "+1 202 555 0100",
        inquiry_content: "Please quote Montessori classroom materials for a new preschool.",
        interested_product: "Montessori materials and preschool furniture",
        source: "Alibaba",
      });
      setResult(inquiry);
    } catch {
      setError("模拟接收询盘失败，请确认后端服务和登录状态正常。");
    } finally {
      setTesting(false);
    }
  }

  return (
    <>
      <div><p className="text-sm text-slate-500">系统设置</p><h2 className="text-3xl font-bold">数据来源管理</h2></div>
      {error && <p className="mt-4 text-sm text-rose-600">{error}</p>}

      <section className="mt-6 max-w-3xl rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-orange-100 font-bold text-orange-700">A</div>
            <div><h3 className="font-bold">Alibaba 国际站</h3><p className="mt-1 text-sm text-slate-500">自动将国际站询盘写入 Lead 询盘池</p></div>
          </div>
          <span className={`rounded-full px-3 py-1 text-sm font-medium ${status?.connected ? "bg-emerald-100 text-emerald-700" : "bg-slate-100 text-slate-600"}`}>
            {status?.connected ? "已连接" : "未连接"}
          </span>
        </div>

        <div className="mt-5 rounded-lg bg-blue-50 p-4 text-sm text-blue-800">
          当前为模拟接入模式，尚未配置真实 Alibaba API。测试按钮会生成一条独立模拟询盘，并执行与未来正式回调相同的数据处理流程。
        </div>

        {user?.role !== "Viewer" && (
          <button disabled={testing} onClick={() => void simulateInquiry()} className="mt-5 rounded-lg bg-orange-600 px-4 py-2 font-semibold text-white disabled:opacity-60">
            {testing ? "模拟接收中…" : "测试接收阿里询盘"}
          </button>
        )}

        {result && (
          <div className="mt-5 rounded-lg bg-emerald-50 p-4 text-sm text-emerald-800">
            <p className="font-semibold">{result.created ? "已创建新的 Lead" : "检测到重复询盘，已返回现有 Lead"}</p>
            <p className="mt-1">Lead ID：{result.lead_id} · {result.lead.company_name}</p>
            <Link to={`/leads/${result.lead_id}`} className="mt-3 inline-block font-semibold underline">打开 Lead 详情</Link>
          </div>
        )}
      </section>
    </>
  );
}
