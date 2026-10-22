const request = async (input, init) => {
  const response = await fetch(input, init);
  if (!response.ok) {
    throw new Error(`Request failed (${response.status})`);
  };
  return response.json();
};

export const fetchTasks = () => {
  return request("/api/tasks");
};

export const updateTaskStatus = (taskId, status) => {
  return request(`/api/tasks/${taskId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
};
