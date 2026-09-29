import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { errorMessage } from "../api/client";
import { useAuth } from "../auth/AuthContext";

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      await login(email, password);
      navigate("/");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="auth-shell">
      <div className="auth-card">
        <img src="/logo.jpg" alt="AETL — Auto ETL & Analysis" className="auth-logo" />
        <h1 className="page-title" style={{ textAlign: "center" }}>
          Welcome back
        </h1>
        <p className="page-subtitle" style={{ textAlign: "center" }}>
          Sign in to AutoETL to continue
        </p>

        {error && <div className="error-banner">{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="form-field">
            <label htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <div className="form-field">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          <button className="btn btn-primary" style={{ width: "100%", justifyContent: "center" }} disabled={submitting}>
            {submitting ? "Signing in…" : "Sign in"}
          </button>
        </form>

        <p style={{ fontSize: 13, color: "var(--text-muted)", textAlign: "center", marginTop: 16 }}>
          No account? <Link to="/register">Register</Link>
        </p>
      </div>
    </div>
  );
}
