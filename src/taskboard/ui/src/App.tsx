import { useEffect, useState } from "react";
import { api, Me, Task } from "./api";

export function App() {
  const [me, setMe] = useState<Me | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [newTitle, setNewTitle] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    try {
      const [m, ts] = await Promise.all([api.me(), api.list()]);
      setMe(m);
      setTasks(ts);
      setError(null);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  async function add() {
    const title = newTitle.trim();
    if (!title) return;
    const t = await api.create(title);
    setTasks((prev) => [t, ...prev]);
    setNewTitle("");
  }

  async function toggle(t: Task) {
    const updated = await api.patch(t.id, { done: !t.done });
    setTasks((prev) => prev.map((x) => (x.id === t.id ? updated : x)));
  }

  async function remove(t: Task) {
    await api.remove(t.id);
    setTasks((prev) => prev.filter((x) => x.id !== t.id));
  }

  if (loading) return <main className="container"><p>Loading…</p></main>;

  return (
    <main className="container">
      <header className="header">
        <h1>Taskboard</h1>
        {me && (
          <div className="user">
            <span>Hi, {me.name || me.email || me.sub}</span>
            <button onClick={async () => { await api.logout(); window.location.href = "/auth/login"; }}>
              Log out
            </button>
          </div>
        )}
      </header>

      {error && <p className="error">{error}</p>}

      <form
        className="new-task"
        onSubmit={(e) => {
          e.preventDefault();
          void add();
        }}
      >
        <input
          value={newTitle}
          onChange={(e) => setNewTitle(e.target.value)}
          placeholder="What needs doing?"
          autoFocus
        />
        <button type="submit" disabled={!newTitle.trim()}>Add</button>
      </form>

      <ul className="tasks">
        {tasks.length === 0 && <li className="empty">No tasks yet.</li>}
        {tasks.map((t) => (
          <li key={t.id} className={t.done ? "task done" : "task"}>
            <label>
              <input type="checkbox" checked={t.done} onChange={() => void toggle(t)} />
              <span>{t.title}</span>
            </label>
            <button className="del" onClick={() => void remove(t)} aria-label="Delete">
              ×
            </button>
          </li>
        ))}
      </ul>

      <footer className="footer">
        <small>Authenticated via Keycloak · Served by FastAPI BFF · mTLS via Istio</small>
      </footer>
    </main>
  );
}
