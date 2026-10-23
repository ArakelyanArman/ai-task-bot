import { useCallback, useEffect, useRef, useState } from "react";

import { fetchTasks, updateTaskStatus } from "./api";

const mergeTask = (tasks, task) => {
    const index = tasks.findIndex((item) => item.id === task.id);
    if (index === -1) {
        return [task, ...tasks];
    }
    return tasks.map((item) => (item.id === task.id ? task : item));
};

export const useTasks = () => {
    const [tasks, setTasks] = useState([]);
    const [error, setError] = useState(null);
    const socketRef = useRef(null);

    const loadTasks = useCallback(async () => {
        try {
            setTasks(await fetchTasks());
            setError(null);
        } catch {
            setError("Could not load tasks.");
        }
    }, []);

    const changeStatus = useCallback(async (taskId, status) => {
        try {
            const updated = await updateTaskStatus(taskId, status);
            setTasks((current) => mergeTask(current, updated));
            setError(null);
        } catch {
            setError("Could not update the task.");
        }
    }, []);

    useEffect(() => {
        loadTasks();
        let reconnectTimer;
        let stopped = false;

        const connect = () => {
            const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
            const socket = new WebSocket(`${protocol}//${window.location.host}/ws`);
            socketRef.current = socket;

            socket.onopen = () => loadTasks();

            socket.onmessage = (event) => {
                let taskEvent;

                try {
                    taskEvent = JSON.parse(event.data);
                } catch {
                    return;
                }

                if (!taskEvent?.task) return;

                setTasks((current) =>
                    taskEvent.type === "task.deleted"
                        ? current.filter((task) => task.id !== taskEvent.task.id)
                        : mergeTask(current, taskEvent.task),
                );
            };

            socket.onerror = () => socket.close();

            socket.onclose = () => {
                if (!stopped) {
                    reconnectTimer = window.setTimeout(connect, 2000);
                }
            };
        };

        connect();

        return () => {
            stopped = true;
            window.clearTimeout(reconnectTimer);
            socketRef.current?.close();
        };
    }, [loadTasks]);

    return { tasks, error, changeStatus };
};
