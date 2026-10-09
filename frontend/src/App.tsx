import { useCallback, useEffect, useState } from "react";
import { ApiError, getMe, logout } from "./api";
import AuthForm from "./AuthForm";
import FileVault from "./FileVault";

// sessionStorage keeps the token for this tab only and clears it when the tab closes
const TOKEN_KEY = "vault_token";

export default function App() {
  const [token, setToken] = useState<string | null>(() => sessionStorage.getItem(TOKEN_KEY));
  const [username, setUsername] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const clearSession = useCallback((message: string | null) => {
    sessionStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setUsername(null);
    setNotice(message);
  }, []);

  const handleLogin = (newToken: string) => {
    sessionStorage.setItem(TOKEN_KEY, newToken);
    setNotice(null);
    setToken(newToken);
  };

  const handleLogout = () => {
    // tell the backend so the logout lands in the audit log; the token is dropped either way
    if (token) logout(token).catch(() => undefined);
    clearSession(null);
  };

  const handleUnauthorized = useCallback(() => {
    clearSession("Your session expired. Please log in again.");
  }, [clearSession]);

  // on load (and after login) confirm the token is still valid and fetch who it belongs to
  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    getMe(token)
      .then((user) => {
        if (!cancelled) setUsername(user.username);
      })
      .catch((error) => {
        if (cancelled) return;
        if (error instanceof ApiError && error.status === 401) handleUnauthorized();
        else setNotice(error instanceof Error ? error.message : "Something went wrong");
      });
    return () => {
      cancelled = true;
    };
  }, [token, handleUnauthorized]);

  return (
    <div className="page">
      <header className="topbar">
        <h1>Secure File Vault</h1>
        {token && (
          <div className="topbar-user">
            {username && <span>{username}</span>}
            <button className="secondary" onClick={handleLogout}>
              Log out
            </button>
          </div>
        )}
      </header>

      {notice && <p className="banner error">{notice}</p>}

      {token ? <FileVault token={token} onUnauthorized={handleUnauthorized} /> : <AuthForm onLogin={handleLogin} />}
    </div>
  );
}
