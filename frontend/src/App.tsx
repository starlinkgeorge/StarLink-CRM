import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AppLayout } from "./components/AppLayout";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { CustomerDetailPage } from "./pages/CustomerDetailPage";
import { CustomersPage } from "./pages/CustomersPage";
import { DashboardPage } from "./pages/DashboardPage";
import { LoginPage } from "./pages/LoginPage";
import { LeadDetailPage } from "./pages/LeadDetailPage";
import { LeadsPage } from "./pages/LeadsPage";
import { NewCustomerPage } from "./pages/NewCustomerPage";
import { SettingsPage } from "./pages/SettingsPage";
import { AuthProvider } from "./store/auth";

export function App() {
  return <AuthProvider><BrowserRouter><Routes><Route path="/login" element={<LoginPage />} /><Route element={<ProtectedRoute />}><Route element={<AppLayout />}><Route path="/" element={<DashboardPage />} /><Route path="/leads" element={<LeadsPage />} /><Route path="/leads/:id" element={<LeadDetailPage />} /><Route path="/customers" element={<CustomersPage />} /><Route path="/customers/new" element={<NewCustomerPage />} /><Route path="/customers/:id" element={<CustomerDetailPage />} /><Route path="/settings" element={<SettingsPage />} /></Route></Route><Route path="*" element={<Navigate to="/" replace />} /></Routes></BrowserRouter></AuthProvider>;
}
