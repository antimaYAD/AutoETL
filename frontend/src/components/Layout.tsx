import { NavLink, Outlet, useNavigate } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <>
      <header className="navbar">
        <NavLink to="/" className="navbar-brand">
          <span
            style={{
              width: 28,
              height: 28,
              borderRadius: 8,
              background: "var(--gradient)",
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#fff",
              fontSize: 15,
              WebkitTextFillColor: "#fff",
            }}
          >
            ⛁
          </span>
          AutoETL
        </NavLink>
        <nav className="navbar-nav">
          <NavLink to="/" end>
            Datasets
          </NavLink>
        </nav>
        {user && (
          <>
            <span className="navbar-user">{user.email}</span>
            <button className="btn" onClick={handleLogout}>
              Log out
            </button>
          </>
        )}
      </header>
      <main className="page">
        <Outlet />
      </main>
    </>
  );
}
