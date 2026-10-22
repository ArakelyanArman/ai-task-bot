import { updateTaskStatus } from "./api";
import { useTasks } from "./useTasks";
import "./styles.css";

const columns = [
  { status: "pending", label: "Pending" },
  { status: "in_progress", label: "In Progress" },
  { status: "completed", label: "Completed" },
];

const TaskCard = ({ task }) => {
  const columnIndex = columns.findIndex((column) => column.status === task.status);
  const move = async (status) => {
    await updateTaskStatus(task.id, status);
  };

  return (
    <article className="task-card">
      <div className="task-heading">
        <span className="source-icon" title={task.source}>
          {task.source === "voice" ? "🎙" : "⌨️"}
        </span>
        <h3>{task.title}</h3>
      </div>
      {task.transcription_status === "processing" && (
        <p className="transcribing"><span className="spinner" /> Transcribing…</p>
      )}
      {task.error_message && <p className="error-message">{task.error_message}</p>}
      {task.description && <p className="description">{task.description}</p>}
      <time dateTime={task.created_at}>
        {new Date(task.created_at).toLocaleString()}
      </time>
      <div className="task-actions">
        <button
          disabled={columnIndex <= 0}
          onClick={() => void move(columns[columnIndex - 1].status)}
        >
          ←
        </button>
        <button
          disabled={columnIndex === columns.length - 1}
          onClick={() => void move(columns[columnIndex + 1].status)}
        >
          →
        </button>
      </div>
    </article>
  );
};

const App = () => {
  const { tasks, error } = useTasks();

  return (
    <main className="app-shell">
      <header>
        <p className="eyebrow">AI TASK BOT</p>
        <h1>Your tasks, at a glance.</h1>
        <p className="subtitle">Create tasks from Telegram and manage them here.</p>
      </header>
      {error && <p className="global-error">{error}</p>}
      <section className="board">
        {columns.map((column) => (
          <div className="column" key={column.status}>
            <div className="column-heading">
              <h2>{column.label}</h2>
              <span>{tasks.filter((task) => task.status === column.status).length}</span>
            </div>
            {tasks
              .filter((task) => task.status === column.status)
              .map((task) => <TaskCard key={task.id} task={task} />)}
          </div>
        ))}
      </section>
    </main>
  );
};

export default App;
