import { NavLink, Outlet } from "react-router-dom";

import { useAuth } from "../store/auth";

const navItems = [
  ["/", "仪表盘"],
  ["/analytics", "经营分析"],
  ["/customers", "客户管理"],
  ["/followup-reminders", "跟进提醒"],
  ["/opportunities", "商机管理"],
  ["/products", "产品库"],
  ["/customer-classification", "客户分类/标签"],
  ["/quotations", "报价管理"],
  ["/orders", "订单管理"],
  ["/settings", "设置"],
] as const;

export function AppLayout() {
  const { user, logout } = useAuth();

  return (
    <div className="min-h-screen md:flex">
      <aside className="bg-slate-950 px-5 py-6 text-slate-100 md:w-60">
        <div className="mb-8">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-blue-300">Dalian StarLink</p>
          <h1 className="mt-2 text-xl font-bold">CRM</h1>
        </div>
        <nav className="flex gap-2 overflow-x-auto md:flex-col">
          {navItems.map(([to, label]) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) => `whitespace-nowrap rounded-lg px-3 py-2 text-sm ${isActive ? "bg-blue-600 text-white" : "text-slate-300 hover:bg-slate-800"}`}
            >
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="mt-8 border-t border-slate-800 pt-4 text-sm">
          <p className="font-medium">{user?.name}</p>
          <p className="text-slate-400">{user?.role}</p>
          <button onClick={logout} className="mt-3 text-blue-300 hover:text-white">退出登录</button>
        </div>
      </aside>
      <main className="min-w-0 flex-1 p-5 md:p-8"><Outlet /></main>
    </div>
  );
}
