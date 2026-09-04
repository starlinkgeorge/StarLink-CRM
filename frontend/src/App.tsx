import { BrowserRouter, Navigate, Route, Routes, useParams } from "react-router-dom";
import { AppLayout } from "./components/AppLayout";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { CustomerDetailPage } from "./pages/CustomerDetailPage";
import { CustomerArchivePage } from "./pages/CustomerArchivePage";
import { DashboardPage } from "./pages/DashboardPage";
import { BusinessAnalyticsPage } from "./pages/BusinessAnalyticsPage";
import { FollowupRemindersPage } from "./pages/FollowupRemindersPage";
import { LoginPage } from "./pages/LoginPage";
import { NewCustomerPage } from "./pages/NewCustomerPage";
import { OpportunitiesPage } from "./pages/OpportunitiesPage";
import { OpportunityDetailPage } from "./pages/OpportunityDetailPage";
import { ProductDetailPage } from "./pages/ProductDetailPage";
import { ProductsPage } from "./pages/ProductsPage";
import { QuotationDetailPage } from "./pages/QuotationDetailPage";
import { QuotationCreatePage } from "./pages/QuotationCreatePage";
import { QuotationsPage } from "./pages/QuotationsPage";
import { SettingsPage } from "./pages/SettingsPage";
import { OrdersPage } from "./pages/OrdersPage";
import { OrderDetailPage } from "./pages/OrderDetailPage";
import { MailCenterPage } from "./pages/MailCenterPage";
import { MailReaderPage } from "./pages/MailReaderPage";
import { AuthProvider } from "./store/auth";

function LegacyCustomerQuotationCreateRedirect() {
  const { customerId } = useParams();
  return <Navigate to={customerId ? `/customers/${customerId}` : "/quotations/new"} replace />;
}

export function App() {
  return <AuthProvider><BrowserRouter><Routes>
    <Route path="/login" element={<LoginPage />} />
    <Route element={<ProtectedRoute />}><Route element={<AppLayout />}>
      <Route path="/" element={<DashboardPage />} />
      <Route path="/analytics" element={<BusinessAnalyticsPage />} />
      <Route path="/followup-reminders" element={<FollowupRemindersPage />} />
      <Route path="/mail" element={<MailCenterPage />} />
      <Route path="/mail/messages/:messageId" element={<MailReaderPage />} />
      <Route path="/customers" element={<CustomerArchivePage />} /><Route path="/customers/new" element={<NewCustomerPage />} /><Route path="/customers/:customerId/quotations/new" element={<LegacyCustomerQuotationCreateRedirect />} /><Route path="/customers/:id" element={<CustomerDetailPage />} />
      <Route path="/opportunities" element={<OpportunitiesPage />} /><Route path="/opportunities/:id" element={<OpportunityDetailPage />} />
      <Route path="/products" element={<ProductsPage />} /><Route path="/products/:id" element={<ProductDetailPage />} />
      <Route path="/quotations" element={<QuotationsPage />} /><Route path="/quotations/new" element={<QuotationCreatePage />} /><Route path="/quotations/:id" element={<QuotationDetailPage />} />
      <Route path="/orders" element={<OrdersPage />} /><Route path="/orders/new" element={<OrdersPage />} /><Route path="/orders/:id" element={<OrderDetailPage />} />
      <Route path="/settings" element={<SettingsPage />} />
    </Route></Route>
    <Route path="*" element={<Navigate to="/" replace />} />
  </Routes></BrowserRouter></AuthProvider>;
}
