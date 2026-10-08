import { useState, type FormEvent } from "react";
import { login, register } from "./api";

interface Props {
  onLogin: (token: string) => void;
}

export default function AuthForm({ onLogin }: Props) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const switchMode = (next: "login" | "register") => {
    setMode(next);
    setError(null);
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      // registering doesn't return a token, so log in straight after
      if (mode === "register") await register(username, email, password);
      onLogin(await login(username, password));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="card auth">
      <div className="tabs" role="tablist">
        <button role="tab" aria-selected={mode === "login"} onClick={() => switchMode("login")}>
          Log in
        </button>
        <button role="tab" aria-selected={mode === "register"} onClick={() => switchMode("register")}>
          Register
        </button>
      </div>

      <form onSubmit={handleSubmit}>
        <label>
          Username
          <input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" required />
        </label>

        {mode === "register" && (
          <label>
            Email
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" required />
          </label>
        )}

        <label>
          Password
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete={mode === "login" ? "current-password" : "new-password"}
            required
          />
        </label>

        {error && <p className="banner error">{error}</p>}

        <button type="submit" disabled={submitting}>
          {submitting ? "Please wait…" : mode === "login" ? "Log in" : "Create account"}
        </button>
      </form>
    </main>
  );
}
